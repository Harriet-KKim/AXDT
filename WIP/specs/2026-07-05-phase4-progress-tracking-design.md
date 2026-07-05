# Phase 4 — 진척 추적 모델(Progress / Report) 설계

> 상태: **초안 (브레인스토밍 합의, 1차 다중 리뷰 Codex+Fable 반영) · 2차 리뷰 대기** · 작성일 2026-07-05 · 범위: Phase 4 (WIP/TODO.md)
> 산출 깊이: **문서 + 검증/헬퍼 도구** — progress 엄격 스키마·통제 status 어휘를 확정하고, 그 위에 파싱·검증(lint)·복원(recover)·마일스톤 커밋(commit) 도구를 Python으로 구현한다. 승격 *판단*은 도구가 하지 않고 Maintainer 게이트로 남긴다.
> 관련 결정: D2(통신), D7(progress 엄격 스키마 MD 테이블), D10(progress 마일스톤 커밋), D12(AXDT 자체 코드는 `WIP/`)
> 관련 ADR: `WIP/adr/0001`(상시 tmux Maintainer), `0002`(무 DB/큐, 파일 기반 상태), `0003`(tmux 하향·report 상향), `0004`(report→progress 권위 흐름), `0007`(계층 강제, D15)
> 관련 규칙: `docs/sot/rule/progress-single-writer.md`, `report-to-progress-authority.md`, `protected-paths.md`, `leader-coordination-via-maintainer.md`, `propagation.md`, `branch-workspace-naming.md`
> 교차-Phase 계약: Phase 1(progress 빈 양식·report 템플릿이 본 스키마에 정합), Phase 2(Maintainer→Leader 주입 규약·report 파일 포맷), Phase 3(허브 git 배선·send-keys substrate), Phase 7(web이 recover 출력을 read-time 렌더)

---

## 1. 목표와 비목표

### 목표
- progress의 **엄격 스키마**(고정 컬럼 MD 테이블 + 통제 status 어휘, D7)를 확정한다 — `report.status`(Leader 주장)와 `progress.status`(Maintainer 수용)의 값 집합, **허용 전이**, 둘 사이 **정합 매트릭스**를 포함한다.
- 그 스키마 위에서 동작하는 도구를 Python으로 구현한다: 테이블·report 파싱, 검증(lint), 상태 복원(recover), 마일스톤 커밋 헬퍼(commit).
- **report→progress 승격**(ADR-0004)과 **크래시/컨텍스트 압축 후 복원**을 Maintainer가 따르는 절차로 정의하고, 도구가 그 절차의 정합성·기록·복원을 보조하게 한다.
- **progress 마일스톤 커밋 정책**(D10)을 확정하고 커밋 헬퍼로 배선한다.

### 비목표 (이 Phase에서 하지 않음)
- **통신 채널·주입 규약**(Maintainer→Leader 작업 지시·반려 전달의 send-keys 메시지 포맷) → Phase 2. 본 Phase는 그 통신을 **유발·기록하는 상태**(배정=`todo`, 반려=`rejected`)만 정의하고, 전달 행위는 phase3 send-keys substrate + Phase 2 규약에 위임한다.
- **작업 배정 로직**(wave/task 분해·Leader 배치) → Phase 8 오케스트레이션 / Maintainer 역할(Phase 2). 본 Phase는 배정 결과를 progress에 등록·추적만 한다.
- **report 파일의 섹션·본문 구조·라이프사이클**(템플릿 구조) → Phase 1/2. 단 report **frontmatter의 두 키 `id`·`status`는 본 Phase의 계약**이다(§5·§9) — 도구가 이를 파싱하므로. 본문 구조는 손대지 않는다.
- **lint를 허브 게이트에 얹어 강제하는 배선** → D15/`ADR-0007` 하드닝. 본 Phase의 lint는 **권고 + 게이트에 꽂을 수 있는 검사 코드**로 제공한다(§2.5).
- **web 브리핑 렌더** → Phase 7. 본 Phase는 web이 소비할 **복원 출력(recover)**만 제공한다(ADR-0002: read-time 렌더).
- 대상 환경: 도구는 순수 Python(파일·git). phase3와 동일하게 Linux/WSL2 우선.

---

## 2. 핵심 설계 결정

### 2.1 상태 어휘와 허용 전이 (report/progress)
통제 status 어휘를 여기서 확정한다(규칙들이 "D7 스키마에서 정의"로 미뤄둔 부분).

**`report.status`** — Leader 자기보고(주장값). Leader만 자기 report에 쓴다.

| 값 | 뜻 |
|---|---|
| `todo` | 배정됨, 미착수 |
| `in-progress` | 작업 중 |
| `blocked` | 막힘(의존·외부 대기) — 블로커는 Maintainer 경유(`leader-coordination-via-maintainer`) |
| `done` | Leader가 완료 **주장** |
| `needs-spec` | SoT 변경 필요로 진행 불가(사양 변경 요청) |

**`progress.status`** — Maintainer가 수용한 진실. Maintainer 단독이 쓴다(`progress-single-writer`). 시스템·web·복원은 항상 이 값을 권위로 읽는다.

| 값 | 뜻 | 진입 계기 |
|---|---|---|
| `todo` | 등록, 미착수 | Maintainer가 task 등록 |
| `in-progress` | 진행 중으로 수용 | report `in-progress` 관측 |
| `blocked` | 막힘으로 수용(+의존 조율). **외부 의존 대기**(다른 task·SoT 게이트·외부 시스템) | report `blocked`/`needs-spec` 수용 |
| `in-review` | report=done, **수용/검토 대기(정상 대기)**. Maintainer 수용 판단 중(사용자 게이트 포함) | report `done` 관측 |
| `accepted` | Maintainer 수용 완료(성공 종료) | 검토·게이트 통과 |
| `rejected` | 검토 반려 → Leader에 되돌림 | 검토 실패 |
| `paused` | **사용자가 의도적으로 보류**(진행 가능하나 결정으로 멈춤) — 외부 의존 대기가 아님 | 사용자 결정 지점 |
| `superseded` | 재계획으로 폐기·대체 | task 취소·재정의 |

> **`blocked` vs `paused` 경계:** `blocked`는 **외부 의존이 풀려야** 진행 가능(SoT 변경 대기 = `blocked`). `paused`는 **진행 가능하지만 사용자가 멈춘** 것. 겹치지 않는다.

**허용 전이 (`progress.status`, Maintainer가 편집):**

| from | 허용 to |
|---|---|
| `todo` | `in-progress`, `blocked`, `paused`, `superseded` |
| `in-progress` | `in-review`, `accepted`, `blocked`, `paused`, `superseded` |
| `blocked` | `in-progress`, `paused`, `superseded` |
| `in-review` | `accepted`, `rejected`, `in-progress`, `paused`, `superseded` |
| `rejected` | `in-progress`, `superseded` |
| `paused` | `todo`, `in-progress`, `blocked`, `superseded` |
| `accepted` | *(종료 — 전이 없음)* |
| `superseded` | *(종료 — 전이 없음)* |

**불변식:**
- progress가 항상 권위. `report=done & progress=in-review`는 모순이 아니라 **정상(수용 대기)**(ADR-0004).
- **`in-review`는 비필수 경유**: Maintainer는 `in-progress→accepted`로 직행할 수 있다. `in-review`는 "report=done을 관측했으나 아직 수용 안 한" 상태다.
- 종료 상태 = `accepted` / `superseded`, **재열림 없음**. 수용 후 회귀가 발견되면 **신규 task**로 등록한다.
- `rejected` 후 Leader가 report를 `in-progress`로 되돌리면, Maintainer는 progress도 `in-progress`로 되돌린다(재순환).
- Maintainer 수용 어휘(`in-review`·`accepted`·`rejected`·`paused`·`superseded`)는 **report에 나타나지 않는다**. Leader는 `done`까지만 주장한다(§4가 lint로 강제).
- 전이 표는 **Maintainer 편집의 규범**이다. progress 단일 스냅샷에는 이력이 없어 lint가 전이 위반을 검사하지 못한다(정적 pair 불변식만 검사, §4). 전이 이력은 git(마일스톤 커밋)으로 남는다.

### 2.2 progress 엄격 스키마 (MD 테이블, D7)
한 행 = 한 task. 고정 컬럼(순서 고정):

| 컬럼 | 내용 |
|---|---|
| `wave` | `w<n>` — 소속 wave. **task id의 wave 접두와 일치해야 함**(§4) |
| `task` | `w<n>.t<n>-<slug>` — task id(`branch-workspace-naming`; phase3 `naming.py`로 형식 검증) |
| `status` | `progress.status`(통제 어휘) |
| `leader` | 담당 Leader 식별자(형식 자유) |
| `report` | report 파일 경로 `report/<task>.md`, 없으면 `—` |
| `updated` | 최종 갱신(ISO date `YYYY-MM-DD`) |

**wave 롤업 — 전량 사상(total mapping).** task 행이 **유일한 권위**다. wave 단위 상태는 저장하지 않고 도구(recover·web)가 소속 task들의 `progress.status`에서 **파생 계산**한다(저장 시 드리프트 방지). 출력은 progress 어휘가 아니라 **전용 어휘** `WAVE_ROLLUP_STATUSES = {empty, todo, in-progress, in-review, blocked, paused, done, superseded}`이며, 규칙은 다음 우선순위의 전량 함수다(위에서부터 첫 매치):

1. task 없음 → `empty`
2. 하나라도 `blocked` → `blocked`
3. 하나라도 `paused` → `paused`
4. 전부 종료(`accepted`∪`superseded`) → `accepted` 하나라도 있으면 `done`, **전부 `superseded`면 `superseded`**(취소된 wave, 완료 아님)
5. 전부 `todo` → `todo`
6. 활성(`todo`·`in-progress`·`rejected`) 없이 `in-review`만 남음(+종료 혼재) → `in-review`
7. 그 외(활성 잔존) → `in-progress`

### 2.3 도구 모듈 (`WIP/axdt/progress/`)
각 모듈은 하나의 명확한 책임을 가지며 `schema`를 단일 정의원으로 참조한다. phase3와 동일하게 TDD로 만든다.

| 모듈 | 책임 | 성격 |
|---|---|---|
| `schema.py` | 컬럼·통제 어휘·종료 상태·허용 전이·정합 매트릭스·wave 롤업 규칙. 모든 모듈이 여기서 읽는다 | 순수(IO 없음) |
| `table.py` | progress MD 테이블 ↔ 구조화 객체 파싱/직렬화, report frontmatter 파싱. lint·recover 공용 | IO-light |
| `lint.py` | 검증: 스키마 적합·참조 무결성(양방향)·report↔progress 정합 매트릭스(§4). 결과는 findings 목록 | 읽기 전용 |
| `recover.py` | 복원: progress(권위)+report 포인터 → 구조화 상태 + 수용 대기·재작업·블로커 목록(§6.2). web도 이걸 렌더 | 읽기 전용 |
| `commit.py` | 마일스톤 커밋 헬퍼(D10, §6.3) — 스테이징 + lint(ERROR 시 거부) + 메시지 규약 | 쓰기(git) |

### 2.4 절차의 Phase 4 소관 경계
승격·반려·복원 절차에서 **Phase 4가 소유하는 것은 상태 전이와 도구뿐**이다. *통신 행위*(Leader에게 지시·반려 전달)는 본 Phase 밖이다.

- **승격/반려** = progress 상태 전이(§2.1) + 도구(lint/commit). Maintainer의 **수용 판단** 자체는 도구가 대신하지 않는다(ADR-0004의 게이트 지점).
- **지시 전달**(작업 배정·반려 통보) = phase3 **tmux send-keys** substrate + Phase 2 **주입 규약**. Phase 4는 그 전달을 유발하는 상태만 기록한다.
- **반려 사유의 durable 기록** = 두 갈래로 남긴다: (a) Leader의 **다음 report 이터레이션**에 "받은 피드백·조치" 반영(report는 Leader 소유), (b) `rejected` 전이의 **마일스톤 커밋 메시지에 사유 요약**(§6.3) — send-keys 휘발성·크래시 소실창 완화(ADR-0002 "git 이력=변경 이력"). Maintainer 반려 근거 자체의 형식화(별도 산출물)는 Phase 2 사안.

### 2.5 강제 경계 — "도구 사용"이 아니라 "결과물 유효성", 그리고 게이트는 아직 미배선
도구를 Maintainer가 실제로 돌렸는지는 강제하지 않으며, 원리상 강제할 수 없다. ADR-0007: 강제는 컨테이너가 접근 못 하는 호스트/허브 층 검사에서만 성립하는데, **Maintainer는 그 층에 상주하는 신뢰 루트**라 감시할 상위 주체가 없다. 강제되는 것은 결과물이며, **그 강제 지점(허브 게이트)은 현재 미구현**이다.

- **현재 사실(중요):** phase3 브랜치의 허브(`WIP/axdt/infra/hub.py`)는 `git daemon --enable=receive-pack`로 **무인증 노출**만 하고 **서버사이드 게이트·훅이 없다**. phase3 스펙 §2.2는 파일시스템 격리만 강제하고 보호 경로 diff 검사(pre-receive)를 **하드닝으로 연기**한다. TODO Phase 3의 "허브 서버사이드 게이트" 항목은 미완, `ADR-0007`은 `status: proposed`다.
- 따라서 **"Leader는 progress를 못 쓴다"는 지금 문서 규범 + 로컬 pre-commit 훅(권고, 우회 가능) 수준**이다. `protected-paths`가 `progress.md`를 Maintainer 단독으로 규정하지만, 이를 실제로 거부하는 **허브 경로 게이트가 배선될 때 비로소 강제**된다(D15/ADR-0007 하드닝, TODO Phase 3 잔여).
- **Phase 4의 역할:** `lint`를 그 게이트에 **꽂을 수 있는 검사 코드**로 만든다(손 편집이든 도구든 스키마·정합 위반이면 걸리도록). 게이트 부재기에는 lint가 **권고**로 동작한다(commit.py가 커밋 전 실행; Maintainer/CI가 호출). 즉 Phase 4는 새 강제 장치를 만들지 않고 **검사를 제공**하며, 강제는 하드닝에 위임한다. phase3 §51과 동일한 태도.

### 2.6 상태 저장 = interim 파일 (ADR-0002)
별도 DB·큐·이벤트 로그를 두지 않는다. progress·report 파일이 유일한 상태 매체이며, progress의 git 이력(마일스톤 커밋, D10)이 변경 이력 역할을 한다. 복원은 파일 재파싱으로 재구성한다(§6.2).

---

## 3. progress 테이블 포맷

파일은 상단에 규범 문단(단일 작성자·스키마 참조)을 두고, **테이블은 파일 내 유일한 MD 테이블**이다(§5 파싱 규약). 빈 양식(Phase 4가 setup하는 정본):

```markdown
| wave | task | status | leader | report | updated |
|---|---|---|---|---|---|
```

행이 있는 예:

```markdown
| wave | task | status | leader | report | updated |
|---|---|---|---|---|---|
| w1 | w1.t1-hub-init | accepted | L-alice | report/w1.t1-hub-init.md | 2026-07-05 |
| w1 | w1.t2-cli-scaffold | in-review | L-bob | report/w1.t2-cli-scaffold.md | 2026-07-05 |
| w2 | w2.t1-auth-login | blocked | L-carol | report/w2.t1-auth-login.md | 2026-07-05 |
```

- 헤더 행·구분 행 고정. 컬럼 순서·이름 고정(lint가 검사).
- `report` 경로는 **progress.md 기준 상대경로 `report/<task>.md`**. progress.md가 `docs/interim/progress.md`이므로 canonical 대상은 `docs/interim/report/<task>.md`다(§4가 정규화·검증). task에 report가 아직 없으면 `—`.

---

## 4. 정합 규칙 (lint가 검사하는 것)

lint는 findings를 **ERROR**(불가 — 게이트가 거부해야 할 위반)와 **WARN**(정상 대기·미반영 등 정보)으로 분류한다. **한 셀이 여러 규칙에 걸리면 ERROR가 WARN보다 우선**한다.

### 4.1 구조·형식 (ERROR)
- 컬럼 누락·순서 위반·헤더/구분행 불일치.
- 파일에 MD 테이블이 2개 이상(진척 테이블 식별 불가).
- `status` 값이 `PROGRESS_STATUSES` 밖.
- `task` id 형식 위반(`branch-workspace-naming`, phase3 `naming.py` 재사용).
- `wave` 컬럼이 `task`의 wave 접두와 불일치(예: `w1` 행에 `w2.t3-…`).
- `task` id 중복(한 task = 한 행).
- `updated`가 `YYYY-MM-DD` 형식 아님.
- (`leader` 형식은 자유 — 검사 안 함.)

### 4.2 참조 무결성 (양방향)
- **ERROR** `report`가 `—`가 아닌데 파일 없음 / 경로가 canonical(`docs/interim/report/<task>.md`) 아님(절대경로·`..`·task와 다른 filename 거부).
- **ERROR** report frontmatter `id` ≠ 행의 `task`.
- **ERROR** report frontmatter `status` 누락 또는 `REPORT_STATUSES` 밖(§2.1 불변식 "수용 어휘가 report에 안 나타남"을 여기서 강제).
- **WARN** `report_dir`에 있으나 progress에 대응 행이 없는 **고아 report**(배정 누락·task id 오타 탐지).

### 4.3 상태 정합 매트릭스 (`pair_severity(report | None, progress)`)
행 = `report.status`(또는 `—`=파일 부재), 열 = `progress.status`. `·`=정상(None) · `W`=WARN · `E`=ERROR.

| report \ progress | todo | in-prog | blocked | in-review | accepted | rejected | paused | superseded |
|---|---|---|---|---|---|---|---|---|
| `todo` | · | · | · | W | **E** | · | · | · |
| `in-progress` | · | · | · | W | **E** | · | · | · |
| `blocked` | W | W | · | W | **E** | W | · | · |
| `done` | W | W | W | · | · | W | W | · |
| `needs-spec` | W | W | · | W | **E** | W | · | · |
| `—`(부재) | · | W | W | W | **E** | W | W | · |

핵심 근거:
- **`accepted` 열은 `report=done`이 아니면 전부 ERROR** — 수용은 Leader의 done 주장을 전제한다. `report=—`(주장 자체가 없음)+`accepted`가 가장 심한 권위 우회이므로 ERROR(1차 리뷰 Blocker 해소).
- **`in-review` 열의 report≠done은 WARN**(ERROR 아님) — in-review는 관측·가역 상태다. Maintainer가 올린 직후 Leader가 done을 회수(→in-progress)하는 것은 정상 재순환이므로, 이 일시 상태가 무관 task의 마일스톤 커밋까지 막지 않게 WARN으로 둔다(1차 리뷰 Major 해소).
- **`done` 행의 `todo/in-progress/blocked/rejected/paused`는 WARN**(승격/재승격 대기) — `rejected`+`done`은 반려 후 재작업 완료를 다시 주장한 "재승격 대기". `paused`+`done`은 in-review로 가야 함.
- **`blocked`·`needs-spec` 행의 미수용은 WARN**(블로커/사양 수용 대기) — done 승격 대기와 대칭. `needs-spec`의 정본 대응은 `blocked`(또는 `paused`), 재계획 종료 `superseded`는 정상(·).
- **`—`(부재) 행**: 진행 상태인데 자기보고가 없으면 WARN. `todo`·`superseded`는 정상(등록만/취소).

---

## 5. 도구 모듈 계약

```python
# schema.py (순수)
REPORT_STATUSES: frozenset[str]        # {todo, in-progress, blocked, done, needs-spec}
PROGRESS_STATUSES: frozenset[str]      # {todo, in-progress, blocked, in-review, accepted, rejected, paused, superseded}
WAVE_ROLLUP_STATUSES: frozenset[str]   # {empty, todo, in-progress, in-review, blocked, paused, done, superseded}
COLUMNS: tuple[str, ...]               # ('wave','task','status','leader','report','updated')
TERMINAL: frozenset[str]               # {accepted, superseded}
ALLOWED_TRANSITIONS: dict[str, frozenset[str]]           # §2.1 전이 표(Maintainer 규범)
def pair_severity(report: str | None, progress: str) -> str | None   # 'ERROR'|'WARN'|None (report=None=부재)
def wave_rollup(task_statuses: list[str]) -> str          # §2.2 전량 사상, 반환 ∈ WAVE_ROLLUP_STATUSES

# table.py
@dataclass
class TaskRow: wave: str; task: str; status: str; leader: str; report: str; updated: str
@dataclass
class Report: id: str; status: str
def parse_progress(text: str) -> list[TaskRow]            # 파일 내 유일 테이블을 파싱, 2개↑면 오류
def render_progress(rows: list[TaskRow]) -> str           # 테이블 영역만 생성(라운드트립 안정); 문서 프로즈 보존은 호출측 책임
def parse_report(text: str) -> Report                     # frontmatter에서 id·status. 키 누락 시 예외(lint가 ERROR로 변환)

# lint.py
@dataclass
class Finding: severity: str; code: str; task: str | None; message: str
def lint(progress_path: Path, report_dir: Path) -> list[Finding]
    # report 컬럼은 progress.md 디렉터리 기준으로 해석하고 canonical == report_dir/<task>.md 인지 검증.
    # report_dir 전체를 스캔해 고아 report(§4.2) 탐지.

# recover.py
@dataclass
class State:
    tasks: list[...]                    # (task, progress.status, report.status|None, updated)
    pending_acceptance: list[...]       # report=done ∧ progress ∈ {todo, in-progress, blocked, in-review}
    in_rework: list[...]                # progress=rejected
    blocked_or_paused: list[...]        # progress ∈ {blocked, paused}
    wave_rollup: dict[str, str]         # wave → WAVE_ROLLUP_STATUSES
def reconstruct(progress_path: Path, report_dir: Path) -> State
def format_summary(state: State) -> str                   # Maintainer·web용 텍스트

# commit.py
def milestone_commit(repo: Path, message: str, extra_paths: list[Path] = ()) -> None
    # progress.md(+관련 report) 스테이징 → lint(파일 전역에 ERROR 있으면 거부) → commit.
    # 허브 push는 하지 않는다(phase3/Phase 6 허브 배선 소관, §6.3).
```

경로(progress.md·report 디렉터리·repo 루트)는 phase3 `config.py`에서 얻는다. 도구는 `docs/interim/` 파일과 git만 다루며 컨테이너·tmux를 알지 못한다(결합 최소).

---

## 6. 절차

### 6.1 승격 흐름 (report→progress)
1. Maintainer가 report 변경을 관측(주기 확인 또는 신호).
2. `axdt progress lint`로 정합성 확인(ERROR 없어야 함).
3. report 내용을 **검토·수용 판단**(필요 시 Reviewer/Tester/사용자 게이트, wave 롤업 고려) — 도구가 대신하지 않는다.
4. 수용: progress 행 `status` 갱신 + `updated`. `in-review`를 경유하거나 `in-progress→accepted` 직행 모두 허용(§2.1). Maintainer만 편집.
5. 반려: progress `rejected` 기록. 전달은 send-keys(Phase 2/phase3). Leader가 report를 `in-progress`로 되돌리면 Maintainer도 progress를 `in-progress`로 되돌려 재순환(§2.1 전이).

### 6.2 복원 절차 (크래시·컨텍스트 압축 후)
1. Maintainer 재시작 → `axdt progress status`(recover) 실행.
2. 도구가 progress(권위)+report를 재구성해 **명시적 집합**으로 분류(§5 `State`): 수용 대기(`report=done ∧ progress ∈ {todo, in-progress, blocked, in-review}`), 재작업 중(`progress=rejected`), 블로커/보류(`progress ∈ {blocked, paused}`), wave 롤업. (부등호 순서 비교 없음.)
3. Maintainer가 "어디까지 수용됐고 무엇이 대기·재작업인지" 즉시 복원해 이어간다.
4. progress git 이력(마일스톤 커밋)이 시점 스냅샷을 제공한다(ADR-0002).

### 6.3 마일스톤 커밋 정책 (D10)
- **무엇**: `progress.md` + 그 전이에 관련된 report 파일을 함께 커밋.
- **언제**: 의미 있는 전이 — 최소 (a) task `accepted`, (b) `rejected`, (c) wave 완료(전 task 종료), (d) 사용자 게이트 통과. 자잘한 `in-progress` 갱신마다가 아니라 **마일스톤 단위**.
- **누가**: Maintainer(호스트 상시 세션, ADR-0001). `commit.py`가 스테이징 + lint(파일 전역 ERROR 시 거부) + 메시지 규약을 적용.
- **메시지 규약**: `chore(progress): <event>` 파싱 가능 형태. `rejected`는 **사유 요약을 포함**: `chore(progress): w1.t1 rejected — <사유>`. 예 `chore(progress): w1.t1 accepted`, `chore(progress): w1 완료`.
- **어디에**: progress가 사는 repo(대상 프로젝트, 도그푸딩 시 AXDT)의 기본 작업본에서. task 브랜치가 아니다. **허브 push는 이 도구의 책임이 아니다**(phase3 허브 배선/Phase 6 소관).

---

## 7. CLI (phase3 `cli.py` 확장)
- `axdt progress lint` — 정합 검사, findings 출력. ERROR 있으면 비정상 종료코드.
- `axdt progress status` — recover 요약(수용 대기·재작업·블로커·wave 롤업).
- `axdt progress commit -m "<message>"` — 마일스톤 커밋(lint 통과 시).

---

## 8. 테스트 전략 (TDD)
- pytest, 모듈별. phase3 `WIP/axdt/test/` 옆에 progress 테스트 추가.
- 픽스처: 유효/무효 progress 테이블, 다양한 report frontmatter(정상·id 불일치·status 누락·비통제 값).
- 커버: **정합 매트릭스 §4.3 전 셀**(report 6상태 × progress 8상태), 구조·형식 검사(§4.1), 참조 무결성 양방향(§4.2 고아 report 포함), `wave_rollup` 전량 사상(빈 wave·all-superseded·혼재·우선순위), 파싱 라운드트립, recover 집합 분류(수용 대기·재작업), commit이 파일 전역 ERROR에서 거부.

---

## 9. 교차-Phase 인터페이스

| 대상 | 계약 |
|---|---|
| **Phase 1** | `report/_TEMPLATE.md`가 **frontmatter 최소 계약** `id`(=task id)·`status`(∈`REPORT_STATUSES`)를 갖도록 한다(§5 `parse_report` 전제). `progress.md` 빈 양식은 Phase 4가 setup한다(§10 ②). 병렬 Phase 1 세션과 파일 경계를 맞춘다 |
| **Phase 2** | Maintainer→Leader **주입 규약**(작업 지시·반려 전달)과 report 파일 섹션·본문 구조. Phase 4는 상태 어휘·frontmatter 두 키·정합만 |
| **Phase 3** | 허브 git 배선(commit.py가 phase3 config·git 사용), send-keys substrate(통신 채널), **허브 경로 게이트**(미구현 — 여기에 lint를 얹으면 강제, §2.5). progress/report 허브 push 배선 |
| **Phase 7** | web 브리핑이 `recover.reconstruct` 출력(+`wave_rollup`)을 read-time 렌더(ADR-0002). 별도 상태원 없음 |

---

## 10. 결정 지점

**① 스키마의 권위 정의 위치 — WIP/specs + 코드(단일 정의원) + 템플릿.**
상태 어휘·스키마의 권위 정의를 본 스펙(WIP/specs, AXDT 자체 설계 D12) + `schema.py`(**단일 정의원**) + 템플릿 헤더에 둔다. 새 SoT 문서를 만들지 않으므로 사용자 게이트 PR이 불필요하다(규범 규칙 3종은 이미 SoT에 있다).
- **트레이드오프(명시):** `progress-single-writer`·`report-to-progress-authority`가 "통제 status 어휘는 D7 스키마에서 정의"로 위임하는데, 그 정의처가 WIP+코드면 **어휘 변경이 사용자 게이트 없이 Maintainer 단독으로 가능**하다(WIP는 보호 경로지만 게이트 PR 대상은 아님). 어휘를 SoT 수준으로 통제·전파하려면 별도 사용자 게이트 PR로 규칙 각주를 확정해야 하며, 현재는 하지 않는다.
- **대상 프로젝트에서의 도구 위치(open):** `schema.py`+템플릿은 clone과 함께 전파되지만, `WIP/axdt`는 D12상 AXDT 자체 코드다. 도그푸딩이 아닌 대상 프로젝트에서 진척 도구가 어디에 실릴지는 후속 결정(현재 범위 밖).

**② Phase 1 경계 — 스키마·progress 빈 양식은 Phase 4, report 템플릿은 Phase 1.**
"progress 빈 양식·report 템플릿"은 TODO상 Phase 1 항목이나 스키마는 본 Phase가 확정한다(의존 역전). 경계: **Phase 4가 스키마 + `docs/interim/progress.md` 정본 빈 양식을 Maintainer 1회성 setup으로 반영**하고(현재 placeholder를 대체), `report/_TEMPLATE.md`는 Phase 1 소관으로 두되 **frontmatter 두 키 계약(§9)을 전달**한다. 같은 파일 동시 편집을 막기 위해 실제 착수 시 Phase 1 세션과 맞춘다. (현재 `docs/interim/progress.md` placeholder와 그 "Phase 1이 빈 양식" 문구도 이 결정에 맞춰 갱신한다.)

**③ 반려 사유의 durable 기록 — report + 커밋 메시지 이중.**
send-keys는 휘발이므로 반려 사유를 (a) Leader 다음 report, (b) `rejected` 마일스톤 커밋 메시지 요약(§6.3) 두 곳에 남긴다(§2.4). 반려 근거의 별도 형식화(산출물)는 Phase 2 통신 프로토콜 사안으로 넘긴다.
