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

- 호스트에 통합 허브 `*.axdt/hub/project.git*`(bare) 1개.
- 각 Leader 작업본 `worktrees/<id>/`는 허브에서 clone된 **완전한 `.git`**을 가진 독립 클론. → 컨테이너 안에서 git이 그대로 동작.
- 통합은 Leader가 branch를 **허브로 push**, Maintainer가 허브에서 fetch·검토·머지.
- 컨테이너는 **자기 작업본만 RW 마운트**(D3). 허브 접근은 **파일시스템 교차 마운트가 아니라 git 프로토콜**(`git daemon`)로 → 다른 Leader 작업본을 절대 못 본다.

> 용어: SoT 규칙·기존 문서가 쓰는 "worktree"는 본 설계에서 **"Leader별 격리 작업 디렉터리"**를 가리키며, 구현은 `git worktree`가 아니라 **bare 허브 clone**이다. 디렉터리명·격리 단위(task:Leader:worktree:container 1:1)는 그대로다.

### 2.2 git 전송 — 기본 `git daemon`, 폴백 `file://` 마운트
- **기본(daemon):** 호스트에서 허브를 `git daemon --base-path=.axdt/hub --export-all --enable=receive-pack`로 노출. 컨테이너는 `--add-host=host.docker.internal:host-gateway`로 호스트를 찾아 `git://host.docker.internal:9418/project.git`에서 clone/push. 컨테이너 마운트는 **자기 작업본뿐**(D3 최대 충실).
- **폴백(file):** 네트워킹이 까다로운 환경에선 허브를 컨테이너에 RW 마운트하고 `file://` 사용. 작업본 외 마운트가 1개 늘지만(허브 = 의도된 공유 통합점) 다른 worktree는 여전히 차단.
- 전송은 `axdt`의 단일 설정값(`AXDT_HUB_TRANSPORT=daemon|file`)으로 선택. **기본은 daemon.**

### 2.3 실행 substrate = tmux 윈도우 안의 컨테이너
Maintainer는 호스트의 **상시 tmux 세션 `axdt`**(ADR-0001)를 소유한다. Leader 하나당 **tmux 윈도우 1개**를 열고, 그 윈도우에서 컨테이너를 **인터랙티브로 실행**한다.

```
tmux 세션 axdt
  └─ 윈도우 <id> : docker run -it ... axdt/leader <command>
        ├─ send-keys  → 컨테이너 stdin (prompt 주입, ADR-0003 하향)
        └─ pipe-pane  → 로그 파일 (출력 증분 읽기)
```
- **하향(주입):** `tmux send-keys -t <id> '<prompt>' Enter` → 컨테이너 안 프로세스의 stdin.
- **상향(읽기):** `tmux pipe-pane -o 'cat >> <logfile>'`로 pane 출력을 로그 파일에 스트리밍 → 저장된 바이트 오프셋부터 증분 읽기. (Phase 5 "단일 drain" 규약과 정합 — runner의 `read_new_output`이 이 증분을 소비.)
- **상향 권위 아님:** 이 출력 읽기는 **모니터링·liveness·readiness용**이다. 작업 결과의 권위 채널은 **report 파일**(ADR-0003/0004). Phase 5 §2.3과 동일 입장.

### 2.4 Phase 5 계약 충족 — `TmuxDockerBackend(SessionBackend)`
Phase 5는 `SessionBackend` ABC(`start/send_text/read_new_output/is_alive/stop`)를 정의하고 `FakeBackend`로 테스트한다. 본 Phase가 **실substrate 구현 `TmuxDockerBackend`**를 제공한다. 이로써 `AgentRunner(adapter, TmuxDockerBackend(...))`가 실제 tmux+Docker 위에서 구동된다.

- 의존 방향: Phase 3 → Phase 5의 **인터페이스(ABC)** 에만 의존(구현이 아님). ABC는 `axdt/agent_runner/backend.py`(Phase 5)에 있다.
- 병렬 진행 조율: agent_runner 서브패키지가 아직 main에 없으면, 본 Phase는 **문서화된 ABC 시그니처에 맞춰** `TmuxDockerBackend`를 구현하고 import 배선은 통합 시점에 맞춘다. Leader 간 조율은 **Maintainer 경유**(rule-leader-coordination-via-maintainer).

### 2.5 상태 저장소 없음 (ADR-0002)
컨테이너/세션/작업본 존재 여부를 별도 파일/DB에 적지 않는다. **`docker ps`·`tmux list-windows`·디렉터리 존재**를 라이브 조회해 도출. `.axdt/`에 두는 것은 허브와 캡처 로그 같은 **파생·재생성 가능 산출물**뿐.

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
def validate(name: str, kind: Literal["identifier","branch","container","worktree"]) -> None
```

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
      tmux.py                     # ensure_session/new_window/send_keys/pipe-pane/read_increment/kill
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
  hub/project.git/        # bare 통합 허브
  capture/<id>.log        # tmux pipe-pane 출력 로그(증분 읽기 소스)
worktrees/
  <id>/                   # Leader별 격리 클론 (컨테이너에 RW 마운트되는 유일 경로)
```
`.gitignore`에 `.axdt/`, `worktrees/` 추가(Phase 0 항목과 정합). progress는 추적(D10)이며 본 경로와 무관.

---

## 6. 모듈별 동작 규약

### 6.1 `hub.py`
- `init(path=.axdt/hub/project.git)` → `git init --bare`. 멱등(이미 있으면 통과).
- `serve(transport)` → daemon 모드일 때 `git daemon`을 백그라운드 기동(receive-pack 허용), 멱등(이미 떠 있으면 통과). file 모드는 no-op.
- `clone_url(transport)` → daemon: `git://host.docker.internal:9418/project.git` / file: 마운트 경로 `file:///hub/project.git`.

### 6.2 `worktree.py`
- `provision(i, base="main")` → 허브에 base 브랜치가 없으면 부트스트랩(빈 커밋), `worktrees/<i>`에 clone, 브랜치 `<i.value>` 생성·체크아웃, origin=허브. 멱등.
- `teardown(i, force=False)` → 미push 커밋이 있으면 force 아닐 때 거부(데이터 보호), 디렉터리 삭제.

### 6.3 `container.py`
- `build_image(tag="dev")` → `docker build -f infra/docker/leader.Dockerfile -t axdt/leader:<tag>`.
- `run_args(i, command, mount_dir, env, transport)` → `docker run` argv 생성: `--name axdt-<id>`, `-v <mount_dir>:/work`(RW, 작업본만), `-w /work`, `-it`, 이미지, command. 전송별 추가: **daemon** → `--add-host=host.docker.internal:host-gateway`; **file** → 허브를 `-v .axdt/hub/project.git:/hub`(RW)로 추가 마운트(의도된 공유 통합점). **argv만 반환**(실행은 tmux 윈도우가 담당).
- `is_running(i)` / `stop(i)` / `rm(i)` → `docker ps`/`stop`/`rm` 래핑.

### 6.4 `tmux.py`
- `ensure_session(name="axdt")` → 없으면 detached 생성. 멱등.
- `new_window(window, argv, cwd)` → `tmux new-window -t axdt -n <window>`로 argv 실행.
- `send_keys(window, text)` → `tmux send-keys -t axdt:<window> -- <text> Enter`.
- `start_capture(window, logfile)` → `tmux pipe-pane -o -t axdt:<window> 'cat >> <logfile>'`.
- `read_increment(logfile, offset)` → `(text, new_offset)`; 로그를 offset부터 읽고 새 오프셋 반환.
- `window_exists(window)` / `kill_window(window)`.

### 6.5 `backend.py` — `TmuxDockerBackend(SessionBackend)`
식별자 `i`로 생성. 계약 매핑:
- `start(command, cwd, env)` → `hub.serve()`; `tmux.ensure_session()`; `tmux.new_window(window(i), container.run_args(i, command, cwd, env, transport), cwd)`; `tmux.start_capture(window(i), .axdt/capture/<id>.log)`; 내부 오프셋 0.
- `send_text(text)` → `tmux.send_keys(window(i), text)`.
- `read_new_output()` → `tmux.read_increment(logfile, offset)`의 증분 반환·오프셋 갱신.
- `is_alive()` → `container.is_running(i) and tmux.window_exists(window(i))`.
- `stop()` → `tmux.kill_window(window(i))`; `container.stop(i)`; `container.rm(i)`. 멱등.

### 6.6 `leader.py` (CLI 합성)
- `up(i, base="main", command=PLACEHOLDER)` → `worktree.provision(i, base)`; `TmuxDockerBackend(i).start(command, worktree_dir(i))`.
- `down(i, force=False)` → `TmuxDockerBackend(i).stop()`; `worktree.teardown(i, force)`.

### 6.7 `cron.py`
- `install(interval_min, watcher_cmd)` → 사용자 crontab에 AXDT 마커 주석으로 둘러싼 항목 추가(멱등 교체).
- `uninstall()` → 마커 블록 제거.

### 6.8 `cli.py` — `axdt <domain> <verb>`
```
axdt hub init|serve
axdt verify-naming <name> --kind identifier|branch|container|worktree
axdt worktree create <id> [--base main] | rm <id> [--force]
axdt container build [--tag dev] | up <id> | down <id>
axdt tmux ensure | send <id> "<text>" | capture <id>
axdt cron install --every <min> --cmd "<watcher>" | uninstall
axdt leader up <id> [--base main] | down <id> [--force]
```

---

## 7. Docker 이미지 (`leader.Dockerfile`)
- 베이스 `python:3.12-slim`(Debian 계열, Python 도구 전방호환) + `git`·`bash` 설치.
- 비root 사용자, `WORKDIR /work`.
- `COPY leader-placeholder.sh /usr/local/bin/axdt-leader-placeholder` (+x).
- `CMD ["axdt-leader-placeholder"]` (Phase 5에서 agent 명령으로 교체 가능).
- agent runner(Claude Code/Codex) 설치·자격증명은 **Phase 5**에서 이미지 확장.

---

## 8. 테스트 전략
- **단위(기본, mock):** `proc.run`을 모킹해 각 모듈이 **올바른 argv**를 만드는지 검증. 네트워크/도커/ tmux 불필요.
  - `test_naming`: 유효/무효 식별자, 슬래시·zero-pad 거부, helper 산출(branch/container/worktree dir) 일치.
  - `test_worktree|container|tmux`: 생성되는 명령 argv·멱등·에러 변환.
  - `test_backend`: `TmuxDockerBackend`가 `SessionBackend` 계약을 만족(start→send→read 증분→is_alive→stop)하는지, tmux/container 모듈 모킹으로 검증.
- **통합(`@pytest.mark.integration`, WSL2):** 실 docker/tmux로 1사이클 — `hub init`→`worktree create`→`leader up`(placeholder)→`tmux send`로 한 줄 주입→`capture`에 `received: ...` 확인→`leader down`→정리 확인. (CI 기본 제외, WSL2에서 수동/옵트인 실행.)
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
