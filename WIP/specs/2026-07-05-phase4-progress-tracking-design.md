# Phase 4 — 진척 추적 모델(Progress / Report) 설계

> 상태: **초안 (브레인스토밍 합의, 다중 모델 리뷰 대기)** · 작성일 2026-07-05 · 범위: Phase 4 (WIP/TODO.md)
> 산출 깊이: **문서 + 검증/헬퍼 도구** — progress 엄격 스키마·통제 status 어휘를 확정하고, 그 위에 파싱·검증(lint)·복원(recover)·마일스톤 커밋(commit) 도구를 Python으로 구현한다. 승격 *판단*은 도구가 하지 않고 Maintainer 게이트로 남긴다.
> 관련 결정: D2(통신), D7(progress 엄격 스키마 MD 테이블), D10(progress 마일스톤 커밋), D12(AXDT 자체 코드는 `WIP/`)
> 관련 ADR: `WIP/adr/0001`(상시 tmux Maintainer), `0002`(무 DB/큐, 파일 기반 상태), `0003`(tmux 하향·report 상향), `0004`(report→progress 권위 흐름), `0007`(계층 강제, D15)
> 관련 규칙: `docs/sot/rule/progress-single-writer.md`, `report-to-progress-authority.md`, `protected-paths.md`, `leader-coordination-via-maintainer.md`, `propagation.md`, `branch-workspace-naming.md`
> 교차-Phase 계약: Phase 1(progress 빈 양식·report 템플릿이 본 스키마에 정합), Phase 2(Maintainer→Leader 주입 규약·report 파일 포맷), Phase 3(허브 git 배선·send-keys substrate), Phase 7(web이 recover 출력을 read-time 렌더)

---

## 1. 목표와 비목표

### 목표
- progress의 **엄격 스키마**(고정 컬럼 MD 테이블 + 통제 status 어휘, D7)를 확정한다 — `report.status`(Leader 주장)와 `progress.status`(Maintainer 수용)의 값 집합과 둘 사이 **정합 규칙**을 포함한다.
- 그 스키마 위에서 동작하는 도구를 Python으로 구현한다: 테이블·report 파싱, 검증(lint), 상태 복원(recover), 마일스톤 커밋 헬퍼(commit).
- **report→progress 승격**(ADR-0004)과 **크래시/컨텍스트 압축 후 복원**을 Maintainer가 따르는 절차로 정의하고, 도구가 그 절차의 정합성·기록·복원을 보조하게 한다.
- **progress 마일스톤 커밋 정책**(D10)을 확정하고 커밋 헬퍼로 배선한다.

### 비목표 (이 Phase에서 하지 않음)
- **통신 채널·주입 규약**(Maintainer→Leader 작업 지시·반려 전달의 send-keys 메시지 포맷) → Phase 2. 본 Phase는 그 통신을 **유발·기록하는 상태**(배정=`todo`, 반려=`rejected`)만 정의하고, 전달 행위는 phase3 send-keys substrate + Phase 2 규약에 위임한다.
- **작업 배정 로직**(wave/task 분해·Leader 배치) → Phase 8 오케스트레이션 / Maintainer 역할(Phase 2). 본 Phase는 배정 결과를 progress에 등록·추적만 한다.
- **report 파일의 상세 포맷·섹션·라이프사이클**(템플릿 구조) → Phase 1/2. 본 Phase는 report의 **`status` 어휘와 progress와의 정합**만 규정한다(파일 구조는 손대지 않는다).
- **lint를 허브 게이트에 얹어 강제하는 배선** → D15/`ADR-0007` 하드닝. 본 Phase의 lint는 **권고 + 게이트에 꽂을 수 있는 검사 코드**로 제공한다(§2.5).
- **web 브리핑 렌더** → Phase 7. 본 Phase는 web이 소비할 **복원 출력(recover)**만 제공한다(ADR-0002: read-time 렌더).
- 대상 환경: 도구는 순수 Python(파일·git). phase3와 동일하게 Linux/WSL2 우선.

---

## 2. 핵심 설계 결정

### 2.1 상태 어휘와 전이 (report/progress)
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
| `blocked` | 막힘으로 수용(+의존 조율) | report `blocked` 수용 |
| `in-review` | report=done, **수용/검토 대기(정상 대기)** | report `done` 관측 |
| `accepted` | Maintainer 수용 완료(성공 종료) | 검토·게이트 통과 |
| `rejected` | 검토 반려 → Leader에 되돌림 | 검토 실패 |
| `paused` | 사용자 결정·의존 대기로 보류 | 결정 지점/게이트 |
| `superseded` | 재계획으로 폐기·대체 | task 취소·재정의 |

**불변식:**
- progress가 항상 권위. `report=done & progress=in-review`는 모순이 아니라 **정상(수용 대기)**(ADR-0004).
- 종료 상태 = `accepted` / `superseded`. `rejected`는 Leader가 report를 다시 `in-progress`로 돌려 재순환한다.
- Maintainer 수용 어휘(`in-review`·`accepted`·`rejected`·`paused`·`superseded`)는 **report에 나타나지 않는다**. Leader는 `done`까지만 주장한다.

### 2.2 progress 엄격 스키마 (MD 테이블, D7)
한 행 = 한 task. 고정 컬럼(순서 고정):

| 컬럼 | 내용 |
|---|---|
| `wave` | `w<n>` — 소속 wave(그룹 키) |
| `task` | `w<n>.t<n>-<slug>` — task id(`branch-workspace-naming`; report 파일명과 동일) |
| `status` | `progress.status`(통제 어휘) |
| `leader` | 담당 Leader 식별자 |
| `report` | report 파일 상대경로, 없으면 `—` |
| `updated` | 최종 갱신(ISO date `YYYY-MM-DD`) |

**wave 롤업:** task 행이 **유일한 권위**다. wave 단위 상태는 저장하지 않고 도구(recover·web)가 소속 task들에서 **파생 계산**한다. 파생 규칙: 전 task `accepted`(또는 `superseded`) → wave `done`; 하나라도 `blocked`/`paused` → 각 우선; 그 외 하나라도 진행 중 → `in-progress`. 별도 권위 행을 두지 않는 이유는 저장 시 task 행과의 **동기화 드리프트**가 생기기 때문. lint는 파생 규칙과 어긋난 수기 롤업 표기가 있으면 경고한다.

### 2.3 도구 모듈 (`WIP/axdt/progress/`)
각 모듈은 하나의 명확한 책임을 가지며 `schema`를 단일 정의원으로 참조한다. phase3와 동일하게 TDD로 만든다.

| 모듈 | 책임 | 성격 |
|---|---|---|
| `schema.py` | 컬럼 정의·통제 어휘·종료 상태·정합 규칙·wave 롤업 규칙. 모든 모듈이 여기서 읽는다 | 순수(IO 없음) |
| `table.py` | progress MD 테이블 ↔ 구조화 객체 파싱/직렬화, report frontmatter 파싱. lint·recover 공용 | IO-light |
| `lint.py` | 검증: 스키마 적합·참조 무결성·report↔progress 정합(§4). 결과는 findings 목록 | 읽기 전용 |
| `recover.py` | 복원: progress(권위)+report 포인터 → 구조화 상태 + 수용 대기·블로커 목록(§6.2). web도 이걸 렌더 | 읽기 전용 |
| `commit.py` | 마일스톤 커밋 헬퍼(D10, §6.3) — 스테이징 + lint(ERROR 시 거부) + 메시지 규약 | 쓰기(git) |

### 2.4 절차의 Phase 4 소관 경계
승격·반려·복원 절차에서 **Phase 4가 소유하는 것은 상태 전이와 도구뿐**이다. *통신 행위*(Leader에게 지시·반려 전달)는 본 Phase 밖이다.

- **승격/반려** = progress 상태 전이(`in-review`→`accepted`/`rejected`) + 도구(lint/commit). Maintainer의 **수용 판단** 자체는 도구가 대신하지 않는다(ADR-0004의 게이트 지점).
- **지시 전달**(작업 배정·반려 통보) = phase3 **tmux send-keys** substrate + Phase 2 **주입 규약**. Phase 4는 그 전달을 유발하는 상태만 기록한다.
- **반려 사유의 durable 기록** = Leader의 **다음 report 이터레이션**에 "받은 피드백·조치"로 반영한다(report는 Leader 소유라 감사추적이 report 이력에 남는다). Maintainer 반려 근거 자체의 형식화가 필요하면 Phase 2 통신 프로토콜 사안이다.

### 2.5 강제 경계 — "도구 사용"이 아니라 "결과물 유효성"
도구를 Maintainer가 실제로 돌렸는지는 강제하지 않으며, 원리상 강제할 수 없다. ADR-0007: 강제는 컨테이너가 접근 못 하는 호스트/허브 층 검사에서만 성립하는데, **Maintainer는 그 층에 상주하는 신뢰 루트**라 감시할 상위 주체가 없다. 강제되는 것은 결과물이다.

- **"Leader는 progress를 못 쓴다"** — `progress.md`는 보호 경로=Maintainer 단독(`protected-paths`). Leader가 task 브랜치에서 고쳐 push하면 허브 게이트가 **경로 규칙으로 거부**(phase3 baseline). 강제됨.
- **"progress 내용이 유효한가(lint)"** — 본 Phase의 lint는 **게이트에 꽂을 수 있는 검사 코드**로 만든다. 손 편집이든 도구든 스키마·정합 위반이면 걸리도록. 다만 이를 허브 pre-receive에 실제로 얹는 것은 **D15/ADR-0007 하드닝 연기**. 그 전까지 lint는 **권고**(commit.py가 커밋 전 실행; Maintainer/CI가 호출).
- 즉 Phase 4는 새 강제 장치를 만들지 않는다. **검사(lint)를 제공**하고, 강제 지점은 phase3 경로 게이트(있음) + 하드닝(연기)에 위임한다. phase3 §51과 동일한 태도.

### 2.6 상태 저장 = interim 파일 (ADR-0002)
별도 DB·큐·이벤트 로그를 두지 않는다. progress·report 파일이 유일한 상태 매체이며, progress의 git 이력(마일스톤 커밋, D10)이 변경 이력 역할을 한다. 복원은 파일 재파싱으로 재구성한다(§6.2).

---

## 3. progress 테이블 포맷

빈 양식(Phase 1이 채울 정본 예시):

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
- `report` 경로는 progress.md 기준 상대경로. task에 report가 아직 없으면 `—`.
- 파일 상단에는 단일 작성자 규범과 스키마 참조를 주석/문단으로 명시한다(현재 `docs/interim/progress.md` 자리표시가 그 틀).

---

## 4. 정합 규칙 (lint가 검사하는 것)

lint는 findings를 **ERROR**(불가 — 게이트가 거부해야 할 위반)와 **WARN**(정상 대기·미반영 등 정보)으로 분류한다.

**ERROR (불가):**
- `status` 값이 통제 어휘 밖.
- 컬럼 누락·순서 위반·헤더 불일치.
- `task` id 중복(한 task = 한 행).
- `report`가 `—`가 아닌데 파일이 없음 / report frontmatter `id` ≠ 행의 `task`.
- **진실이 주장을 앞섬**: `progress ∈ {in-review, accepted}`인데 `report ≠ done`. (수용은 Leader의 done 주장을 전제로 한다.)

**WARN (대기·미반영):**
- `report=done`인데 `progress ∈ {todo, in-progress, blocked}` → 승격 대기(곧 `in-review`가 되어야 함).
- `report=needs-spec`인데 `progress ∉ {blocked, paused}` → SoT 게이트 대기와 어긋남.
- `report`가 `—`인데 `progress ∉ {todo, superseded}` → 진행 중인데 자기보고 없음.
- 수기 wave 롤업 표기가 파생 규칙과 불일치(§2.2).

`report=done & progress=in-review`는 **정상**이며 finding을 내지 않는다(ADR-0004).

---

## 5. 도구 모듈 계약

```python
# schema.py (순수)
REPORT_STATUSES: frozenset[str]      # {todo, in-progress, blocked, done, needs-spec}
PROGRESS_STATUSES: frozenset[str]    # {todo, in-progress, blocked, in-review, accepted, rejected, paused, superseded}
COLUMNS: tuple[str, ...]             # ('wave','task','status','leader','report','updated')
TERMINAL: frozenset[str]             # {accepted, superseded}
def pair_severity(report: str, progress: str) -> str | None   # 'ERROR' | 'WARN' | None
def wave_rollup(task_statuses: list[str]) -> str

# table.py
@dataclass
class TaskRow: wave: str; task: str; status: str; leader: str; report: str; updated: str
@dataclass
class Report: id: str; status: str
def parse_progress(text: str) -> list[TaskRow]
def render_progress(rows: list[TaskRow]) -> str          # 라운드트립 안정
def parse_report(text: str) -> Report                     # frontmatter에서 id·status

# lint.py
@dataclass
class Finding: severity: str; code: str; task: str | None; message: str
def lint(progress_path: Path, report_dir: Path) -> list[Finding]

# recover.py
@dataclass
class State: tasks: list[...]; pending_acceptance: list[...]; blocked: list[...]; wave_rollup: dict[str, str]
def reconstruct(progress_path: Path, report_dir: Path) -> State
def format_summary(state: State) -> str                   # Maintainer·web용 텍스트

# commit.py
def milestone_commit(repo: Path, message: str, extra_paths: list[Path] = ()) -> None
    # progress.md(+관련 report) 스테이징 → lint(ERROR 있으면 거부) → commit
```

경로(progress.md·report 디렉터리·repo 루트)는 phase3 `config.py`에서 얻는다. 도구는 `docs/interim/` 파일과 git만 다루며 컨테이너·tmux를 알지 못한다(결합 최소).

---

## 6. 절차

### 6.1 승격 흐름 (report→progress)
1. Maintainer가 report 변경을 관측(주기 확인 또는 신호).
2. `axdt progress lint`로 정합성 확인(ERROR 없어야 함).
3. report 내용을 **검토·수용 판단**(필요 시 Reviewer/Tester/사용자 게이트, wave 롤업 고려) — 도구가 대신하지 않는다.
4. 수용: progress 행 `status` 갱신(예 `in-review`→`accepted`) + `updated`. Maintainer만 편집.
5. 반려: progress `rejected` 기록. 반려 전달은 send-keys(Phase 2/phase3), Leader가 report를 `in-progress`로 되돌려 재순환(§2.4).

### 6.2 복원 절차 (크래시·컨텍스트 압축 후)
1. Maintainer 재시작 → `axdt progress status`(recover) 실행.
2. 도구가 progress(권위)+report를 재구성: task별 `(progress.status, report.status, updated)`, **수용 대기 목록**(`report=done & progress<accepted`), **블로커/보류 목록**, wave 롤업 파생.
3. Maintainer가 "어디까지 수용됐고 무엇이 대기인지" 즉시 복원해 이어간다.
4. progress git 이력(마일스톤 커밋)이 시점 스냅샷을 제공한다(ADR-0002).

### 6.3 마일스톤 커밋 정책 (D10)
- **무엇**: `progress.md` + 그 전이에 관련된 report 파일을 함께 커밋.
- **언제**: 의미 있는 전이 — 최소 (a) task `accepted`, (b) wave 완료(전 task 종료), (c) 사용자 게이트 통과. 자잘한 `in-progress` 갱신마다가 아니라 **마일스톤 단위**.
- **누가**: Maintainer(호스트 상시 세션, ADR-0001). `commit.py`가 스테이징 + lint + 메시지 규약을 적용.
- **메시지 규약**: `chore(progress): <event>` 파싱 가능 형태(예 `chore(progress): w1.t1 accepted`, `chore(progress): w1 완료`). git 이력이 곧 변경 이력이 된다(ADR-0002).
- **어디에**: progress가 사는 repo(대상 프로젝트, 도그푸딩 시 AXDT)의 기본 작업본에서. task 브랜치가 아니다.

---

## 7. CLI (phase3 `cli.py` 확장)
- `axdt progress lint` — 정합 검사, findings 출력. ERROR 있으면 비정상 종료코드.
- `axdt progress status` — recover 요약(수용 대기·블로커·wave 롤업).
- `axdt progress commit -m "<message>"` — 마일스톤 커밋(lint 통과 시).

---

## 8. 테스트 전략 (TDD)
- pytest, 모듈별. phase3 `WIP/axdt/test/` 옆에 progress 테스트 추가.
- 픽스처: 유효/무효 progress 테이블, 다양한 report frontmatter.
- 커버: 정합 규칙 매트릭스(§4) 전수, 파싱 라운드트립(`parse`→`render`→`parse` 안정), lint findings 코드, recover 요약(수용 대기 탐지), commit이 ERROR에서 거부.

---

## 9. 교차-Phase 인터페이스

| 대상 | 계약 |
|---|---|
| **Phase 1** | `docs/interim/progress.md` 빈 양식·`report/_TEMPLATE.md`가 본 스키마(§2.2·§3)에 정합. 우리가 스키마와 progress 정본 양식을 확정, report 템플릿은 Phase 1 소관(§10 ②) |
| **Phase 2** | Maintainer→Leader **주입 규약**(작업 지시·반려 전달)과 report 파일 상세 포맷. Phase 4는 상태 어휘·정합만 |
| **Phase 3** | 허브 git 배선(commit.py가 phase3 config·git 사용), send-keys substrate(통신 채널). D15 게이트에 lint를 얹는 강제는 하드닝 |
| **Phase 7** | web 브리핑이 `recover.reconstruct` 출력을 read-time 렌더(ADR-0002). 별도 상태원 없음 |

---

## 10. 결정 지점

**① 스키마의 권위 정의 위치 — WIP/specs + 코드 + 템플릿 (새 SoT 없음).**
상태 어휘·스키마의 권위 정의를 본 스펙(WIP/specs, AXDT 자체 설계 D12) + `schema.py`(코드가 강제) + 템플릿 헤더에 둔다. **새 SoT 문서를 만들지 않으므로 사용자 게이트 PR이 불필요**하다(규범 규칙 3종은 이미 SoT에 있다). 어휘를 SoT 규칙으로 못박아 신규 프로젝트에 전파(`propagation`)하려면 별도 사용자 게이트 PR이 필요하며, 현재는 하지 않는다(스키마는 `schema.py`+템플릿으로 clone과 함께 전파된다).

**② Phase 1 경계 — 스키마는 우리, report 템플릿은 Phase 1.**
"progress 빈 양식·report 템플릿"은 TODO상 Phase 1 항목이고 병렬 세션이 진행 중인데, 스키마는 본 Phase가 확정한다(의존 역전). 경계: **우리가 스키마 + `progress.md` 정본 빈 양식까지 만들고**, `report/_TEMPLATE.md`는 Phase 1 소관으로 둔다. 같은 파일 동시 편집을 막기 위해 실제 착수 시 Phase 1 세션과 맞춘다.

**③ 반려 사유의 durable 기록 — Leader 다음 report에 반영.**
progress는 자유 텍스트가 없는 엄격 스키마, report는 Leader 소유. 반려 사유는 send-keys로 전달하고 durable 기록은 Leader의 다음 report 이터레이션에 남긴다(§2.4). 반려 근거 자체의 형식화는 Phase 2 통신 프로토콜 사안으로 넘긴다.
