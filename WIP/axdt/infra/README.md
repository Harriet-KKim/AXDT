# axdt.infra — Phase 3 격리 & 인프라

workspace 클론·Docker 컨테이너·tmux 세션·cron·네이밍 검증을 **실제로 수행**하는
Python 모듈 모음. 설계: [`WIP/specs/2026-06-26-phase3-isolation-infra-design.md`](../../specs/2026-06-26-phase3-isolation-infra-design.md)

## 목적
- Leader 작업을 workspace·컨테이너로 **격리**(D3)하고, Maintainer가 tmux로 다수
  Leader 세션을 관리(ADR-0001/0003)하는 실행 substrate를 제공한다.
- 세션 안에서 실행되는 명령은 **placeholder**(실제 agent runner는 Phase 5 seam).
- 대상 런타임: **Linux/WSL2**(tmux/cron/Docker 네이티브).

## 구성 (모듈 = Phase 3 구성요소)
| 모듈 | 책임 |
|---|---|
| `naming.py` | SoT 식별자 규칙(`w<n>.t<n>-<slug>`) 파싱·검증·렌더 |
| `proc.py` | subprocess 공통 래퍼(argv 실행·캡처·`ProcError`) |
| `config.py` | `.axdt/`·`workspaces/` 경로, 포트 파생, 전송 선택 |
| `hub.py` | 로컬 bare 허브(권위 상태) init/serve, clone URL(호스트/컨테이너) |
| `workspace.py` | 허브 clone 기반 격리 작업본 provision/teardown |
| `container.py` | Docker 생애주기(run_args·정확명 조회·stop/rm·image) |
| `tmux.py` | 세션/윈도우(@id 타깃)·send_text·pipe-pane 증분 캡처 |
| `cron.py` | Watcher crontab 멱등 등록/해제(flock overlap 방지) |
| `backend.py` | `axdt.agent_runner.backend.SessionBackend`(정본, 7메서드: start/send_text/read_new_output/is_alive/exit_code/last_error/stop) 단일 계약을 import·구현하는 `TmuxDockerBackend` |
| `leader.py` | up/down 합성(provision+컨테이너+tmux) |
| `docker/` | `leader.Dockerfile` + `leader-placeholder.sh` |

CLI 진입점은 패키지 루트 [`axdt/cli.py`](../cli.py) (`axdt <domain> <verb>`).

## 네이밍 규칙 (SoT)
단일 식별자 `w<n>.t<n>-<slug>`(선행 0 금지, 점 구분, 슬래시 금지)가
**branch·workspace dir·container를 모두** 구동한다.
- branch = `w3.t12-auth-login`
- workspace dir = `workspaces/w3.t12-auth-login`
- container = `axdt-w3.t12-auth-login`
- tmux 윈도우 = `w3.t12-auth-login` (단, 타깃은 생성 시 캡처한 `@window-id`)

## 런타임 산출물 (gitignore)
```
.axdt/hub/project.git   # bare 통합 허브 (권위 상태 — 재생성 금지)
.axdt/capture/<id>.log  # tmux 캡처 로그 (파생, start 시 truncate)
workspaces/<id>/        # Leader별 격리 클론 (컨테이너 RW 마운트 유일 경로)
```

## 테스트
```bash
# 단위(기본): 외부 도구 불필요, proc 모킹
py -m pytest          # WIP/ 에서

# 통합(WSL2 옵트인): 실 docker/tmux/git daemon
py -m pytest -m integration
```
> Windows에서는 `python`이 MS Store 스텁으로 잡힐 수 있어 **`py`** 런처 사용.
