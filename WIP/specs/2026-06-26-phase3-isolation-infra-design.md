# Phase 3 — 격리 & 인프라(Isolation / Infra) 설계

> 상태: **승인됨 (브레인스토밍 합의)** · 작성일 2026-06-26 · 범위: Phase 3 (WIP/TODO.md)
> 산출 깊이: **실동 인프라 CLI** — workspace 클론·Docker 컨테이너·tmux 세션·cron·네이밍 검증을 실제 수행. 세션 안에서 실행되는 명령은 **placeholder**(agent runner는 Phase 5 seam).
> 관련 결정: D3(workspace당 컨테이너 1개, 해당 workspace만 RW), D5(GitHub 1차), D6(트리거), D9(Python), D10(progress 커밋), D11(README), D12(AXDT 자체 코드는 `WIP/`)
> 관련 ADR: `WIP/adr/0001`(상시 tmux Maintainer), `0002`(무 DB/큐), `0003`(tmux 하향·report 상향), (신규) `WIP/adr/0006-git-isolation-via-local-bare-hub.md`
> 관련 규칙: `docs/sot/rule/branch-workspace-naming.md`
> 교차-Phase 계약: Phase 5 스펙(`WIP/specs/2026-06-26-phase5-agent-runner-design.md`) §2.2 — 본 Phase가 `TmuxDockerBackend(SessionBackend)`를 구현한다.

---

## 1. 목표와 비목표

### 목표
- Leader 작업을 **workspace·컨테이너로 격리**(D3)하고, Maintainer가 **tmux로 다수 Leader 세션을 관리**(ADR-0001/0003)하는 실행 substrate를 Python으로 구현한다.
- 격리된 세션에 **임의의 명령**을 띄우고, **tmux send-keys로 prompt를 주입**하고, **출력을 증분으로 읽고**, 정리(teardown)까지 하는 **실동 CLI** (`axdt`)를 제공한다.
- Phase 5의 `SessionBackend`(ABC)를 충족하는 **`TmuxDockerBackend`**를 구현해, Phase 5 agent runner가 이 substrate 위에서 실제로 구동되게 한다.
- workspace·컨테이너 안에서 git이 동작하도록 **로컬 bare repo 허브**를 통합 지점으로 둔다(D3의 `.git` 공유 문제 해결).
- branch·workspace·container **네이밍 규칙을 강제**하는 검증을 제공한다.
- Watcher를 **cron으로 주기 호출**하도록 등록한다(ADR-0001).

### 비목표 (이 Phase에서 하지 않음)
- 세션 안에서 실제 Claude Code/Codex를 구동(→ Phase 5 어댑터가 명령을 제공). 본 Phase는 placeholder 명령으로 substrate를 검증한다.
- Watcher의 **context 압축 로직 자체**(→ Phase 2/Watcher 역할 정의). 본 Phase는 호출 배선(cron 등록 + 진입점)만.
- progress/report **파일 스키마와 승격 흐름**(→ Phase 4). 본 Phase는 D10 마일스톤 커밋의 git 배선 토대만 제공.
- GitHub 연동·PR 생성(→ Phase 6). 본 Phase의 통합 허브는 **로컬 bare repo**이며 GitHub는 그 위에 얹는다.
- 선언적 config 기반 수렴/상태 조정(→ Phase 8 오케스트레이션 엔진).
- 대상 환경: **Linux/WSL2 우선**. tmux/cron/Docker를 Linux 네이티브로 가정하고, 이 Windows 머신에서는 WSL2로 검증한다(Windows 네이티브 미지원).

---

## 2. 핵심 설계 결정

### 2.1 git 격리 — 로컬 bare repo 허브 (D3의 `.git` 공유 문제 해결) → `WIP/adr/0006`
`git worktree`는 메인 repo의 `.git`을 공유하므로, worktree 폴더만 컨테이너에 마운트하면 git이 동작하지 않는다. 해결: 각 Leader 작업본은 **bare 허브에서 clone한 독립 작업 디렉터리**다.

- 호스트에 통합 허브 `.axdt/hub/project.git`(bare) 1개 — **머지 전 Leader push를 보유하는 권위 상태**(§2.5).
- 각 Leader 작업본 `workspaces/<id>/`는 허브에서 clone된 **완전한 `.git`**을 가진 독립 클론. → 컨테이너 안에서 git이 그대로 동작.
- 통합은 Leader가 branch를 **허브로 push**, Maintainer가 허브에서 fetch·검토·머지.
- 컨테이너는 **자기 작업본만 RW 마운트**(D3). 허브 접근은 **파일시스템 교차 마운트가 아니라 git 프로토콜**(`git daemon`)로 → 다른 Leader 작업본을 절대 못 본다.

> 용어: 본 설계에서 **"Leader별 격리 작업 디렉터리"**는 `workspace`로 표기하며(구현은 `git worktree`가 아니라 **bare 허브 clone**), 격리 단위(task:Leader:workspace:container 1:1)는 그대로다.

실제 SoT 규칙 파일(`docs/sot/rule/branch-workspace-naming.md`) 개명과 WIP/TODO.md의 D3 문구 갱신은 이 브랜치 밖이라 통합 시 Maintainer가 조율한다.

### 2.2 git 전송 — 기본 `git daemon`(strict), 폴백 `file://` 마운트(relaxed)
- **기본 = strict(daemon):** 호스트에서 허브를 `git daemon --base-path=<.axdt/hub 절대경로> --port=<port> --export-all --enable=receive-pack`로 노출. 컨테이너는 `--add-host=host.docker.internal:host-gateway`로 호스트를 찾아 `git://host.docker.internal:<port>/project.git`에서 push. **포트(`AXDT_HUB_PORT`): 기본 9418, 점유 시 프로젝트 경로 해시로 등록 대역(10000–49151, ephemeral 49152+ 회피)에서 결정적 파생** → 비-AXDT git daemon과의 클래시 회피. `serve()`는 **readiness 확인**(포트 connect)까지 대기, PID를 `.axdt/hub/daemon.pid` 추적.
- **단일 프로젝트 전제(Phase 3):** tmux 세션은 `axdt`(단일), 컨테이너는 SoT 규칙상 `axdt-<식별자>`로 **호스트 전역 네임**이다. 따라서 **호스트당 동시 1개 AXDT 프로젝트**를 전제한다(두 프로젝트가 같은 식별자를 쓰면 윈도우/컨테이너가 충돌). 다중 프로젝트 동시구동은 비목표 — 필요 시 세션·컨테이너에 프로젝트 네임스페이스를 입히는 것은 후속(SoT 컨테이너 규칙 변경 동반). 포트 파생은 이 전제와 무관한 데몬 클래시 방어일 뿐 다중 프로젝트를 보장하지 않는다.
- **폴백 = relaxed(file):** 네트워킹이 까다로운 환경에선 허브를 컨테이너에 RW 마운트(`-v <.axdt/hub/project.git 절대경로>:/hub`)하고 `file:///hub`. **D3 격리의 명시적 예외** — 작업본 외 마운트가 1개 늘지만(허브 = 의도된 공유 통합점) 다른 작업본은 여전히 차단. bind mount 경로는 Docker에 넘기기 전 **절대경로로 resolve + 존재 검증**.
- 전송은 단일 설정값(`AXDT_HUB_TRANSPORT=daemon|file`, 기본 `daemon`)으로 선택.
- **격리 정직성:** 본 Phase가 강제하는 것은 **파일시스템 격리**(D3: 작업본만 마운트)다. 로컬 daemon은 **설계상 무인증**(단일 호스트·단일 사용자 오프라인 허브)이라 `receive-pack`을 켜면 어떤 클론이든 허브의 임의 ref를 push할 수 있다 — 즉 **Leader 간 git-ref 수준 격리는 advisory이며 강제되지 않는다.** 강제하려면 인증(SSH/auth)·pre-receive ACL 도입이 필요하고, 이는 **하드닝 단계로 연기**(현재 범위 밖, 단일 사용자 신뢰 호스트 가정).

### 2.3 실행 substrate = tmux 윈도우 안의 컨테이너
Maintainer는 호스트의 **상시 tmux 세션 `axdt`**(ADR-0001)를 소유한다. Leader 하나당 **tmux 윈도우 1개**를 열고, 그 윈도우에서 컨테이너를 **인터랙티브로 실행**한다.

```
tmux 세션 axdt
  └─ 윈도우 <id> : docker run -it ... axdt/leader <command>
        ├─ send-keys  → 컨테이너 stdin (prompt 주입, ADR-0003 하향)
        └─ pipe-pane  → 로그 파일 (출력 증분 읽기)
```
- **하향(주입):** `backend.send_text(text)`는 받은 텍스트를 **그대로**(제출키 미부착) pane에 보낸다. 단일 라우팅: 텍스트에 **개행·제어문자가 없으면 `send-keys -l`**, **있으면 `load-buffer`+`paste-buffer`**(개행/특수키 보존). **Enter 부착은 backend가 하지 않는다** — Phase 5 `adapter.format_prompt`가 제출 개행/키를 포함해 렌더하므로(이중 제출 방지). CLI `--submit`(§6.8)이 붙이는 개행도 이 라우팅을 거쳐 paste-buffer로 전달된다.
- **tmux 타깃 정확성:** 윈도우/페인은 **이름이 아니라 생성 시 캡처한 고유 id(`@window-id`)로 타깃**한다. 식별자에 점(`.`)이 있어 `-t axdt:<name>`은 tmux가 `window.pane`으로 오해석하거나 prefix 매칭(`w3.t1-a`⊂`w3.t1-ab`)할 수 있기 때문(§3 정합 검증에 tmux 항목 포함).
- **상향(읽기):** `tmux pipe-pane -o 'cat >> <logfile>'`로 pane 출력을 로그 파일에 스트리밍 → 저장된 바이트 오프셋부터 증분 읽기. (Phase 5 "단일 drain" 규약과 정합 — runner의 `read_new_output`이 이 증분을 소비.) 로그는 **start 시 truncate**(§5)해 이전 run의 stale 출력 재전달을 막는다.
- **상향 권위 아님:** 이 출력 읽기는 **모니터링·liveness·readiness용**이다. 작업 결과의 권위 채널은 **report 파일**(ADR-0003/0004). Phase 5 §2.3과 동일 입장. → 따라서 **prompt 주입 이전의 배너 등 초기 출력 캡처는 best-effort**이며, 결정적 검증은 prompt 주입 이후 출력에 대해 한다(§8).

### 2.4 Phase 5 계약 충족 — `TmuxDockerBackend(SessionBackend)`
Phase 5의 `SessionBackend` ABC를 본 Phase가 실substrate로 구현한다. 드리프트 방지를 위해 **계약 시그니처를 여기 인라인 고정**한다(Phase 5 스펙 §3과 일치해야 함; 불일치 시 Maintainer 경유 조율).

```python
from collections.abc import Mapping, Sequence
from pathlib import Path

class SessionBackend(ABC):
    def start(self, command: Sequence[str], cwd: Path,
              env: Mapping[str, str] | None = None) -> None: ...
    def send_text(self, text: str) -> None: ...      # literal, 제출키 미부착(§2.3)
    def read_new_output(self) -> str: ...            # 마지막 read 이후 증분
    def is_alive(self) -> bool: ...
    def stop(self) -> None: ...                       # 멱등
```

**에러/상태 계약(본 Phase가 추가 고정):**
- `command`은 **argv `Sequence[str]`**(shell 문자열 아님). shell 변환·quoting 책임은 `tmux.new_window` 한 곳.
- 상태 전이: `NOT_STARTED → start() → RUNNING → stop() → STOPPED`.
- `start()`를 RUNNING에서 재호출 → `AlreadyStarted`. NOT_STARTED에서 `send_text/read_new_output` → `NotStarted`.
- 세션이 죽은 뒤 `send_text` → `SessionDead`. `read_new_output`은 죽은 뒤에도 **남은 로그 증분을 반환**(드레인 허용), 그 다음 빈 문자열.
- `stop()`은 **멱등**(이미 STOPPED여도 무해), 부분 잔여(window-only/container-only)도 best-effort 정리.
- **provision 책임(중요):** `start(command, cwd, env)`의 `cwd`는 **호스트 bind 소스(작업본 절대경로)** 의미이며, 컨테이너 cwd는 `/work` 고정. **start는 작업본을 clone(provision)하지 않는다** — 작업본 존재는 **호출자(`leader.up`)가 보장**한다. Phase 5가 `AgentRunner(adapter, TmuxDockerBackend(i))`로 backend를 직접 구동할 경우에도 **반드시 `workspace.provision(i)` 선행** 후 `start`의 `cwd=workspace_dir(i)`를 넘겨야 한다(미존재 시 마운트/push 실패). 이 책임 경계를 ABC 주석으로 고정.
- **hub 책임 경계:** start는 `hub.init`(seed 필요)을 하지 않고 **`hub.serve()`+존재 보장만** 한다. `hub.init(seed_from=canonical)`은 seed source를 아는 `leader.up`/`provision`의 책임(§6.1/§6.2).

- 의존 방향: Phase 3 → Phase 5의 **인터페이스(ABC)** 에만 의존(구현이 아님). ABC는 `axdt/agent_runner/backend.py`(Phase 5).
- **권위:** Phase 5 스펙 파일은 본 worktree에 없으므로(병렬 세션), 위 **인라인 계약을 Phase 3 구현의 단일 권위**로 삼는다. agent_runner가 main에 들어오면 시그니처 대조·정합은 **통합 시 Maintainer가 수행**(rule-leader-coordination-via-maintainer)하며, 불일치 시 ADR/조율로 해소.

### 2.5 상태 저장소 없음 (ADR-0002) — 단, 허브는 권위 상태
컨테이너/세션/작업본 **존재 여부**를 별도 파일/DB에 적지 않는다. **`docker ps`·`tmux list-windows`·디렉터리 존재**를 라이브 조회해 도출(여기까지가 ADR-0002의 "무 상태저장소"). `.axdt/`의 산출물은 **권위 등급이 다르다**:
- **허브 `hub/project.git` = 권위 상태**(파생 아님). 머지 전 Leader push(미머지 branch)를 보유하므로 **함부로 재생성·삭제 금지.** 손실 시 미머지 작업이 사라진다.
  - **Seed(강제):** 신규 허브는 **현 작업 repo(canonical, 또는 Phase 6 GitHub)에서 `git push --mirror`로 seed**한다. `hub.init`은 **seed source를 필수로 받으며**, seed 없는 빈 허브는 **명시적 `--empty`로만** 허용(도그푸딩/테스트용). `provision`/`leader up`은 기본적으로 canonical repo를 seed source로 넘긴다 → §2.5/§6.1/§6.2 정합.
  - **복구:** 허브가 권위이며, 보조 미러는 Phase 6 호스트. 본 Phase는 호스트 미러를 만들지 않으므로 **허브 백업은 사용자/Maintainer 책임**(연기 항목으로 명시).
- **캡처 로그 `capture/<id>.log` = 파생·재생성 가능**(모니터링 전용, start 시 truncate).

> 이는 ADR-0002와 모순이 아니다 — ADR-0002가 거부한 것은 *진척·이벤트용 별도 DB/큐*이고, 허브는 git 그 자체(이미 권위본·이력 매체)다.

### 2.6 placeholder seam
세션 안 기본 실행 명령은 `axdt-leader-placeholder` — 배너를 찍고 stdin 라인을 읽어 `received: <line>`을 출력하는 작은 스크립트. send-keys→stdin→capture 경로를 agent 없이 실증한다. Phase 5에서 이 명령이 adapter의 `build_launch_command` 산출물로 교체된다.

---

## 3. 네이밍 (`naming.py`) — SoT 규칙 구현

`docs/sot/rule/branch-workspace-naming.md`를 코드로 강제한다. **단일 식별자 `w<n>.t<n>-<slug>`** 가 branch·workspace·container를 모두 구동. zero-pad 없음, 점 구분, **슬래시 금지**.

| 대상 | 형식(정규식) | 예 |
|---|---|---|
| 식별자 | `^w[1-9]\d*\.t[1-9]\d*-[a-z0-9]+(-[a-z0-9]+)*$` | `w3.t12-auth-login` |
| branch | = 식별자 | `w3.t12-auth-login` |
| workspace dir | `workspaces/<식별자>` | `workspaces/w3.t12-auth-login` |
| container | `axdt-<식별자>` | `axdt-w3.t12-auth-login` |
| tmux 윈도우 | = 식별자 (세션은 `axdt` 단일) | `w3.t12-auth-login` |
| leader 이미지 | `axdt/leader:<tag>` | `axdt/leader:dev` |

예약: `main`/`develop` 등 long-lived 통합 브랜치는 규칙 대상 아님. 숫자부는 **선행 0 금지**(`w03`/`t012` 거부 — §8 테스트와 정합). 점·슬래시는 Docker 컨테이너명/디렉터리/git ref 제약과 정합(점 허용, 슬래시 불가)임을 검증하고, **tmux는 점을 `window.pane` 구분자로 보므로 이름 대신 `@window-id`로 타깃**(§2.3)함을 정합 항목에 포함.

API:
```python
@dataclass(frozen=True)
class Identifier:
    wave: int
    task: int
    slug: str
    def __post_init__(self):             # 불변식 보장: 직접 생성도 검증 통과해야
        validate(self.value)             # 위반 시 NamingError (w0/t0·대문자·슬래시 등 차단)
    @property
    def value(self) -> str: ...          # "w{wave}.t{task}-{slug}"

def parse(value: str) -> Identifier      # 위반 시 NamingError
def is_valid(value: str) -> bool
def branch(i: Identifier) -> str
def workspace_dir(i: Identifier) -> Path  # workspaces/<value>
def container(i: Identifier) -> str      # axdt-<value>
def tmux_window(i: Identifier) -> str    # <value>
def validate(identifier: str) -> None    # raw 식별자만 받음; 위반 시 NamingError
```
> `validate`/`verify-naming`은 **raw 식별자**(`w3.t12-auth-login`)를 입력으로 받는다(렌더된 `axdt-...`/`workspaces/...`가 아님). 렌더는 `branch/container/workspace_dir/tmux_window` 헬퍼가 단방향으로 생성하므로, 검증은 식별자 한 곳만 보면 충분하다.

---

## 4. 패키지 레이아웃 (D12 → `WIP/`, Phase 5 컨벤션 준수)

`agent_runner`와 **형제 서브패키지 `infra`**. `pyproject.toml`은 `WIP/` 루트(Phase 5가 정의)에 `console_script: axdt`를 추가.

```
WIP/
  pyproject.toml                  # [Phase5 정의] + console_scripts: axdt = axdt.cli:main
  axdt/
    __init__.py
    cli.py                        # axdt <domain> <verb> 디스패치 (argparse)
    agent_runner/                 # [Phase5, 병렬]
    infra/                        # [Phase3, 본 설계]
      __init__.py
      README.md                   # D11: 목적·구성·네이밍
      config.py                   # .axdt/·workspaces/ 경로, 상수, env(AXDT_HUB_TRANSPORT 등)
      proc.py                     # subprocess 공통 래퍼(run/capture/에러→ProcError)
      naming.py                   # §3
      hub.py                      # bare 허브 init/serve, clone_url
      workspace.py                # provision/teardown (허브 clone + 브랜치)
      container.py                # 이미지 build, run argv, stop/rm/is_running
      tmux.py                     # ensure_session/new_window(@id)/send_text/pipe-pane/read_increment/kill
      cron.py                     # watcher crontab install/uninstall
      backend.py                  # TmuxDockerBackend(SessionBackend)
      leader.py                   # up=workspace+container+window+capture / down=역순
      docker/
        leader.Dockerfile         # git + placeholder, 비root, workdir=/work
        leader-placeholder.sh     # stdin echo 루프(seam 실증)
      tests/
        __init__.py
        test_naming.py
        test_proc.py
        test_workspace.py
        test_container.py
        test_tmux.py
        test_backend.py           # SessionBackend 계약(모킹)
        test_integration_wsl2.py  # @pytest.mark.integration (실 docker/tmux)
```

---

## 5. 런타임 레이아웃 (모두 gitignore)

```
.axdt/
  hub/project.git/        # bare 통합 허브  ← 권위 상태(§2.5), 재생성 금지
  hub/daemon.pid          # git daemon PID (readiness/정리용)
  capture/<id>.log        # tmux pipe-pane 출력 로그 ← 파생, start 시 truncate
workspaces/
  <id>/                   # Leader별 격리 클론 (컨테이너에 RW 마운트되는 유일 경로)
```
- `.gitignore`에 `.axdt/`, `workspaces/` 추가(Phase 0 항목과 정합). progress는 추적(D10)이며 본 경로와 무관.
- **로그 수명주기:** `capture/<id>.log`는 `start()`에서 **truncate(또는 run마다 새 파일)** → 같은 식별자 재기동 시 이전 run의 출력이 오프셋 0부터 재전달되는 것을 방지. 오프셋은 backend 내부 상태이며 backend 수명과 일치(재생성 시 §2.4 드레인 계약 적용).

---

## 6. 모듈별 동작 규약

### 6.1 `hub.py`
- `init(path=.axdt/hub/project.git, seed_from, empty=False)` → 없을 때만 `git init --bare`. **seed_from 필수**: **canonical은 로컬 repo 경로**이며 `git -C <canonical> push --mirror <hub 절대경로>`로 seed(원격 URL이면 먼저 mirror clone 후 push). `empty=True`면 seed 생략(테스트용). **이미 내용이 있으면 절대 덮어쓰지 않음**(권위, §2.5).
- `serve(transport)` → daemon 모드: 절대 base-path로 `git daemon --port=<파생 port>`(receive-pack 허용) 백그라운드 기동, **readiness 확인**(포트 connect + `git ls-remote`로 기대 repo identity 확인), PID를 `daemon.pid` 기록. 이미 떠 있으면 **PID cmdline/base-path 검증** 후 통과(stale PID·타 워크스페이스 포트점유 구분). file 모드는 no-op.
- `stop_daemon()` → **활성 Leader 세션(`tmux list-windows`)이 있으면 거부**(컨테이너 push 단절 방지), 없을 때만 `daemon.pid` 종료. (재부팅 후 재기동은 `serve` 멱등 호출로; 자동 재기동 훅은 연기.)
- **clone URL 분리(정규):** `clone_url_for_host()` = **`file://<허브 절대경로>`**(호스트 작업은 항상 이 경로 — daemon 의존 없이 동작·정합). `clone_url_for_container(transport)` → daemon: `git://host.docker.internal:<port>/project.git` / file: `file:///hub`.

### 6.2 `workspace.py`
- `provision(i, base="main", force=False)` → **`hub.init(seed_from=canonical)`+`hub.serve()` 보장** → 허브에 base 브랜치 없으면 부트스트랩 → `clone_url_for_host()`로 **호스트에서** `workspaces/<i>`에 clone → 브랜치 `<i.value>` 생성·체크아웃 → **원격 2개 구성**: `hub`=`clone_url_for_host()`(호스트용, fetch·teardown 검사), `origin`=`clone_url_for_container(transport)`(컨테이너 내부 push용). **멱등 아님**: 작업본이 이미 있으면 `force` 없이 **fail-fast**, `force`면 **teardown(비force)** 후 재생성(미push 보호는 유지 → §6.2 teardown 규칙 그대로 적용).
- `teardown(i, force=False)` → **`hub` 원격(호스트 해석 가능)으로 fetch 후** 미push 커밋 유무 판정(`origin`=컨테이너 URL은 호스트에서 해석 불가하므로 검사에 쓰지 않음). 미push가 있으면 force 아닐 때 거부(데이터 보호), 이후 디렉터리 삭제.

### 6.3 `container.py`
- 경로·context는 `config`가 제공하는 **절대경로** 사용.
- `build_image(tag="dev")` → `docker build -f <leader.Dockerfile 절대경로> -t axdt/leader:<tag> <build context=axdt/infra/docker 절대경로>`. `image_exists(tag)` 제공.
- `run_args(i, command: Sequence[str], host_workdir: Path, env, transport)` → `docker run` argv: `--name axdt-<id>`, `-v <host_workdir 절대경로>:/work`(RW, 작업본만), `-w /work`, `--user <uid>:<gid>`(호스트 UID/GID → WSL2 bind mount 권한 회피), `-e HOME=/tmp/axdt-home`(**비-repo 경로** — passwd/HOME 부재 경고는 피하되 `~/.gitconfig`·자격증명이 작업트리에 새어 커밋되는 것 차단; Phase 5 도구용 nss-wrapper는 §7), `-it`, env, 이미지, **command(argv 그대로)**. 전송별: **daemon** → `--add-host=host.docker.internal:host-gateway`; **file** → `-v <.axdt/hub/project.git 절대경로>:/hub`(RW). **argv만 반환**.
- `exists(i)` / `is_running(i)` → **정확명 조회**(`docker ps -a --filter name=^/axdt-<id>$` 앵커 또는 `docker inspect axdt-<id>`) — docker name 필터는 substring이라 `axdt-w3.t1-a`가 `...-ab`에 오매칭되므로 **반드시 앵커/정확명**. `stop(i)` / `rm(i)` → 없는 컨테이너에도 무해(멱등). **이름 충돌 방지: start 전 `exists(i)` 검사**(중지된 컨테이너가 남아도 `docker run --name`은 실패) — 잔여 시 fail-fast 또는 `--force`로 `rm`.

### 6.4 `tmux.py`
- `ensure_session(name="axdt")` → 없으면 detached 생성. 멱등.
- `new_window(window, argv: Sequence[str], cwd) -> WindowId` → **`resolve_window` 기반 중복검사**로 이미 있으면 fail-fast. argv를 **한 곳에서 `shlex.quote`**해 `tmux new-window -n <window=식별자> -P -F '#{window_id}'`로 실행하고 **생성된 `@window-id` 반환**.
- **`resolve_window(i) -> WindowId|None` (프로세스 간 복구의 핵심):** `tmux list-windows -F '#{window_id} #{window_name}'` 출력을 받아 **Python에서 `window_name == i.value` 정확 일치**로 `@id`를 찾는다. tmux의 `-t <name>` 해석을 거치지 않으므로 점·prefix 문제 없음. 별도 CLI 프로세스(`leader down`/`tmux send`)와 start 사전검사·`new_window` 중복검사가 **모두 이 프리미티브를 공유**한다.
- `send_text(win_id, text)` → 개행·제어문자 없으면 `tmux send-keys -t <win_id> -l -- <text>`, 있으면 `load-buffer`+`paste-buffer -t <win_id>` (**둘 다 Enter 미부착**, §2.3).
- `start_capture(win_id, logfile)` → logfile **truncate 후** `tmux pipe-pane -o -t <win_id> "cat >> <shlex.quote(logfile)>"` — 로그 경로 quoting 필수(경로에 공백 존재: 예 `AX Strategy`).
- `read_increment(logfile, offset)` → `(text, new_offset)`; offset부터 **바이트로 읽고** UTF-8 디코드(`errors="replace"`), **말단 partial 멀티바이트 보류**(offset은 완전 디코드 바이트까지만 전진).
- `kill_window(win_id)`(없어도 무해). (윈도우 존재 확인은 `resolve_window(i) is not None`으로 일원화 — id 인자가 필요한 별도 `window_exists`는 두지 않음.)

### 6.5 `backend.py` — `TmuxDockerBackend(SessionBackend)`
식별자 `i`로 생성. **win_id는 인스턴스에 캐시하되, 비었으면 `tmux.resolve_window(i)`로 복구**(별도 CLI 프로세스에서 `down`/`send`가 동작하도록 — §6.4). 상태 머신(§2.4). 계약 매핑:
- `start(command, cwd, env)` → 상태 검사(RUNNING이면 `AlreadyStarted`); **사전 fail-fast = active run 신호만**(`tmux.resolve_window(i) is not None` 또는 `container.exists(i)`; **log 존재는 신호 아님** → start에서 truncate); `hub.serve()`·`tmux.ensure_session` 보장(**hub.init/provision은 안 함** → 호출자 책임, §2.4); `win_id = tmux.new_window(window(i), container.run_args(i, command, cwd, env, transport), cwd)`; `tmux.start_capture(win_id, log)`; 오프셋 0; RUNNING. **부분 실패 시 보상 정리**(역순 best-effort 후 예외 재전파).
  - `cwd` = **host_workdir(작업본 절대경로)**; 컨테이너 cwd는 `/work` 고정. **작업본 미존재면 즉시 실패**(provision은 호출자가 선행).
- `send_text(text)` → 상태 검사(NOT_STARTED→`NotStarted`, dead→`SessionDead`); win_id 복구; `tmux.send_text(win_id, text)`.
- `read_new_output()` → `_drain()`: `tmux.read_increment` 증분 반환·오프셋 갱신(죽은 뒤에도 잔여 드레인).
- `is_alive()` → `container.is_running(i) and tmux.resolve_window(i) is not None`.
- `status()` → `NOT_STARTED`/`RUNNING`/`WINDOW_ONLY`/`CONTAINER_ONLY`/`STOPPED`(§2.4 전이 포함, 부분 장애 노출).
- `stop()` → win_id 복구(`resolve_window(i)`) 후 `tmux.kill_window`; `container.stop(i)`; `container.rm(i)`. **멱등**(win_id 없어도 컨테이너는 name으로 정리, 윈도우 orphan 방지), STOPPED.

### 6.6 `leader.py` (CLI 합성)
- `up(i, base="main", command=PLACEHOLDER, tag="dev")` → **이미지 보장**(`container.image_exists(tag)` 아니면 `build_image` 또는 명확한 fail-fast); `workspace.provision(i, base)`(hub seed·serve 포함); `TmuxDockerBackend(i).start(command, workspace_dir(i))`. **start 실패 시** 방금 provision한 작업본까지 보상 정리(원자성 근사).
- `down(i, force=False)` → `TmuxDockerBackend(i).stop()`; `workspace.teardown(i, force)`.

### 6.7 `cron.py`
- `install(interval_min, watcher_cmd, *, cwd=config.project_root, env=config.cron_env)` → 사용자 crontab에 AXDT 마커 블록으로 항목 추가(멱등 교체). **cwd/env는 인자 미지정 시 config에서 파생**(CLI가 노출하지 않아도 일관). 엔트리는 **cwd로 cd**, **PATH/env 주입**, **flock 락파일로 overlap 방지**, 타임아웃 래핑 포함.
- `uninstall()` → 마커 블록 제거.

### 6.8 `cli.py` — `axdt <domain> <verb>`
```
axdt hub init [--seed-from <path|url>] [--empty] | serve | stop-daemon
axdt verify-naming <identifier>            # raw 식별자 검증(§3)
axdt workspace create <id> [--base main] [--force] | rm <id> [--force]
axdt container build [--tag dev] | stop <id> | rm <id>
axdt tmux ensure | send <id> "<text>" [--submit] | capture <id>
axdt cron install --every <min> --cmd "<watcher>" [--cwd <path>] | uninstall
axdt leader up <id> [--base main] [--tag dev] | down <id> [--force]
```
- container CLI는 모듈 책임(§6.3 build/stop/rm)과 일치 — **세션 기동/정리는 leader 레벨**(`leader up/down`)이 담당(컨테이너 단독 `up/down` 없음).
- `tmux send`의 `--submit`은 **개행을 덧붙여 한 줄 제출**(placeholder가 라인 단위로 읽으므로 수동/테스트용). backend `send_text`는 literal(제출키는 Phase 5 adapter 소유, §2.3) — `--submit`은 CLI 편의이며 계약과 분리.

---

## 7. Docker 이미지 (`leader.Dockerfile`)
- 베이스 `python:3.12-slim`(Debian 계열, Python 도구 전방호환) + `git`·`bash` 설치.
- build context = `axdt/infra/docker/`(절대경로, §6.3). `COPY leader-placeholder.sh /usr/local/bin/axdt-leader-placeholder` (+x).
- `WORKDIR /work`. **사용자는 빌드시 고정하지 않고 run에서 `--user <uid>:<gid>`로 호스트 UID/GID 주입**(§6.3) → bind mount 파일이 호스트 소유로 생성돼 WSL2 권한 충돌 회피. run에 `-e HOME=/tmp/axdt-home`(**비-repo 경로**)를 주입해 passwd/HOME 부재 경고는 피하되 도구 설정·자격증명이 작업트리에 새지 않게 한다. (placeholder엔 무해. **Phase 5 접합 메모:** commit author/HOME에 민감한 도구가 들어오면 `nss-wrapper`·`/etc/passwd` 보강 + HOME 디렉터리(tmpfs) 마운트를 이미지/run에 추가.)
- placeholder는 **line-buffered**(`stdbuf -oL` 또는 `python -u`)로 출력 → pipe-pane 캡처가 즉시 보이게(테스트 결정성).
- `CMD ["axdt-leader-placeholder"]` (Phase 5에서 agent 명령으로 교체 가능).
- agent runner(Claude Code/Codex) 설치·자격증명은 **Phase 5**에서 이미지 확장.

---

## 8. 테스트 전략
- **단위(기본, mock):** `proc.run`을 모킹해 각 모듈이 **올바른 argv**를 만드는지 검증. 네트워크/도커/ tmux 불필요.
  - `test_naming`: 유효/무효 식별자, **선행 0 거부(`w03`/`t012`)**, 슬래시 거부, helper 산출(branch/container/workspace dir) 일치.
  - `test_workspace|container|tmux`: 생성되는 명령 argv·멱등·에러 변환. tmux: `send_text`가 **Enter 미부착** + 개행 포함 시 paste-buffer 경로, `new_window` 중복 fail-fast·**`@window-id` 반환·타깃에 id 사용**, 로그경로 quoting, build context 절대경로, `--user`·`HOME` 주입 포함.
  - `test_backend`: `TmuxDockerBackend`가 계약 만족(start→send→read 증분→is_alive→stop) + **에러/상태 계약**(NOT_STARTED send→`NotStarted`, RUNNING start→`AlreadyStarted`, dead send→`SessionDead`, `stop` 멱등, start 부분 실패 보상 정리, **작업본 미존재 시 start 실패**)을 tmux/container 모킹으로 검증.
- **통합(`@pytest.mark.integration`, WSL2):** 실 docker/tmux로 1사이클 — `container build`→`hub init --seed-from <canonical-repo-path>`→`leader up`(=provision 포함, **별도 `workspace create` 없음** — 이중 provision 금지, §6.2)→`tmux send <id> "ping" --submit`→`capture`에 **주입 이후** `received: ping`을 **라인/정규식 매칭**(pty ANSI·echo 노이즈 대비 escape strip)으로 확인(초기 배너 best-effort, §2.3)→`leader down`→작업본·컨테이너 정리 확인. (CI 기본 제외, WSL2 옵트인.)
- 테스트는 `WIP/`에서 `pytest`로 구동(Phase 5 pyproject 설정 공유).

---

## 9. 산출물 체크리스트 (TODO Phase 3 매핑)
- [ ] Workspace 생성/삭제 자동화 → `workspace.py` (+ `hub.py`)
- [ ] Docker 격리(workspace당 1컨테이너, 해당 workspace만 마운트, D3) → `container.py`
- [ ] `.git` 공유 문제 해결(독립 클론 + bare 허브 + git 프로토콜) → `hub.py`/`workspace.py` + ADR-0006
- [ ] Leader를 Docker로 배치 자동화 → `leader.py` + `backend.py`
- [ ] Tmux 오케스트레이션(다수 Leader 윈도우 + send-keys 주입) → `tmux.py` + `backend.py`
- [ ] Cron 설정(Watcher 주기 호출) → `cron.py`
- [ ] 네이밍 규칙 강제 검증 → `naming.py` + `axdt verify-naming`
- [ ] (교차계약) `TmuxDockerBackend(SessionBackend)` → `backend.py`
- [ ] (후속, agent_runner main 진입 후) 실제 `SessionBackend` ABC import한 **`issubclass`/추상메서드 적합성 테스트** 추가 — 인라인 계약 드리프트 검출(현재는 duck-typing만)
- [ ] ADR 기록 → `WIP/adr/0006-git-isolation-via-local-bare-hub.md`
- [ ] 단위·통합 테스트 + `pyproject.toml` console_script

---

## 10. 다음 Phase 접합
- **Phase 4(진척 추적):** 같은 `axdt` 패키지에 `progress`/`report` 모듈을 형제 서브패키지로 추가. D10 마일스톤 커밋은 본 Phase의 허브·git 배선 위에서 동작.
- **Phase 5(agent runner):** `AgentRunner(adapter, TmuxDockerBackend(i))`로 실제 에이전트를 본 substrate 위에 구동. placeholder가 adapter 명령으로 교체.
- **Phase 7(Web·메신저):** progress/report(Phase 4)를 read-only 렌더. 본 Phase의 workspace/컨테이너 상태는 라이브 조회로 보조 표시 가능.

실제 SoT 규칙 파일(`docs/sot/rule/branch-workspace-naming.md`) 개명과 WIP/TODO.md의 D3 문구 갱신은 이 브랜치 밖이라 통합 시 Maintainer가 조율한다.
