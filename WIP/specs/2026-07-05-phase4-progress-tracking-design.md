# Phase 4 — 진척 추적 모델(Progress / Report) 설계

> 상태: **초안 (브레인스토밍 합의, 3차 다중 리뷰 Codex+Fable 반영 — commit 검사=합성 폐포로 확정)** · 작성일 2026-07-05 · 범위: Phase 4 (WIP/TODO.md)
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
- **lint를 허브 경로 게이트에 얹어 강제하는 배선** → **Phase 3 baseline 허브 게이트(미구현)**. 본 Phase의 lint는 **권고 + 게이트에 꽂을 수 있는 검사 코드**로 제공한다(§2.5). (ref 위장 방지 같은 **주체 인증만** D15/`ADR-0007` 하드닝으로 연기 — 경로/콘텐츠 게이트 자체는 하드닝이 아니라 baseline.)
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
| `todo` | `in-progress`, `blocked`, `paused`, `in-review`, `accepted`, `superseded` |
| `in-progress` | `blocked`, `paused`, `in-review`, `accepted`, `rejected`, `superseded` |
| `blocked` | `in-progress`, `paused`, `in-review`, `accepted`, `superseded` |
| `paused` | `todo`, `in-progress`, `blocked`, `in-review`, `accepted`, `superseded` |
| `in-review` | `accepted`, `rejected`, `in-progress`, `blocked`, `paused`, `superseded` |
| `rejected` | `in-progress`, `blocked`, `paused`, `in-review`, `accepted`, `superseded` |
| `accepted` | *(종료 — 전이 없음)* |
| `superseded` | *(종료 — 전이 없음)* |

**불변식:**
- progress가 항상 권위. `report=done & progress=in-review`는 모순이 아니라 **정상(수용 대기)**(ADR-0004).
- **`in-review`는 비필수 경유**: Maintainer는 `in-progress→accepted`로 직행할 수 있다. `in-review`는 "report=done을 관측했으나 아직 수용 안 한" 상태다.
- 종료 상태 = `accepted` / `superseded`, **재열림 없음**. 수용 후 회귀가 발견되면 **신규 task**로 등록한다.
- `rejected` 후 Leader가 report를 `in-progress`로 되돌리면, Maintainer는 progress도 `in-progress`로 되돌린다(재순환).
- Maintainer 수용 어휘(`in-review`·`accepted`·`rejected`·`paused`·`superseded`)는 **report에 나타나지 않는다**. Leader는 `done`까지만 주장한다(§4가 lint로 강제).
- 전이 표는 **Maintainer 편집 시점의 규범**이다(한 번의 편집이 밟는 한 칸). lint는 progress 단일 스냅샷만 봐서 전이를 검사하지 못하고, **`commit.py`도 전이표로 끝점을 재검사하지 않는다.** 마일스톤 커밋은 중간 전이(예: `in-progress`)를 건너뛰므로 "지난 커밋↔지금" diff가 여러 칸 점프가 되어, 끝점 쌍을 한 칸 전이표로 보면 정상 커밋(예: `todo→rejected`, 빈 양식→`accepted`)이 거부된다. 커밋이 실제로 강제하는 것은 전이표의 **합성 폐포**(여러 칸을 합쳐도 불변인 검사)뿐 — **종료 재개 금지·행 삭제 금지·과claim·구조**(§5). 전이 이력은 git(마일스톤 커밋)으로 남는다.

### 2.2 progress 엄격 스키마 (MD 테이블, D7)
한 행 = 한 task. 고정 컬럼(순서 고정):

| 컬럼 | 내용 |
|---|---|
| `wave` | `w<n>` — 소속 wave. **task id의 wave 접두와 일치해야 함**(§4) |
| `task` | `w<n>.t<n>-<slug>` — task id(`branch-workspace-naming`; phase3 `naming.py`로 형식 검증) |
| `status` | `progress.status`(통제 어휘) |
| `leader` | 담당 Leader 식별자(형식 자유) |
| `updated` | 최종 갱신(ISO date `YYYY-MM-DD`) |

report 파일은 **컬럼으로 두지 않는다**(pointer 중복 제거). 각 task의 report 존재·상태는 canonical 경로 `report_dir/<task>.md`(task id에서 파일명 결정)로 판정한다(§4.2). 파일이 없으면 "report 없음"으로 취급한다.

**wave 롤업 — 전량 사상(total mapping).** task 행이 **유일한 권위**다. wave 단위 상태는 저장하지 않고 도구(recover·web)가 소속 task들의 `progress.status`에서 **파생 계산**한다(저장 시 드리프트 방지). 출력은 progress 어휘가 아니라 **전용 어휘** `WAVE_ROLLUP_STATUSES = {empty, todo, in-progress, in-review, blocked, paused, done, superseded}`이며, 규칙은 다음 우선순위의 전량 함수다(위에서부터 첫 매치):

1. task 없음 → `empty`
2. 하나라도 `blocked` → `blocked`
3. 하나라도 `paused` → `paused`
4. 전부 종료(`accepted`∪`superseded`) → `accepted` 하나라도 있으면 `done`, **전부 `superseded`면 `superseded`**(취소된 wave, 완료 아님)
5. 전체 상태가 `{todo, superseded}`의 부분집합이고 `todo`가 하나 이상 → `todo` (미착수 wave — `superseded`만 섞임. `accepted` 등이 하나라도 있으면 미해당 → 규칙 7)
6. 활성(`todo`·`in-progress`·`rejected`) 없이 `in-review`만 남음(+종료 혼재) → `in-review`
7. 그 외(활성 잔존) → `in-progress`

(`empty`는 순수함수 결과일 뿐 — recover 입력 `(progress_path, report_dir)`으로는 도달 불가하나 함수 계약상 남겨둔다. 무해.)

### 2.3 도구 모듈 (`WIP/axdt/progress/`)
각 모듈은 하나의 명확한 책임을 가지며 `schema`를 단일 정의원으로 참조한다. phase3와 동일하게 TDD로 만든다.

| 모듈 | 책임 | 성격 |
|---|---|---|
| `schema.py` | 컬럼·통제 어휘·종료 상태·허용 전이·정합 매트릭스·wave 롤업 규칙. 모든 모듈이 여기서 읽는다 | 순수(IO 없음) |
| `table.py` | progress MD 테이블 ↔ 구조화 객체 파싱/직렬화, report frontmatter 파싱. lint·recover 공용 | IO-light |
| `lint.py` | 검증: 스키마 적합·참조 무결성(양방향)·report↔progress 정합 매트릭스(§4). 결과는 findings 목록 | 읽기 전용 |
| `recover.py` | 복원: progress(권위)+report(canonical 경로) → 구조화 상태 + 수용 대기·블로커 수용 대기·재작업·주의 목록(§6.2). web도 이걸 렌더 | 읽기 전용 |
| `commit.py` | HEAD 대비 progress diff의 **합성-폐포 검사**(종료 재개·행 삭제·과claim·구조; 전이표 한 칸 검증 아님, §5) + diff에서 이벤트·규약 메시지 생성 → 스테이징 → commit. progress 편집 안 함·수용 판단 안 함·허브 push 안 함(§6.3) | 쓰기(git, 로컬 보조) |

### 2.4 절차의 Phase 4 소관 경계
승격·반려·복원 절차에서 **Phase 4가 소유하는 것은 상태 전이와 도구뿐**이다. *통신 행위*(Leader에게 지시·반려 전달)는 본 Phase 밖이다.

- **승격/반려** = progress 상태 전이(§2.1) + 도구(lint/commit). Maintainer의 **수용 판단** 자체는 도구가 대신하지 않는다(ADR-0004의 게이트 지점).
- **지시 전달**(작업 배정·반려 통보) = phase3 **tmux send-keys** substrate + Phase 2 **주입 규약**. Phase 4는 그 전달을 유발하는 상태만 기록한다.
- **반려 사유의 durable 기록** = 두 갈래로 남긴다: (a) Leader의 **다음 report 이터레이션**에 "받은 피드백·조치" 반영(report는 Leader 소유), (b) `rejected` 전이의 **마일스톤 커밋 메시지에 사유 요약**(§6.3) — send-keys 휘발성·크래시 소실창 완화(ADR-0002 "git 이력=변경 이력"). (b)의 강제는 **조건부**다: `rejected`가 커밋 diff에 남는 한 메시지 생성기가 사유를 강제한다(§5 `format_milestone_message`, 없으면 거부). 다만 마일스톤 단위라, Maintainer가 반려 시점에 커밋하지 않고 재작업·재승격까지 미루면 끝점 diff에 `rejected`가 안 남아 사유가 소실될 수 있다 — 이를 좁히려 **반려 기록 시 즉시 마일스톤 커밋**을 규범으로 둔다(§6.1 5·§6.3 (b)). Maintainer 반려 근거 자체의 형식화(별도 산출물)는 Phase 2 사안.

### 2.5 강제 경계 — "도구 사용"이 아니라 "결과물 유효성", 그리고 게이트는 아직 미배선
도구를 Maintainer가 실제로 돌렸는지는 강제하지 않으며, 원리상 강제할 수 없다. ADR-0007: 강제는 컨테이너가 접근 못 하는 호스트/허브 층 검사에서만 성립하는데, **Maintainer는 그 층에 상주하는 신뢰 루트**라 감시할 상위 주체가 없다. 강제되는 것은 결과물이며, **그 강제 지점(허브 경로 게이트)은 현재 미구현**이다.

- **현재 사실(중요):** phase3 브랜치의 허브(`WIP/axdt/infra/hub.py`)는 `git daemon --enable=receive-pack`로 **무인증 노출**만 하고 **서버사이드 훅이 없다**. 보호 경로 diff를 거부하는 **경로/콘텐츠 게이트는 ADR-0007상 "하드닝"이 아니라 "Phase 3 baseline"**이다 — 다만 **아직 미구현**(TODO Phase 3 잔여). 하드닝으로 연기된 것은 **주체 인증(ref 위장 방지)뿐**이다. `ADR-0007`은 `status: proposed`.
- **로컬 pre-commit 훅도 미설치**다(ADR-0007 설계 항목일 뿐 현존물 아님). 따라서 지금 progress 보호는 **문서 규범뿐**이다(“문서 규범 + 로컬 훅”이 아님). `protected-paths`가 `progress.md`를 Maintainer 단독으로 규정하지만, 이를 실제로 거부하는 **허브 경로 게이트가 배선될 때 비로소 강제**된다(Phase 3 baseline 잔여).
- **Phase 4의 역할:** `lint`를 그 (아직 안 만든) baseline 경로/콘텐츠 게이트에 **꽂을 수 있는 검사 코드**로 만든다(손 편집이든 도구든 스키마·정합 위반이면 걸리도록). 게이트 부재기에는 lint가 **권고**로 동작한다(commit.py가 커밋 전 실행; Maintainer/CI가 호출). 즉 Phase 4는 새 강제 장치를 만들지 않고 **검사를 제공**하며, 강제는 Phase 3 baseline 경로 게이트에 위임한다. phase3 스펙 §2.2(격리 정직성)와 동일한 태도.
- **게이트 스코핑(중요):** 미래 허브 경로 게이트가 lint를 강제할 때도 **그 push가 바꾼 경로·행에 대한 ERROR만** 거부 사유로 쓴다. 그렇지 않으면 Leader가 유발한(남의 행) ERROR가 Maintainer의 무관한 마일스톤 push를 막아, `commit.py`가 피한 데드락을 게이트에서 재생산한다. `commit.py`의 거부범위(§5)와 **동일 원칙** — 검사는 전역, 거부는 이번 조작이 바꾼 것으로 스코핑.

### 2.6 상태 저장 = interim 파일 (ADR-0002)
별도 DB·큐·이벤트 로그를 두지 않는다. progress·report 파일이 유일한 상태 매체이며, progress의 git 이력(마일스톤 커밋, D10)이 변경 이력 역할을 한다. 복원은 파일 재파싱으로 재구성한다(§6.2).

---

## 3. progress 테이블 포맷

파일은 상단에 규범 문단(단일 작성자·스키마 참조)을 두고, **테이블은 파일 내 유일한 MD 테이블**이다(§5 파싱 규약). 빈 양식(Phase 4가 setup하는 정본):

```markdown
| wave | task | status | leader | updated |
|---|---|---|---|---|
```

행이 있는 예:

```markdown
| wave | task | status | leader | updated |
|---|---|---|---|---|
| w1 | w1.t1-hub-init | accepted | L-alice | 2026-07-05 |
| w1 | w1.t2-cli-scaffold | in-review | L-bob | 2026-07-05 |
| w2 | w2.t1-auth-login | blocked | L-carol | 2026-07-05 |
```

- 헤더 행·구분 행 고정. 컬럼 순서·이름 고정(lint가 검사).
- **report는 컬럼이 아니다.** 각 task의 report 존재·상태는 canonical 경로 `docs/interim/report/<task>.md`(progress.md가 `docs/interim/progress.md`, task id에서 파일명 결정)로 판정한다(§4.2). 파일이 없으면 "report 없음"으로 취급한다.

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

### 4.2 참조 무결성 (report는 canonical 경로로 판정)
report는 progress 컬럼이 아니므로 **pointer 정합 검사는 없다**. 각 task의 report는 canonical 경로 `docs/interim/report/<task>.md`로만 찾는다(task id → 파일명). 파일 부재 자체는 ERROR가 아니라 §4.3에서 `report=—`로 처리한다.
- **ERROR** canonical report 파일이 있으나 frontmatter `id` ≠ 그 task.
- **ERROR** canonical report 파일이 있으나 frontmatter `status` 누락 또는 `REPORT_STATUSES` 밖(§2.1 불변식 "수용 어휘가 report에 안 나타남"을 여기서 강제).
- **WARN** `report_dir`에 있으나 progress에 대응 task 행이 없는 **고아 report**(배정 누락·task id 오타 탐지). 스캔 대상은 **task 형식 파일명(`w<n>.t<n>-<slug>.md`)뿐** — `README.md`·`_TEMPLATE.md` 등 비-task 파일은 제외.

### 4.3 상태 정합 매트릭스 (`pair_severity(report | None, progress)`)
행 = `report.status`(또는 `—`=파일 부재), 열 = `progress.status`. `·`=정상(None) · `W`=WARN · `E`=ERROR.

| report \ progress | todo | in-prog | blocked | in-review | accepted | rejected | paused | superseded |
|---|---|---|---|---|---|---|---|---|
| `todo` | · | · | · | W | **E** | W | · | · |
| `in-progress` | · | · | · | W | **E** | W | W | · |
| `blocked` | W | W | · | W | **E** | W | W | · |
| `done` | W | W | W | · | · | W | W | · |
| `needs-spec` | W | W | · | W | **E** | W | · | · |
| `—`(부재) | · | W | · | W | **E** | W | · | · |

핵심 근거:
- **`accepted` 열은 `report=done`이 아니면 전부 ERROR** — 수용은 Leader의 done 주장을 전제한다. `report=—`(주장 자체가 없음)+`accepted`가 가장 심한 권위 우회이므로 ERROR(1차 리뷰 Blocker 해소).
- **`in-review` 열의 report≠done은 WARN**(ERROR 아님) — in-review는 관측·가역 상태다. Maintainer가 올린 직후 Leader가 done을 회수(→in-progress)하는 것은 정상 재순환이므로, 이 일시 상태가 무관 task의 마일스톤 커밋까지 막지 않게 WARN으로 둔다(1차 리뷰 Major 해소).
- **`done` 행의 `todo/in-progress/blocked/rejected/paused`는 WARN**(승격/재승격 대기) — `rejected`+`done`은 반려 후 재작업 완료를 다시 주장한 "재승격 대기". `paused`+`done`은 in-review로 가야 함.
- **`blocked`·`needs-spec` 행의 미수용은 WARN**(블로커/사양 수용 대기) — done 승격 대기와 대칭. `needs-spec`의 정본 대응은 `blocked`(또는 `paused`), 재계획 종료 `superseded`는 정상(·).
- **`report`가 활성/블로커인데 `progress=rejected`면 WARN**(재순환 신호) — `todo`/`in-progress`/`blocked`/`needs-spec` 행의 `rejected` 열. `rejected`는 이전 done 주장을 전제하므로, report가 그 아래(미착수 `todo` 리셋 포함)로 돌아간 것은 Leader 재순환 신호다. 되돌아오는 중인 정상 과도기라 ERROR 아님.
- **`report`가 진행/블로커인데 `progress=paused`면 WARN**(충돌 신호) — `in-progress`/`blocked` 행의 `paused` 열. Maintainer는 "의도적 보류"인데 Leader는 계속 진행(`in-progress`)하거나 외부 대기(`blocked`)를 주장. `paused`≠그 둘(§2.1)이라 불일치 표시. (`needs-spec`/`paused`는 "사양 결정 대기로 보류"가 자연스러워 정상(·).)
- **`todo` 행과 `—`(부재) 행의 비대칭**: `report=todo`는 "미착수"를 **적극 주장**하는 것이라 progress가 앞서가도(예: `blocked`/`paused`) 보고 lag일 뿐 정상(·). (단 `rejected`는 이전 done 주장을 전제하므로 예외 — 위 재순환 근거대로 W.) `report=—`는 주장 자체가 없어, progress가 활성(`in-progress`/`in-review`/`rejected`)이면 WARN. 단 `progress`가 `blocked`/`paused`면 착수 전 정상(·)이고, `accepted`는 주장 없는 수용이라 ERROR.

---

## 5. 도구 모듈 계약

```python
# schema.py (순수)
REPORT_STATUSES: frozenset[str]        # {todo, in-progress, blocked, done, needs-spec}
PROGRESS_STATUSES: frozenset[str]      # {todo, in-progress, blocked, in-review, accepted, rejected, paused, superseded}
WAVE_ROLLUP_STATUSES: frozenset[str]   # {empty, todo, in-progress, in-review, blocked, paused, done, superseded}
COLUMNS: tuple[str, ...]               # ('wave','task','status','leader','updated')  — report 컬럼 없음
TERMINAL: frozenset[str]               # {accepted, superseded}
ALLOWED_TRANSITIONS: dict[str, frozenset[str]]           # §2.1 전이 표 — 편집 시점 규범(commit 끝점 검사엔 안 씀, §2.1/§5 commit.py)
def pair_severity(report: str | None, progress: str) -> str | None   # 'ERROR'|'WARN'|None (report=None=부재)
def wave_rollup(task_statuses: list[str]) -> str          # §2.2 전량 사상, 반환 ∈ WAVE_ROLLUP_STATUSES

# table.py
@dataclass
class TaskRow: wave: str; task: str; status: str; leader: str; updated: str   # report 컬럼 없음
@dataclass
class Report: id: str; status: str
def parse_progress(text: str) -> list[TaskRow]            # 파일 내 유일 테이블을 파싱, 2개↑면 오류
def render_progress(rows: list[TaskRow]) -> str           # 테이블 영역만 생성(라운드트립 안정); 문서 프로즈 보존은 호출측 책임
def parse_report(text: str) -> Report                     # frontmatter에서 id·status. 키 누락 시 예외(lint가 ERROR로 변환)

# lint.py
@dataclass
class Finding: severity: str; code: str; task: str | None; message: str
def lint(progress_path: Path, report_dir: Path) -> list[Finding]
    # 각 task의 report는 canonical 경로 report_dir/<task>.md 로 유도(progress에 pointer 컬럼 없음).
    # report_dir 스캔은 task 형식 파일명만 대상으로 고아 report(§4.2) 탐지(비-task 파일 제외).

# recover.py
@dataclass
class State:
    tasks: list[...]                       # (task, progress.status, report.status|None, updated)
    pending_acceptance: list[...]          # report=done ∧ progress ∉ {accepted, superseded}  (rejected=재승격 포함)
    pending_blocker_acceptance: list[...]  # report ∈ {blocked, needs-spec} ∧ progress ∈ {todo, in-progress, in-review, rejected}
                                           #   (종료·이미 blocked/paused 제외 — accepted는 §4.3 E라 needs_attention 몫)
    in_rework: list[...]                   # progress=rejected
    blocked_or_paused: list[...]           # progress ∈ {blocked, paused}
    needs_attention: list[...]             # §4.3 pair_severity 가 W/E 인 행 (매트릭스에서 파생 — 드리프트 방지)
    wave_rollup: dict[str, str]            # wave → WAVE_ROLLUP_STATUSES
def reconstruct(progress_path: Path, report_dir: Path) -> State
    # canonical report가 있으나 파싱 불가·id 불일치면 report.status=None(부재)로 접지 않고 invalid로 표기,
    # needs_attention에 넣는다(깨진 report가 '없음'으로 오분류돼 pending_acceptance 등을 왜곡하지 않게).
def format_summary(state: State) -> str                   # Maintainer·web용 텍스트
    # 모든 집합은 소속(∈/∉)으로만 판정 — progress 어휘엔 순서가 없어 부등호 비교 없음.

# commit.py — 커밋 시점 HEAD:progress.md vs 작업본 progress.md 비교(둘 다 있는 유일 지점)로
#             합성-폐포 검사 + diff에서 이벤트·메시지 생성. lint(단일 스냅샷)도 git(의미 무지)도 못 하는 일.
# 마일스톤은 중간 전이를 건너뛰므로 끝점 diff는 여러 칸 점프일 수 있다 → 전이표 한 칸 검증을
# 끝점에 적용하지 않는다(그러면 정상 반려·최초 수용 커밋이 거부됨, §2.1). 강제 대상은
# 몇 칸을 건너뛰어도 불변인 검사(전이표의 합성 폐포)뿐: 종료 재개·행 삭제·과claim·구조.
@dataclass
class ProgressEvent: task: str; before: str | None; after: str; kind: str   # before=None → 신규 행
def diff_progress(base: list[TaskRow], new: list[TaskRow]) -> list[ProgressEvent]
    # base=HEAD:progress.md(없으면=최초 커밋, 빈 테이블로 간주 → 모든 행 신규), new=작업본.
    # 행 단위로 (before, after) 이벤트 산출. 전이표 한 칸 검사는 여기서 하지 않는다.
    # 신규 행(before=None): 비종료 임의 허용(등록+진행이 한 마일스톤에 접힐 수 있음).
    #   accepted 신규면 과claim 검사가 커버(in-review 신규는 §4.3 W, 차단 아님).
def format_milestone_message(events: list[ProgressEvent], rejection_reasons: dict[str, str] = {},
                             gates: tuple[str, ...] = ()) -> str
    # 파싱 가능한 커밋 메시지 생성. after==rejected 이벤트는 task별 사유 필수(없으면 오류).
    # events=0 ∧ gates 있음(상태 무변경 게이트 통과)도 유효 — 게이트명으로 메시지 생성.
def milestone_commit(repo: Path, rejection_reasons: dict[str, str] = {},
                     extra_paths: tuple[Path, ...] = (), gates: tuple[str, ...] = ()) -> None
    # 합성-폐포 검사(거부범위) → progress.md(+관련 report) 스테이징 → 생성 메시지로 commit.
    # progress 편집 안 함·수용 판단 안 함·허브 push 안 함.
    #
    # 거부범위 = 전이표의 합성 폐포(여러 칸 건너뛰어도 불변) ∩ Maintainer가 지금 고칠 수 있는 것:
    #   (1) 종료 재개 — HEAD가 종료(accepted/superseded)인 행의 status가 바뀜
    #   (2) 행 삭제 — HEAD에 있던 task 행이 사라짐
    #   (3) 과claim — 이번 커밋에서 accepted로 올린(또는 accepted로 신규 등록한) 행인데 그 task report=done 미확인.
    #        done = 이번 커밋에 스테이징되는 report 블롭이 파싱 성공 ∧ status=done ∧ id=task 모두 만족
    #        (하나라도 실패=미확인=거부). in-review 상승/신규는 차단 안 함(가역 관측, §4.3 W — lint가 표시).
    #   (4) progress.md 구조 오류(§4.1)
    # 거부 안 함(경고+라우팅): 이번에 손 안 댄 다른 task의 report 문제(누락·frontmatter·orphan·id).
    #   Leader 소유라 Maintainer가 못 고침 → 막으면 데드락. lint가 잡아 보여주고 Maintainer가 되돌림.
    #   (미래 허브 게이트도 같은 스코핑: 이 push가 바꾼 행/경로에 대해서만 lint E를 거부 사유로 씀, §2.5.)
    # 전이표(§2.1) 한 칸 검사는 여기서 하지 않는다 — 편집 시점 규범일 뿐(끝점 diff로 검증 불가).
    # 순수 git으로 우회 가능(로컬 보조). 진짜 차단은 미래 허브 게이트(§2.5).
```

경로(progress.md·report 디렉터리·repo 루트)는 phase3 `config.py`에서 얻는다 — 단 현재 `config.py`에는 progress/report 경로 함수가 없으므로 **Phase 4가 `progress_path`·`report_dir`를 추가**한다. 도구는 `docs/interim/` 파일과 git만 다루며 컨테이너·tmux를 알지 못한다(결합 최소).

---

## 6. 절차

### 6.1 승격 흐름 (report→progress)
1. Maintainer가 report 변경을 관측(주기 확인 또는 신호).
2. `axdt progress lint`로 정합성 확인 — **findings는 전부 표시**하되, 커밋 거부는 §5 거부범위(이번에 바꾼 행)만 따른다. 남의 task ERROR가 무관한 승격을 막지 않는다(데드락 회피).
3. report 내용을 **검토·수용 판단**(필요 시 Reviewer/Tester/사용자 게이트, wave 롤업 고려) — 도구가 대신하지 않는다.
4. 수용: progress 행 `status` 갱신 + `updated`. `in-review`를 경유하거나 `in-progress→accepted` 직행 모두 허용(§2.1). Maintainer만 편집.
5. 반려: progress `rejected` 기록 + **즉시 마일스톤 커밋**(사유를 메시지에 고정, §6.3 (b) — 미루면 소실창, §2.4). 전달은 send-keys(Phase 2/phase3). Leader가 report를 `in-progress`로 되돌리면 Maintainer도 progress를 `in-progress`로 되돌려 재순환(§2.1 전이).

### 6.2 복원 절차 (크래시·컨텍스트 압축 후)
1. Maintainer 재시작 → `axdt progress status`(recover) 실행.
2. 도구가 progress(권위)+report를 재구성해 **명시적 집합**으로 분류(§5 `State`): 수용 대기(`report=done ∧ progress ∉ {accepted, superseded}`), 블로커/사양 수용 대기(`report ∈ {blocked, needs-spec} ∧ progress ∈ {todo, in-progress, in-review, rejected}`), 재작업 중(`progress=rejected`), 블로커/보류(`progress ∈ {blocked, paused}`), 주의 필요(§4.3 매트릭스에서 파생), wave 롤업. (순서 비교 없이 집합 소속으로만 판정 — 드리프트 방지.)
3. Maintainer가 "어디까지 수용됐고 무엇이 대기·재작업인지" 즉시 복원해 이어간다.
4. progress git 이력(마일스톤 커밋)이 시점 스냅샷을 제공한다(ADR-0002).

### 6.3 마일스톤 커밋 정책 (D10)
- **무엇**: `progress.md` + 그 전이에 관련된 report 파일을 함께 커밋.
- **언제**: 의미 있는 전이 — 최소 (a) task `accepted`, (b) `rejected`, (c) wave 완료(전 task 종료), (d) 사용자 게이트 통과. 자잘한 `in-progress` 갱신마다가 아니라 **마일스톤 단위**.
- **누가**: Maintainer(호스트 상시 세션, ADR-0001). `commit.py`가 **합성-폐포 검사(거부범위)** → 스테이징 → **도구가 생성한** 메시지로 commit(§5).
- **왜 전이표 한 칸 검사가 아닌가**: 마일스톤은 중간 전이를 건너뛰어 "지난 커밋↔지금" diff가 여러 칸 점프가 된다. 끝점을 전이표 한 칸으로 보면 정상 반려(`todo→rejected`)·최초 수용(빈 양식→`accepted`) 커밋이 거부된다. 그래서 커밋은 **몇 칸을 건너뛰어도 불변인 검사(합성 폐포)**만 강제한다. 전이표(§2.1)는 편집 시점 규범.
- **거부범위(합성 폐포 ∩ Maintainer가 지금 고칠 수 있는 것)**: (1) 종료 재개 (2) 행 삭제 (3) 이번 커밋에서 **accepted**로 올린/신규 등록한 행의 과claim(report=done 미확인; done=스테이징 report 블롭 파싱∧status=done∧id=task. `in-review`는 §4.3 W라 차단 안 함) (4) progress.md 구조 오류(§4.1)만 거부. 이번에 손 안 댄 다른 task의 report 문제는 **경고+라우팅**(막으면 데드락). 미래 허브 게이트도 같은 스코핑(이 push가 바꾼 행/경로에 대해서만 lint E, §2.5). 상세는 §5 `milestone_commit` 주석.
- **메시지 규약**: 도구가 diff에서 **생성**한다(자유 `-m` 아님). 형식 — subject `chore(progress): <task> <from>-><to>`, 복수/wave면 `chore(progress): batch <n> events` + 본문 `Events:` 목록. `rejected` 이벤트는 본문에 `Reason: <task> <사유>` 필수(§2.4 durable 기록 (b)). 상태 무변경 게이트 통과(events=0 ∧ gates)면 게이트명으로 메시지 생성.
- **어디에**: progress가 사는 repo(대상 프로젝트, 도그푸딩 시 AXDT)의 기본 작업본에서. task 브랜치가 아니다. **허브 push는 이 도구의 책임이 아니다**(phase3 허브 배선/Phase 6 소관).

---

## 7. CLI (phase3 `cli.py` 확장)
- `axdt progress lint` — 정합 검사, findings 출력. ERROR 있으면 비정상 종료코드.
- `axdt progress status` — recover 요약(수용 대기·블로커 수용 대기·재작업·블로커/보류·**주의 필요**·wave 롤업).
- `axdt progress commit` — 마일스톤 커밋. 메시지는 HEAD 대비 diff에서 **생성**(자유 `-m` 없음). `--reason <task>="<사유>"`(반복, `rejected`에 필수), `--gate "<이름>"`, `--dry-run`(생성될 메시지·스테이징 집합만 출력).

---

## 8. 테스트 전략 (TDD)
- pytest, 모듈별. phase3 `WIP/axdt/test/` 옆에 progress 테스트 추가.
- 픽스처: 유효/무효 progress 테이블, 다양한 report frontmatter(정상·id 불일치·status 누락·비통제 값).
- 커버: **정합 매트릭스 §4.3 전 셀**(report 6상태 × progress 8상태), 구조·형식 검사(§4.1), 참조 무결성(§4.2 고아 report·비-task 파일 제외·id/status 검사), `wave_rollup` 전량 사상(빈 wave·all-superseded·`todo`+`superseded`·**`todo`+`accepted`**·혼재·우선순위), 파싱 라운드트립, recover 집합 분류(수용 대기·블로커 수용 대기·재작업·**블로커/보류·주의 필요·깨진 report는 needs_attention**).
- commit: **합성-폐포 거부**(종료 재개·행 삭제·구조; **여러 칸 점프 diff는 통과** — `todo→rejected`·빈 양식→`accepted`), **diff→이벤트 파생**(수용·반려·wave·신규 등록·복합; 최초 base=빈 테이블), **생성 메시지 파싱 라운드트립**(`rejected` 사유 필수·events=0∧gates), **거부범위 스코핑**(이번 커밋에서 `accepted`로 올린 행의 과claim은 거부 vs 남의 report 문제·`in-review` 상승은 통과).

---

## 9. 교차-Phase 인터페이스

| 대상 | 계약 |
|---|---|
| **Phase 1** | `report/_TEMPLATE.md`가 **frontmatter 최소 계약** `id`(=task id)·`status`(∈`REPORT_STATUSES`)를 갖도록 한다(§5 `parse_report` 전제). `progress.md` 빈 양식은 Phase 4가 setup한다(§10 ②). 병렬 Phase 1 세션과 파일 경계를 맞춘다 |
| **Phase 2** | Maintainer→Leader **주입 규약**(작업 지시·반려 전달)과 report 파일 섹션·본문 구조. Phase 4는 상태 어휘·frontmatter 두 키·정합만 |
| **Phase 3** | 허브 git 배선(commit.py가 phase3 config·git 사용), send-keys substrate(통신 채널), **허브 경로 게이트**(미구현 — 여기에 lint를 얹으면 강제하되 **push가 바꾼 경로/행 스코프로만**, §2.5). progress/report 허브 push 배선 |
| **Phase 7** | web 브리핑이 `recover.reconstruct` 출력(+`wave_rollup`)을 read-time 렌더(ADR-0002). 별도 상태원 없음 |

---

## 10. 결정 지점

**① 스키마의 권위 정의 위치 — WIP/specs + 코드(단일 정의원) + 템플릿.**
상태 어휘·스키마의 권위 정의를 본 스펙(WIP/specs, AXDT 자체 설계 D12) + `schema.py`(**단일 정의원**) + 템플릿 헤더에 둔다. 새 SoT 문서를 만들지 않으므로 사용자 게이트 PR이 불필요하다(규범 규칙 3종은 이미 SoT에 있다).
- **트레이드오프(명시):** `progress-single-writer`·`report-to-progress-authority`가 "통제 status 어휘는 D7 스키마에서 정의"로 위임하는데, 그 정의처가 WIP+코드면 **어휘 변경이 사용자 게이트 없이 Maintainer 단독으로 가능**하다(WIP는 보호 경로지만 게이트 PR 대상은 아님). 어휘를 SoT 수준으로 통제·전파하려면 별도 사용자 게이트 PR로 규칙 각주를 확정해야 하며, 현재는 하지 않는다.
- **대상 프로젝트에서의 도구 위치(open):** `schema.py`+템플릿은 clone과 함께 전파되지만, `WIP/axdt`는 D12상 AXDT 자체 코드다. 도그푸딩이 아닌 대상 프로젝트에서 진척 도구가 어디에 실릴지는 후속 결정(현재 범위 밖).

**② Phase 1 경계 — 스키마·progress 빈 양식은 Phase 4, report 템플릿은 Phase 1.**
"progress 빈 양식·report 템플릿"은 TODO상 Phase 1 항목이나 스키마는 본 Phase가 확정한다(의존 역전). 경계: **Phase 4가 스키마 + `docs/interim/progress.md` 정본 빈 양식을 Maintainer 1회성 setup으로 반영**하고(현재 placeholder를 대체), `report/_TEMPLATE.md`는 Phase 1 소관으로 두되 **frontmatter 두 키 계약(§9)을 전달**한다. 같은 파일 동시 편집을 막기 위해 실제 착수 시 Phase 1 세션과 맞춘다. (착수 시 갱신 대상: 현재 `docs/interim/progress.md` placeholder와 그 "Phase 1이 빈 양식" 문구 → 5컬럼 정본으로; `WIP/TODO.md`의 D7 항목이 아직 6컬럼("…담당 Leader, report 경로")을 전제하므로 5컬럼으로 함께 갱신.)

**③ 반려 사유의 durable 기록 — report + 커밋 메시지 이중.**
send-keys는 휘발이므로 반려 사유를 (a) Leader 다음 report, (b) `rejected` 마일스톤 커밋 메시지 요약(§6.3) 두 곳에 남긴다(§2.4). 반려 근거의 별도 형식화(산출물)는 Phase 2 통신 프로토콜 사안으로 넘긴다.
