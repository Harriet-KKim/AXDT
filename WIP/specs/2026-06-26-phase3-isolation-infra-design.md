# Phase 3 — 격리 & 인프라(Isolation / Infra) 설계

> 상태: **승인됨 (브레인스토밍 합의)** · 작성일 2026-06-26 · 범위: Phase 3 (WIP/TODO.md)
> 산출 깊이: **실동 인프라 CLI** — worktree 클론·Docker 컨테이너·tmux 세션·cron·네이밍 검증을 실제 수행. 세션 안에서 실행되는 명령은 **placeholder**(agent runner는 Phase 5 seam).
> 관련 결정: D3(worktree당 컨테이너 1개, 해당 worktree만 RW), D5(GitHub 1차), D6(트리거), D9(Python), D10(progress 커밋), D11(README), D12(AXDT 자체 코드는 `WIP/`)
> 관련 ADR: `WIP/adr/0001`(상시 tmux Maintainer), `0002`(무 DB/큐), `0003`(tmux 하향·report 상향), (신규) `WIP/adr/0006-git-isolation-via-local-bare-hub.md`
> 관련 규칙: `docs/sot/rule/branch-worktree-naming.md`
> 교차-Phase 계약: Phase 5 스펙(`WIP/specs/2026-06-26-phase5-agent-runner-design.md`) §2.2 — 본 Phase가 `TmuxDockerBackend(SessionBackend)`를 구현한다.

---

## 1. 목표와 비목표

### 목표
- Leader 작업을 **worktree·컨테이너로 격리**(D3)하고, Maintainer가 **tmux로 다수 Leader 세션을 관리**(ADR-0001/0003)하는 실행 substrate를 Python으로 구현한다.
- 격리된 세션에 **임의의 명령**을 띄우고, **tmux send-keys로 prompt를 주입**하고, **출력을 증분으로 읽고**, 정리(teardown)까지 하는 **실동 CLI** (`axdt`)를 제공한다.
- Phase 5의 `SessionBackend`(ABC)를 충족하는 **`TmuxDockerBackend`**를 구현해, Phase 5 agent runner가 이 substrate 위에서 실제로 구동되게 한다.
- worktree·컨테이너 안에서 git이 동작하도록 **로컬 bare repo 허브**를 통합 지점으로 둔다(D3의 `.git` 공유 문제 해결).
- branch·worktree·container **네이밍 규칙을 강제**하는 검증을 제공한다.
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
- 각 Leader 작업본 `worktrees/<id>/`는 허브에서 clone된 **완전한 `.git`**을 가진 독립 클론. → 컨테이너 안에서 git이 그대로 동작.
- 통합은 Leader가 branch를 **허브로 push**, Maintainer가 허브에서 fetch·검토·머지.
- 컨테이너는 **자기 작업본만 RW 마운트**(D3). 허브 접근은 **파일시스템 교차 마운트가 아니라 git 프로토콜**(`git daemon`)로 → 다른 Leader 작업본을 절대 못 본다.

> 용어: SoT 규칙·기존 문서가 쓰는 "worktree"는 본 설계에서 **"Leader별 격리 작업 디렉터리"**를 가리키며, 구현은 `git worktree`가 아니라 **bare 허브 clone**이다. 디렉터리명·격리 단위(task:Leader:worktree:container 1:1)는 그대로다.

### 2.2 git 전송 — 기본 `git daemon`(strict), 폴백 `file://` 마운트(relaxed)
- **기본 = strict(daemon):** 호스트에서 허브를 `git daemon --base-path=<.axdt/hub 절대경로> --export-all --enable=receive-pack`로 노출. 컨테이너는 `--add-host=host.docker.internal:host-gateway`로 호스트를 찾아 `git://host.docker.internal:9418/project.git`에서 clone/push. 컨테이너 마운트는 **자기 작업본뿐**(D3 최대 충실). 포트는 단일 허브 기준 9418 고정. `serve()`는 **readiness 확인**(포트 connect 성공)까지 대기하고 PID를 `.axdt/hub/daemon.pid`로 추적.
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
- **하향(주입):** `backend.send_text(text)`는 받은 텍스트를 **literal로** pane에 보낸다(`tmux send-keys -l`). **제출키(Enter) 부착은 backend가 하지 않는다** — Phase 5 `adapter.format_prompt`가 제출 개행/키를 포함해 렌더하므로, backend가 또 Enter를 붙이면 이중 제출이 된다. multiline/특수키는 `load-buffer`+`paste-buffer`로 안전 전달.
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

- 의존 방향: Phase 3 → Phase 5의 **인터페이스(ABC)** 에만 의존(구현이 아님). ABC는 `axdt/agent_runner/backend.py`(Phase 5).
- 병렬 진행 조율: agent_runner가 아직 main에 없으면 위 인라인 시그니처에 맞춰 구현하고 import 배선은 통합 시점에. Leader 간 조율은 **Maintainer 경유**(rule-leader-coordination-via-maintainer).

### 2.5 상태 저장소 없음 (ADR-0002) — 단, 허브는 권위 상태
컨테이너/세션/작업본 **존재 여부**를 별도 파일/DB에 적지 않는다. **`docker ps`·`tmux list-windows`·디렉터리 존재**를 라이브 조회해 도출(여기까지가 ADR-0002의 "무 상태저장소"). `.axdt/`의 산출물은 **권위 등급이 다르다**:
- **허브 `hub/project.git` = 권위 상태**(파생 아님). 머지 전 Leader push(미머지 branch)를 보유하므로 **함부로 재생성·삭제 금지.** 손실 시 미머지 작업이 사라진다.
  - **Seed:** 신규 허브는 현 작업 repo(또는 Phase 6의 GitHub)에서 `git push --mirror`로 초기화. `hub.init`은 비어있을 때만 seed(멱등).
  - **복구:** 허브가 권위이며, 보조 미러는 Phase 6 호스트. 본 Phase는 호스트 미러를 만들지 않으므로 **허브 백업은 사용자/Maintainer 책임**(연기 항목으로 명시).
- **캡처 로그 `capture/<id>.log` = 파생·재생성 가능**(모니터링 전용, start 시 truncate).

> 이는 ADR-0002와 모순이 아니다 — ADR-0002가 거부한 것은 *진척·이벤트용 별도 DB/큐*이고, 허브는 git 그 자체(이미 권위본·이력 매체)다.

### 2.6 placeholder seam
세션 안 기본 실행 명령은 `axdt-leader-placeholder` — 배너를 찍고 stdin 라인을 읽어 `received: <line>`을 출력하는 작은 스크립트. send-keys→stdin→capture 경로를 agent 없이 실증한다. Phase 5에서 이 명령이 adapter의 `build_launch_command` 산출물로 교체된다.

---

## 3. 네이밍 (`naming.py`) — SoT 규칙 구현

`docs/sot/rule/branch-worktree-naming.md`를 코드로 강제한다. **단일 식별자 `w<n>.t<n>-<slug>`** 가 branch·worktree·container를 모두 구동. zero-pad 없음, 점 구분, **슬래시 금지**.

| 대상 | 형식(정규식) | 예 |
|---|---|---|
| 식별자 | `^w\d+\.t\d+-[a-z0-9]+(-[a-z0-9]+)*$` | `w3.t12-auth-login` |
| branch | = 식별자 | `w3.t12-auth-login` |
| worktree dir | `worktrees/<식별자>` | `worktrees/w3.t12-auth-login` |
| container | `axdt-<식별자>` | `axdt-w3.t12-auth-login` |
| tmux 윈도우 | = 식별자 (세션은 `axdt` 단일) | `w3.t12-auth-login` |
| leader 이미지 | `axdt/leader:<tag>` | `axdt/leader:dev` |

예약: `main`/`develop` 등 long-lived 통합 브랜치는 규칙 대상 아님. 점·슬래시 모두 Docker 컨테이너명/디렉터리/ git ref 제약과 정합(점 허용, 슬래시 불가)임을 검증.

API:
```python
@dataclass(frozen=True)
class Identifier:
    wave: int
    task: int
    slug: str
    @property
    def value(self) -> str: ...          # "w{wave}.t{task}-{slug}"

def parse(value: str) -> Identifier      # 위반 시 NamingError
def is_valid(value: str) -> bool
def branch(i: Identifier) -> str
def worktree_dir(i: Identifier) -> Path  # worktrees/<value>
def container(i: Identifier) -> str      # axdt-<value>
def tmux_window(i: Identifier) -> str    # <value>
def validate(identifier: str) -> None    # raw 식별자만 받음; 위반 시 NamingError
```
> `validate`/`verify-naming`은 **raw 식별자**(`w3.t12-auth-login`)를 입력으로 받는다(렌더된 `axdt-...`/`worktrees/...`가 아님). 렌더는 `branch/container/worktree_dir/tmux_window` 헬퍼가 단방향으로 생성하므로, 검증은 식별자 한 곳만 보면 충분하다.

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
      config.py                   # .axdt/·worktrees/ 경로, 상수, env(AXDT_HUB_TRANSPORT 등)
      proc.py                     # subprocess 공통 래퍼(run/capture/에러→ProcError)
      naming.py                   # §3
      hub.py                      # bare 허브 init/serve, clone_url
      worktree.py                 # provision/teardown (허브 clone + 브랜치)
      container.py                # 이미지 build, run argv, stop/rm/is_running
      tmux.py                     # ensure_session/new_window/send_literal/pipe-pane/read_increment/kill
      cron.py                     # watcher crontab install/uninstall
      backend.py                  # TmuxDockerBackend(SessionBackend)
      leader.py                   # up=worktree+container+window+capture / down=역순
      docker/
        leader.Dockerfile         # git + placeholder, 비root, workdir=/work
        leader-placeholder.sh     # stdin echo 루프(seam 실증)
      tests/
        __init__.py
        test_naming.py
        test_proc.py
        test_worktree.py
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
worktrees/
  <id>/                   # Leader별 격리 클론 (컨테이너에 RW 마운트되는 유일 경로)
```
- `.gitignore`에 `.axdt/`, `worktrees/` 추가(Phase 0 항목과 정합). progress는 추적(D10)이며 본 경로와 무관.
- **로그 수명주기:** `capture/<id>.log`는 `start()`에서 **truncate(또는 run마다 새 파일)** → 같은 식별자 재기동 시 이전 run의 출력이 오프셋 0부터 재전달되는 것을 방지. 오프셋은 backend 내부 상태이며 backend 수명과 일치(재생성 시 §2.4 드레인 계약 적용).

---

## 6. 모듈별 동작 규약

### 6.1 `hub.py`
- `init(path=.axdt/hub/project.git, seed_from=None)` → 없을 때만 `git init --bare` + (seed_from 있으면) `git push --mirror`로 seed. **이미 내용이 있으면 절대 덮어쓰지 않음**(권위 상태, §2.5). 멱등.
- `serve(transport)` → daemon 모드: 절대 base-path로 `git daemon`(receive-pack 허용) 백그라운드 기동, **readiness(포트 connect) 확인**까지 대기, PID를 `daemon.pid`에 기록. 이미 떠 있으면 통과. file 모드는 no-op.
- `stop_daemon()` → `daemon.pid` 기준 종료(정리용).
- `clone_url(transport)` → daemon: `git://host.docker.internal:9418/project.git` / file: `file:///hub/project.git`.

### 6.2 `worktree.py`
- `provision(i, base="main")` → **`hub.init()`+`hub.serve()` 보장**(없으면 생성·기동) → 허브에 base 브랜치 없으면 부트스트랩(빈 커밋) → `worktrees/<i>`에 clone → 브랜치 `<i.value>` 생성·체크아웃 → origin=허브 URL. **이미 작업본이 있으면 fail-fast**(중복 방지, force로만 재생성). 멱등(동일 상태 재호출 무해).
- `teardown(i, force=False)` → 미push 커밋이 있으면 force 아닐 때 거부(데이터 보호), 디렉터리 삭제.

### 6.3 `container.py`
- 경로·context는 `config`가 제공하는 **절대경로** 사용.
- `build_image(tag="dev")` → `docker build -f <infra/docker/leader.Dockerfile 절대경로> -t axdt/leader:<tag> <build context=infra/docker 절대경로>`.
- `run_args(i, command: Sequence[str], host_workdir: Path, env, transport)` → `docker run` argv: `--name axdt-<id>`, `-v <host_workdir 절대경로>:/work`(RW, 작업본만), `-w /work`, `--user <uid>:<gid>`(호스트 UID/GID로 실행 → WSL2 bind mount 소유권/권한 문제 회피), `-it`, env, 이미지, **command(argv 그대로)**. 전송별 추가: **daemon** → `--add-host=host.docker.internal:host-gateway`; **file** → `-v <.axdt/hub/project.git 절대경로>:/hub`(RW). **argv만 반환**(실행은 tmux 윈도우).
- `is_running(i)` / `stop(i)` / `rm(i)` → `docker ps`/`stop`/`rm` 래핑. `stop`·`rm`은 없는 컨테이너에도 무해(멱등).

### 6.4 `tmux.py`
- `ensure_session(name="axdt")` → 없으면 detached 생성. 멱등.
- `new_window(window, argv: Sequence[str], cwd)` → window 이미 존재 시 **fail-fast**(중복 금지). argv를 **한 곳에서 안전 quoting**(shlex)해 `tmux new-window -t axdt -n <window>`로 실행. shell 변환 책임은 여기 단일화.
- `send_literal(window, text)` → `tmux send-keys -t axdt:<window> -l -- <text>` (**literal, Enter 미부착**). multiline/특수키는 `load-buffer`+`paste-buffer`.
- `start_capture(window, logfile)` → logfile **truncate 후** `tmux pipe-pane -o -t axdt:<window> 'cat >> <logfile>'`.
- `read_increment(logfile, offset)` → `(text, new_offset)`.
- `window_exists(window)` / `kill_window(window)`(없어도 무해).

### 6.5 `backend.py` — `TmuxDockerBackend(SessionBackend)`
식별자 `i`로 생성, 상태 머신 보유(§2.4). 계약 매핑:
- `start(command, cwd, env)` → 상태 검사(RUNNING이면 `AlreadyStarted`); **사전 fail-fast**(`window_exists`/`is_running`/log 존재 시 중복 거부); `hub`·`tmux.ensure_session` 보장; `tmux.new_window(window(i), container.run_args(i, command, cwd, env, transport), cwd)`; `tmux.start_capture(...)`; 오프셋 0; 상태 RUNNING. **부분 실패 시 보상 정리**(역순 best-effort teardown 후 예외 재전파).
  - `cwd`는 **host_workdir**(작업본 절대경로)로 쓰이며, 컨테이너 내부 작업 디렉터리는 `/work` 고정(`container_cwd` 분리).
- `send_text(text)` → 상태 검사(NOT_STARTED→`NotStarted`, dead→`SessionDead`); `tmux.send_literal(window(i), text)`.
- `read_new_output()` → `_drain()`: `tmux.read_increment` 증분 반환·오프셋 갱신(죽은 뒤에도 잔여 드레인 허용).
- `is_alive()` → `container.is_running(i) and tmux.window_exists(window(i))`.
- `status()` → 디버그용 세부 상태(`RUNNING`/`WINDOW_ONLY`/`CONTAINER_ONLY`/`STOPPED`) — `is_alive`의 boolean이 가리는 부분 장애를 노출.
- `stop()` → `tmux.kill_window`; `container.stop`; `container.rm`. **멱등**(STOPPED 재호출·부분 잔여 무해), 상태 STOPPED.

### 6.6 `leader.py` (CLI 합성)
- `up(i, base="main", command=PLACEHOLDER)` → `worktree.provision(i, base)`(hub 보장 포함); `TmuxDockerBackend(i).start(command, worktree_dir(i))`. **start 실패 시** 방금 provision한 작업본까지 보상 정리(원자성 근사).
- `down(i, force=False)` → `TmuxDockerBackend(i).stop()`; `worktree.teardown(i, force)`.

### 6.7 `cron.py`
- `install(interval_min, watcher_cmd, cwd, env)` → 사용자 crontab에 AXDT 마커 블록으로 항목 추가(멱등 교체). 엔트리는 **명시 cwd로 cd**, **PATH/env 주입**, **flock 락파일로 overlap 방지**, 타임아웃 래핑을 포함(중복·장기 실행 누적 방지).
- `uninstall()` → 마커 블록 제거.

### 6.8 `cli.py` — `axdt <domain> <verb>`
```
axdt hub init [--seed-from <url>] | serve | stop-daemon
axdt verify-naming <identifier>            # raw 식별자 검증(§3)
axdt worktree create <id> [--base main] [--force] | rm <id> [--force]
axdt container build [--tag dev] | up <id> | down <id>
axdt tmux ensure | send <id> "<text>" | capture <id>
axdt cron install --every <min> --cmd "<watcher>" | uninstall
axdt leader up <id> [--base main] | down <id> [--force]
```

---

## 7. Docker 이미지 (`leader.Dockerfile`)
- 베이스 `python:3.12-slim`(Debian 계열, Python 도구 전방호환) + `git`·`bash` 설치.
- build context = `axdt/infra/docker/`(절대경로, §6.3). `COPY leader-placeholder.sh /usr/local/bin/axdt-leader-placeholder` (+x).
- `WORKDIR /work`. **사용자는 빌드시 고정하지 않고 run에서 `--user <uid>:<gid>`로 호스트 UID/GID 주입**(§6.3) → bind mount 파일이 호스트 소유로 생성돼 WSL2 권한 충돌 회피. (이미지에 특정 UID를 굳히지 않음.)
- placeholder는 **line-buffered**(`stdbuf -oL` 또는 `python -u`)로 출력 → pipe-pane 캡처가 즉시 보이게(테스트 결정성).
- `CMD ["axdt-leader-placeholder"]` (Phase 5에서 agent 명령으로 교체 가능).
- agent runner(Claude Code/Codex) 설치·자격증명은 **Phase 5**에서 이미지 확장.

---

## 8. 테스트 전략
- **단위(기본, mock):** `proc.run`을 모킹해 각 모듈이 **올바른 argv**를 만드는지 검증. 네트워크/도커/ tmux 불필요.
  - `test_naming`: 유효/무효 식별자, 슬래시·zero-pad 거부, helper 산출(branch/container/worktree dir) 일치.
  - `test_worktree|container|tmux`: 생성되는 명령 argv·멱등·에러 변환. tmux: `send_literal`이 **Enter를 붙이지 않음**, `new_window` 중복 fail-fast, build context 절대경로, `--user` 주입 포함.
  - `test_backend`: `TmuxDockerBackend`가 `SessionBackend` 계약을 만족(start→send→read 증분→is_alive→stop)하는지 + **에러/상태 계약**(NOT_STARTED에서 send→`NotStarted`, RUNNING에서 start→`AlreadyStarted`, dead에서 send→`SessionDead`, `stop` 멱등, start 부분 실패 시 보상 정리)을 tmux/container 모듈 모킹으로 검증.
- **통합(`@pytest.mark.integration`, WSL2):** 실 docker/tmux로 1사이클 — `hub init`→`worktree create`→`leader up`(placeholder)→`tmux send`로 한 줄 주입→`capture`에 **주입 이후** `received: ...` 확인(초기 배너는 best-effort, §2.3)→`leader down`→정리 확인. (CI 기본 제외, WSL2에서 수동/옵트인 실행.)
- 테스트는 `WIP/`에서 `pytest`로 구동(Phase 5 pyproject 설정 공유).

---

## 9. 산출물 체크리스트 (TODO Phase 3 매핑)
- [ ] Worktree 생성/삭제 자동화 → `worktree.py` (+ `hub.py`)
- [ ] Docker 격리(worktree당 1컨테이너, 해당 worktree만 마운트, D3) → `container.py`
- [ ] `.git` 공유 문제 해결(독립 클론 + bare 허브 + git 프로토콜) → `hub.py`/`worktree.py` + ADR-0006
- [ ] Leader를 Docker로 배치 자동화 → `leader.py` + `backend.py`
- [ ] Tmux 오케스트레이션(다수 Leader 윈도우 + send-keys 주입) → `tmux.py` + `backend.py`
- [ ] Cron 설정(Watcher 주기 호출) → `cron.py`
- [ ] 네이밍 규칙 강제 검증 → `naming.py` + `axdt verify-naming`
- [ ] (교차계약) `TmuxDockerBackend(SessionBackend)` → `backend.py`
- [ ] ADR 기록 → `WIP/adr/0006-git-isolation-via-local-bare-hub.md`
- [ ] 단위·통합 테스트 + `pyproject.toml` console_script

---

## 10. 다음 Phase 접합
- **Phase 4(진척 추적):** 같은 `axdt` 패키지에 `progress`/`report` 모듈을 형제 서브패키지로 추가. D10 마일스톤 커밋은 본 Phase의 허브·git 배선 위에서 동작.
- **Phase 5(agent runner):** `AgentRunner(adapter, TmuxDockerBackend(i))`로 실제 에이전트를 본 substrate 위에 구동. placeholder가 adapter 명령으로 교체.
- **Phase 7(Web·메신저):** progress/report(Phase 4)를 read-only 렌더. 본 Phase의 worktree/컨테이너 상태는 라이브 조회로 보조 표시 가능.
