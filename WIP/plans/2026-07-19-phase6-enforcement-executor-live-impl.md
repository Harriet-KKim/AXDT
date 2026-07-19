# Phase 6 강제 게이트 실행부(GitHubGatePorts) 라이브 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **착수 시점 = Phase 9 (라이브 도그푸딩).** 모든 Task는 실제 GitHub 저장소·`gh` CLI 응답을 봐야 스키마가 확정되는 provisional 구현이다(스펙 §1 비목표·§8·§9). 착수 전에 "활성화 전제조건 P1~P4"를 모두 처리한다. 순수 코어(`gate.py`·`keys.py`·`models.py`)와 포트 계약(`ports.py`)의 시그니처·데이터 모델·기존 동작은 동결이며, 동결을 바꾸는 항목은 모두 P3의 승인 대상으로 열거한다(조용한 변경 금지).

**Goal:** `hosts/github.py`의 7개 포트를 실제 `gh api` 호출로 구현하고, 룰셋 점검·`axdt-critical-paths` 두 사전 관문을 컨트롤러 층에 배선한다.

**Architecture:** `github.py`는 `git_host`의 `CommandBackend`(ABC)를 주입받아 gh 호출을 격리하고(subprocess 직접 호출 금지), (b) 클라이언트의 adapter+backend 분리를 계승한다. 각 포트는 gh 응답 JSON을 파싱해 순수 코어 계약(`models.py`·`keys.py`)으로 매핑한다. 포트는 원시 사실만 채우고 결정권 논리곱은 순수 코어가 계산한다.

**Tech Stack:** Python 3(`py -3`), `gh` CLI, pytest. 재사용: `axdt.git_host.backend.{CommandBackend,FakeCommandBackend,SubprocessBackend}`, `axdt.git_host.models.{PullRequest,CommandResult,GitHostError}`. **pytest 기준 디렉터리 = `WIP`**: `cd WIP && py -3 -m pytest axdt/sot_gate/...`.

## 활성화 전제조건 / 선행 계약 작업 (착수 전 필수)

라이브 코드 이전에 처리해야 하며, 정본 개정·동결 계약 확장을 포함해 이 계획의 라이브 코드 범위를 벗어난다(사용자 게이트/별도 승인). 계획은 이를 조용히 넘기지 않고 전제조건으로 명시한다.

- **P1. 정본 규칙 드리프트 정정(사용자 게이트 SoT PR).** `sot-readiness.md` 92·105행이 "`sot/*` 보호 불요/요구하지 않음(`ADR-0009` 결정 8)"으로 남아 있으나 결정 8은 2026-07-18 개정으로 RS-C를 요구한다. 개정 전 활성화하면 규칙과 `verify_ruleset_config`가 반대를 가리켜 모든 머지가 막힌다. 두 문장을 결정 8·스펙 §4.1에 맞추는 SoT PR이 선행돼야 한다.
- **P2. `verify_ruleset_config` 감시 범위 정본 개정(필수).** 매트릭스가 기계판독 블록 **전량**을 값 일치로 대조하므로(스펙 §4.1 감시 열거보다 넓음 — `require_last_push_approval`·RS-A `bypass`/`rules`·`enforcement` 활성 상태 포함), 정본 §4.1 감시 열거 **및 §3 `verify_ruleset_config` 계약·`ports.py` docstring**을 이 블록에 맞추는 개정이 선행돼야 한다. (초과 감시는 fail-closed 강화라 개정 전에도 안전하나 정합을 위해 필수 전제로 둔다.)
- **P3. 동결 계약 확장 승인(별도 승인 — 아래 전부).** 착수 전 승인받거나 동결 코어 밖 호스팅 래퍼에 둘지 결정한다.
  - (a) `merge_pull_request`의 `-> None → -> str`(§2.9 확정, Task 8).
  - (b) 두 키 취득 (ㄱ) base 복원 시 컨트롤러 감사·first-parent 이력 resolver 주입 계약(Task 6·9).
  - (c) `AuditRecord.base` first-parent SHA 취득 경로(Task 8) + **머지 성공 후 parent 조회·감사 쓰기 실패 시 durable retry/outbox 또는 복구 가능한 merge-SHA 기록 계약**.
  - (d) **Task 2 기동 점검·경보·실패 감사** — `controller.py:50-52`가 유보한 동결 동작 변경. 현재 `AuditRecord`(controller.py:21-40)는 성공 머지 전용이라 PR/base가 없는 **기동 실패 감사용 스키마**(사유·시각·룰셋 diff)를 추가하고 경보 sink를 정의한다.
  - (e) **Task 4 잠금 안 사전 관문** — critical-paths 블록 판독 실패의 RED 신호를 컨트롤러 계약에 넣거나(§7 (ㅁ) "잠금 안" 요구상 `merge_if_green` 내부 잠금과 통합), 래퍼로 둘 경우 잠금 통합 방안.
  - (f) **두 키 무효 표현 모델 개정(Task 6, (ㄴ) 선택 시)** — 두 키가 non-optional(`models.py:60-69`)이라 스탬프 결손을 표현할 수 없다. `stamp_valid: bool` 또는 optional raw stamp 필드를 `ApprovalEvent`에 추가해, SoT 완료 분기만 두 키 존재·일치를 요구하고 강제-필수 경로 분기(키 불요, 스펙 §2.6·92행)는 승인을 유지하도록 한다(임의 센티널 대신 구조적 표현).
- **P4. Phase 9 활성화 §7 전제 체크리스트 + 순서.** 단순 순서가 아니라 §7 전제를 모두 확인한다:
  1. 저장소 public·컨트롤러 신원·최소 권한 토큰 확보(`ADR-0009` 결정 1·12).
  2. `axdt-critical-paths` 블록이 신뢰 base(`main`)에 착지하고 파싱 가능(실행기 manifest 경로·허브 게이트 실행 폐쇄 전체 포함, `protected-paths.md:71-75·91-93`; 스펙 §7 (ㅁ)·506행). 실행기 manifest 경로 미확정분은 P1류 정본 확정.
  3. 초기 완전성 스윕(축3) **실행 + baseline finding 결정 종료 + 감사 이관 완료**(스펙 502-504행) — "실행"만이 아니라 완료 조건까지.
  4. **활성화 순서**: 워크플로 전제 실증(force-push 미사용) → **RS-C 적용** → RS-B 적용 → 컨트롤러 배포 + **bootstrap mode**(RS-A·기동 점검이 아직 불일치라 머지를 안 받는 fail-closed 대기; 배포 자체는 저장소 밖이라 룰셋과 무관 — 순서의 실제 귀결은 "컨트롤러 준비 전 모든 머지 정지") → **RS-A 적용** → strict 기동 점검(전 룰셋 일치 확인) → 종단 스모크. (스펙 505행이 고정한 것은 RS-B→컨트롤러 확인→RS-A 부분뿐이고 RS-C 적용 시점·나머지 단계는 이 계획의 합성이다 — RS-C 적용 시점을 §4.1에 명문화하는 것은 P2류 후속.)
  5. **스키마 캡처와 운영 활성화 분리**: 각 Task Step 0의 라이브 캡처는 **별도 도그푸드 저장소/수동 셋업**에서 하고, 위 운영 활성화 순서와 분리한다(캡처-적용 순환 제거).

## Global Constraints

- **라이브 스키마 캡처 우선 (조기 동결 금지)**: 각 포트 Task는 Step 0으로 라이브 `gh api` 응답을 캡처·확인한 뒤 그 캡처를 fixture로 red를 쓴다(스펙 §1·§8). 캡처는 P4-5의 도그푸드 셋업에서. (헬퍼 Task 0·배선 Task 2·4는 캡처 대상이 포트 응답과 달라 각 Task가 명시한다 — 모든 Task에 동일 Step 0이 있다는 뜻이 아니다.)
- **페이지네이션**: 목록 응답(rulesets·PR files·comments·reviews)은 Task 0 헬퍼로 전 페이지 수집하고 각 포트에 다중 페이지 red를 둔다. 뒤 페이지 누락은 `touches_*` 오판(pass-through)이므로 fail-closed상 필수(스펙 §2.6·§7).
- **동결 계약 확장 규약**: 동결 시그니처·동작을 바꾸는 Task(2·4·6·8·9의 resolver)는 P3에서 승인/래퍼 결정을 선행하고 Task 안에서 조용히 바꾸지 않는다.
- **provisional 경계**: gh api 스키마·산출물 저장·제안 머지 결과 취득·두 키 취득·사람 판별은 §8 미확정. Step 0 실측 전 동결하지 않는다(스펙 §8·§10).
- **테스트 경계**: 순수 코어·컨트롤러 테스트는 `FakeGatePorts`(회귀 152 유지). `github.py`는 `FakeCommandBackend`로 단위 테스트, 최종 스키마는 라이브 스모크(스펙 §6).
- **두 키 재계산 금지**: 두 키는 §2.3 (ㄱ)/(ㄴ)로 취득, 머지 시점 재계산 금지. 선택·표현은 §8·P3.
- **포트는 판정하지 않는다**: `role_name`·사람 여부·`dismissed`·스탬프 유효(`stamp_valid`) 등 원시 사실만 채우고, 논리곱·유효성 판정은 코어(스펙 §2.7·§3·§2.6 항목10).
- **사람/기계 판별(§2.7·§8)**: 결정권 = admin ∧ 명단 ∧ 사람. `author_is_human`·`approver_is_human`은 동결 필수 필드. 공통 identity resolver로 author·approver 양쪽을 채우고, **판별불능은 현 bool 계약상 `False`(→ 코어 fail-closed)**로 매핑한다.
- **선언 단일 진실원**: 룰셋 대조 값은 `ENFORCEMENT_MATRIX.md`의 `axdt-enforcement-matrix` 블록(신뢰 컨트롤러 배포본)이 정본. `verify_ruleset_config`가 블록 전량을 값 일치로 대조(손사본 금지, Task 1).

---

## Task 0: CommandBackend 주입 + gh api JSON/페이지네이션 헬퍼

**Files:** Modify `hosts/github.py`; Test `tests/test_hosts_github.py`(신규).

**Interfaces:** Consumes `CommandBackend`·`FakeCommandBackend`·`GitHostError`. Produces `GitHubGatePorts(backend, repo)`; `_api_json(*args) -> dict|list`(exit≠0·malformed JSON·빈 stdout·예상 밖 top-level 타입 → `GitHostError`); `_api_paginated(*args) -> list`.

- [ ] **Step 0(라이브): 페이지네이션 출력 형태 캡처**(P4-5 도그푸드).
- [ ] **Step 1: 실패 테스트** — 정상 JSON; exit≠0→`GitHostError`; exit 0 + malformed JSON→`GitHostError`; 빈 stdout→`GitHostError`; top-level 타입 불일치→`GitHostError`; `_api_paginated`가 2페이지 합침.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과(`cd WIP && py -3 -m pytest axdt/sot_gate/tests/test_hosts_github.py -v`) → 커밋** `feat(phase6): GitHubGatePorts 주입 + JSON/페이지네이션 헬퍼`.

---

## Task 1: verify_ruleset_config — 블록 파싱 + 블록 전량 값 대조

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_paginated`·`axdt-enforcement-matrix` 블록. Produces `verify_ruleset_config() -> bool` + 블록 파서.

**gh 매핑(스펙 §4.1·§8):** `rulesets` + `rulesets/{id}`. 블록을 파싱(코드 상수 금지)해 대조 규칙 5항목(매트릭스)을 **블록 전량 값 일치**로 검사.

- [ ] **Step 0(라이브): rulesets 응답 캡처**(도그푸드) — `enforcement` 상태 필드명·`rules[].parameters`·`bypass_actors` 경로 확인.
- [ ] **Step 1a: 파서 red** — 정상 블록 파싱; 매트릭스 fail-closed 거부 조건 전부(부재·중복·미종결·유효행0·미지원 version·중복 ID/필드·unknown 필드/룰/파라미터·필드 누락·placeholder 미해결/비수치·중복 룰/actor)→fail-closed.
- [ ] **Step 1b: 대조 red(캡처 fixture)** — 정상→`True`; **`enforcement: disabled`/`evaluate`→`False`**; `required_approving_review_count: 2`→`False`; `dismiss_stale_reviews_on_push: false`→`False`; **`require_last_push_approval: false`→`False`**; `allowed_merge_methods: ["squash"]`→`False`; RS-B `non_fast_forward`/`deletion` 누락→`False`; RS-B `bypass_actors` 있음→`False`; **RS-A `rules`가 `[update]` 아님→`False`**; **RS-A `bypass`에 추가 actor→`False`**; RS-A 부재/합쳐짐→`False`; RS-C 부재→`False`; RS-C `pull_request` 추가→`False`; RS-C `bypass` 비어있지 않음→`False`; **선언 외 추가 룰/actor/대상→`False`**; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): verify_ruleset_config — 블록 파싱 + 전량 값 대조`.

**라이브 확정 항목:** `rulesets` 필드 경로·`enforcement` 상태 필드는 Step 0 캡처로 확정(스펙 §8).

---

## Task 2: 룰셋 점검 배선 — 기동 + 매 머지 실패 경보·감사 (호스팅, P3-d)

**Files:** Modify `controller.py` 또는 호스팅 래퍼(P3-d); Test `test_controller.py` 또는 호스팅 테스트.

**규칙(스펙 §4.1·363행):** "기동 시와 매 머지의 직렬화 잠금 안에서" 점검하고 불일치 시 경보·감사. `controller.py:50-52` 유보, `merge_if_green`(115-117행)은 감사 없이 RED만 반환.

- [ ] **Step 0: 배선 위치·기동 실패 감사 스키마 결정(P3-d)** — 성공 머지 전용 `AuditRecord`와 별개로 PR/base 없는 기동 실패 감사 스키마·경보 sink 정의.
- [ ] **Step 1: 실패 테스트** — 기동 시 `verify==False`→머지 수용 전 차단 + 기동 실패 감사; **매 머지 점검 실패→경보 + 실패 감사**; `True`→정상 기동(부트스트랩: RS-A 미적용 시점엔 불일치 대기가 정상 — P4-4).
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과(회귀 152) → 커밋** `feat(phase6): 룰셋 점검 — 기동+매 머지 실패 경보·감사`.

---

## Task 3: read_pr_metadata — PR 메타데이터 + touches_sot (rename)

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §2.6·§8):** PR 조회 → `author`·`head_ref`·`head_repo`·`head_sha`·`state`. 변경 경로를 전 페이지 수집해 projection 교차→`touches_sot`. **rename 이전·이후 합집합**(구경로 projection 내면 삭제도 SoT 변경; Task 4 헬퍼 공유).

- [ ] **Step 0(라이브): PR 조회·변경분·rename 응답 캡처**(도그푸드).
- [ ] **Step 1: 실패 테스트** — 필드 매핑; SoT 변경→`True`; `README.md`만→`False`; **rename 구경로가 projection 내→`True`**; 2페이지 SoT 감지; state 매핑.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_pr_metadata — touches_sot(전 페이지·rename)`.

---

## Task 4: critical-paths 잠금 안 사전 관문 → touches_enforcement_surface (P3-e)

**Files:** Modify `hosts/github.py`(블록 읽기·glob·rename 합집합); Modify `controller.py` 또는 래퍼(P3-e 잠금 통합); Test `test_hosts_github.py`·`test_controller.py`.

**규칙(스펙 §7·506행):** `axdt-critical-paths` 블록을 **신뢰 base(`main`)**에서 읽는다. glob 의미 `protected-paths.md:50-53`. **rename 이전·이후 합집합**(근거 `protected-paths.md:48`; 블록 문법 절 56-59행엔 rename 의미 없어 red 이전 §8 결정·라이브 역기입). 블록 부재·기형·유효행0→`evaluate_gate` 이전 **잠금 안** 사전 관문에서 fail-closed RED(§7 (ㅁ) — 잠금은 `merge_if_green` 내부 controller.py:114, 래퍼 선택 시 잠금 통합).

- [ ] **Step 0: 잠금 통합 결정(P3-e)** + **Step 0b(라이브): base 블록 읽기(`contents/...?ref=main` base64) 캡처**.
- [ ] **Step 1: 파싱·매칭 red** — 파싱; glob 매칭; rename 이전 경로 critical→매칭; 부재/기형→예외.
- [ ] **Step 2: 관문 배선 red** — 블록 못 읽으면 잠금 안 fail-closed RED; enforcement_surface만 참 PR이 포크 거부+결정권자 승인 통과/차단.
- [ ] **Step 3~5: 실패 확인 → 구현 → 통과(회귀 152) → 커밋** `feat(phase6): critical-paths 잠금 안 사전 관문 + glob(rename)`.

---

## Task 5: read_channel_decisions — 코멘트 + role_name + 사람 판별 + 버전 스탬프

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §2.7·§4.1·§8):** `issues/{n}/comments`(전 페이지) → 구조화 코멘트 → `ChannelDecision`. `author_role`=`collaborators/{login}/permission`의 `role_name`. `author_is_human`=공통 identity resolver(판별불능→`False`). **버전된 스탬프 문법**(필드명·version·완전 결속 키·accepted/rejected)을 **먼저 승인·게시**한 뒤 사람이 실제 코멘트를 생성해 round-trip 캡처(스펙 98행은 개념만). unknown version·중복 필드·부분 키는 **한 규칙으로 고정**(무시 또는 fail-closed 중 택일 확정).

- [ ] **Step 0: 스탬프 문법 승인·게시 → 라이브 코멘트·permission·계정유형 응답 캡처**(round-trip).
- [ ] **Step 1: 실패 테스트** — 구조화 코멘트→매핑; `updated_at != created_at`→편집; `role_name`→`author_role`; 사람→`True`·봇→`False`·판별불능→`False`; unknown version·중복·부분 키·기형→고정 규칙대로; 비구조화 무시; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_channel_decisions — role_name·사람 판별·버전 스탬프`.

---

## Task 6: read_approvals — 스트림 전량 + 두 키(라이브 결정) + dismissed·무효 보존

**Files:** Modify `hosts/github.py`(+ P3-b/P3-f에 따라 `ports.py`·`models.py`·생성자); Test `test_hosts_github.py`.

**gh 매핑(스펙 §2.3·§8):** `pulls/{n}/reviews`(전 페이지) → 승인 스트림 **전체**를 `ApprovalEvent`로 반환. 유효성은 게이트가 판정, 포트는 필터링 안 함(`ports.py:51-55`). `dismissed`도 `dismissed=True`로 전량 반환. `approver_role`·`approver_is_human`은 Task 5와 같은 공통 resolver.

- [ ] **Step 0: 두 키 취득·무효 표현 라이브 결정(P3-b/f)** — (ㄱ) base 복원(감사·first-parent resolver 주입) / (ㄴ) 구조화 스탬프. **무효 표현**은 임의 센티널·임의 제외 대신 P3-f 모델 개정(`stamp_valid` 또는 optional raw stamp)으로 — SoT 완료 분기만 두 키 존재·일치 요구, 강제-필수 경로 분기(키 불요)는 승인 유지. reviews·스탬프 응답 캡처.
- [ ] **Step 1: 실패 테스트(결정 후)** — 전량 반환(대표 선정 금지); dismissed→`dismissed=True`; approver 사람/봇/판별불능(`False`); (ㄴ) 두 키 스탬프 **하나라도 빠지면** `stamp_valid=False`(단일 스탬프도 무효), 둘 다 있으면 유효; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_approvals — 전량+dismissed·무효(stamp_valid)+두 키`.

---

## Task 7: read_ci_artifacts — 조회 + 쓰기 신뢰 통제

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §4.2·§8):** 두 신뢰 산출물을 산출물 저장소에서 읽는다(커밋 상태 금지). 없거나 파싱 실패→`None`(fail-closed). **쓰기 신뢰 모델이 진짜 방어선** — 신뢰된 ② CI 신원만 쓸 수 있어야(ACL/서명; 스펙 401·521행).

- [ ] **Step 0(라이브): 저장 위치·형식·쓰기 통제 선택·실증**.
- [ ] **Step 1: 실패 테스트** — 정상→매핑; 정합성만→`(a, None)`; 파싱 실패→`None`; `FullBindingKey` 매핑; **위조 산출물·잘못된 서명·일반 PR 신원 쓰기→fail-closed** 음성 시험.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_ci_artifacts — 산출물 + 쓰기 신뢰·음성 시험`.

---

## Task 8: merge_pull_request — head 고정 머지 + SHA + base 취득 (P3-a/c)

**Files:** Modify `hosts/github.py`·`ports.py`(ABC 시그니처·docstring)·`ports.py`의 `FakeGatePorts`·`controller.py`(감사)·Test `test_hosts_github.py`·`test_ports.py`·`test_controller.py`.

**Interfaces:** Produces **`merge_pull_request(...) -> str`(머지 커밋 SHA)** — §2.9 확정 `None→str`. `MergeResult(merge_sha, base_sha)` 구조체 반환은 §2.9 문면(반환만 확장)을 넘어서므로 **채택 시 별도 §2.9 스펙 개정 필요**(P3 승인만으로는 부족); 기본은 `-> str` 유지 + first-parent resolver를 P3-c 별도 계약.

**gh 매핑(스펙 §2.5·§2.9·§8):** `PUT .../merge`, `merge_method=merge`, `sha={head_sha}`(스냅샷, 재조회 금지). 응답의 머지 커밋 SHA 반환. `AuditRecord.base`=first-parent는 머지 응답에 없어 P3-c로 취득(커밋 `commits/{sha}` parents[0] 등) + **머지 성공 후 조회·감사 쓰기 실패 시 durable retry/outbox**. head 이동→`HeadMovedError`.

- [ ] **Step 0(라이브): merge 응답·거부 코드·payload·parent 조회 캡처** — `405`는 승인 부족(실증, 매트릭스)에도 나므로 **HTTP 코드 + 오류 payload/message를 함께** 캡처해 head SHA 불일치만 `HeadMovedError`로, 승인·룰셋 위반은 `GitHostError`로 분리.
- [ ] **Step 1: 실패 테스트** — 정상 머지→argv + 반환=머지 SHA; head 불일치(코드+payload)→`HeadMovedError`; 승인 부족 `405`→`GitHostError`(오분류 금지); `FakeGatePorts`가 SHA 반환; 컨트롤러 감사 `base`=first-parent; **머지 성공 후 감사 쓰기 실패→retry/outbox** 음성 시험; `test_ports` 반환형 회귀.
- [ ] **Step 2~5: 실패 확인 → 구현(`None→str`: github·ports ABC·Fake·controller·test_ports) → 통과 → 커밋** `feat(phase6): merge_pull_request None→str(§2.9) + base 취득·감사 복구`.

---

## Task 9: compute_landing_keys — 두 키 + trusted epoch + 공유 정규화 + 골든 벡터

**Files:** Modify `hosts/github.py`; **Create 공유 canonical calculator 모듈**(record-set/합성 키 계산기 — ② CI·컨트롤러 공유); Test `test_hosts_github.py`·신규 conformance 테스트.

**Interfaces:** Consumes `_api_json` + trusted epoch provider + 공유 계산기. Produces `compute_landing_keys(pr) -> tuple[JudgmentKey, CompletenessSweepKey]`.

**규칙(스펙 §2.3·§4.2, `sot-readiness.md` 32·35·41·42·46·49·52·53·55행):**
- 제안 머지 결과에서 두 키 계산. **신뢰 base에서 읽는 것 = 실행기(하니스·`sot-lint`·판정 키 계산기)뿐**; **완료 규칙·검토 스킬 내용은 후보 정책이므로 머지 결과에서 해시해 epoch에 결속**(규칙 52·55행 — 계획 이전 판의 "정책=base"는 오류였고 삭제).
- `review_policy_epoch` = trusted 환경 성분(모델 revision·실행기 revision·프롬프트·추론 설정; 규칙 41·46행)을 **trusted epoch provider**가 공급 + 완료 규칙·검토 스킬 digest(머지 결과)를 조립.
- **공유 정규화 계산기 신설 필수**: `keys.py`의 기존 정규화는 finding digest용(ASCII 길이+US 프레이밍, `keys.py:58-87`)이라 규칙의 record-set(uint32 big-endian 프레이밍·합성 키 태그·순서)과 **다르다**. ② CI와 공유할 canonical calculator를 새 모듈로 만들고 규칙 42행의 **골든 벡터(preimage 바이트 + 기대 hex)**로 고정(Phase 6 conformance).
- 적용 rule = active global + 선언된 active local(규칙 32행); 완전성 입력 = **active rule 전량**(규칙 35행).

- [ ] **Step 0(라이브): 제안 머지 결과 취득 방법·trusted epoch provider 확정 + 골든 벡터 산출**.
- [ ] **Step 1: 실패 테스트(테스트표 분리)** — 결정성; projection 트리 변경→두 키 모두; **`active+적용(선언 active local)` rule 본문 편집→판정 키·완전성 키 모두**; **`active+미선언 active local` rule 본문 편집→완전성 키만**(규칙 35행); **`deprecated/superseded`(inactive) rule 본문 편집→어느 키도 불변**; **`active↔inactive 전이`→manifest(판정 키)·active 입력(완전성 키) 모두 변경**(규칙 53행); 검토 스킬·완료 규칙(후보) 편집→두 키 모두; `review_policy_epoch`(실행기 revision) 변경→두 키 모두; 활성 카탈로그 입력 digest→완전성 키만; **골든 벡터 preimage·hex 일치·경로 NFC·내용 비-NFC·BOM 1회 제거·CRLF/단독 CR·종단 개행·UTF-8 실패·uint32 프레이밍·raw-digest 합성**; README/_TEMPLATE 제외.
- [ ] **Step 2~5: 실패 확인 → 구현(공유 계산기 + 골든 벡터) → 통과 → 커밋** `feat(phase6): compute_landing_keys — 공유 정규화·trusted epoch·골든 벡터`.

---

## 라이브 스모크 (Phase 9, 계약 테스트 뒤 — P4 순서)

전제조건 P1~P4 확인 후 P4-4 순서로 활성화하고, 확정 스키마로 각 Task "라이브 확정 항목"을 메꿔 provisional 표기를 제거한다. **`ADR-0009`만 이 계획의 몫으로 proposed→accepted로 올린다**; `ADR-0007`은 "허브 콘텐츠·경로 게이트 CODE(Phase 3) 착지" 조건이라(`ADR-0009:15`) Phase 6/9만으론 승급하지 않고 그 조건 충족 시 별도 승급한다. Task 3·4의 rename 합집합 등 정본에 명문 근거가 얇은 세부의 **정본 역기입(`docs/sot/rule/**`)은 사용자 게이트 SoT PR로** 한다(그 경로는 사용자 게이트 전용, `protected-paths.md:27`).

## Self-Review (계획 대 스펙)

- **스펙 커버리지**: 7개 포트 Task 1·3·5~9, 두 사전 관문 Task 2·4; 선행 P1~P4로 정본 개정·동결 확장·§7 전제·활성화 순서 명시.
- **provisional 명시**: 포트 Task마다 Step 0(라이브 캡처/결정)과 "라이브 확정 항목"으로 §8 목록을 조기 동결 없이 표기; 헬퍼·배선 Task는 Step 0 대상이 다름을 명시.
- **동결 계약 존중**: 동결 변경(Task 2·4·6·8·9 resolver·머지 반환형·두 키 모델)을 P3 (a)~(f)에 전부 열거해 승인/래퍼 결정 선행; `MergeResult`는 §2.9 개정 필요를 명기.
- **정본 정합**: 검토 스킬=머지 결과(규칙 55행), 미선언 active local vs inactive 구분(규칙 35·53행), 감시 범위=블록 전량(P2 정본 개정 전제).
