# Phase 6 강제 게이트 실행부(GitHubGatePorts) 라이브 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **착수 시점 = Phase 9 (라이브 도그푸딩).** 모든 Task는 실제 GitHub 저장소·`gh` CLI 응답을 봐야 스키마가 확정되는 provisional 구현이다(스펙 §1 비목표·§8·§9). **P1~P3는 구현 착수의 전제**(정본 개정·동결 계약 확장 승인), **P4는 코드 이후의 활성화 절차**(exit criteria + 순서)다. 순수 코어(`gate.py`·`keys.py`·`models.py`)·포트 계약(`ports.py`)·머지 컨트롤러(`controller.py`)의 시그니처·데이터 모델·기존 동작은 동결이며, 동결을 바꾸는 항목은 모두 P3의 승인 대상으로 열거한다(조용한 변경 금지).

**Goal:** `hosts/github.py`의 7개 포트를 실제 `gh api` 호출로 구현하고, 룰셋 점검·`axdt-critical-paths` 두 사전 관문을 컨트롤러 층에 배선한다. ② 검토 CI 생산자·정본 개정·마이그레이션 실행은 이 계획 밖의 Phase 9 선행조건으로 명시한다(P3·P4).

**Architecture:** `github.py`는 `git_host`의 `CommandBackend`(ABC)를 주입받아 gh 호출을 격리하고(subprocess 직접 호출 금지), (b) 클라이언트의 adapter+backend 분리를 계승한다. 각 포트는 gh 응답 JSON을 파싱해 순수 코어 계약(`models.py`·`keys.py`)으로 매핑한다. 포트는 원시 사실만 채우고 결정권 논리곱은 순수 코어가 계산한다.

**Tech Stack:** Python 3(`py -3`), `gh` CLI, pytest. 재사용: `axdt.git_host.backend.{CommandBackend,FakeCommandBackend,SubprocessBackend}`, `axdt.git_host.models.{PullRequest,CommandResult,GitHostError}`. **pytest 기준 디렉터리 = `WIP`**: `cd WIP && py -3 -m pytest axdt/sot_gate/...`.

## 착수 전제 P1~P3 (구현 착수 전 필수)

정본 개정·동결 계약 확장을 포함해 이 계획의 라이브 코드 범위를 벗어난다(사용자 게이트/별도 승인).

- **P1. 정본 규칙·ADR 드리프트 정정(사용자 게이트 SoT PR).**
  - (ㄱ) `sot-readiness.md` 92·105행의 "`sot/*` 보호 불요/요구하지 않음"을 `ADR-0009` 결정 8 개정(RS-C 요구)·스펙 §4.1에 맞춘다 — 개정 전 활성화 시 규칙과 `verify_ruleset_config`가 반대를 가리켜 모든 머지가 막힌다.
  - (ㄴ) **`ADR-0009` 2키 내부 드리프트** — 결정 3(단일 판정 키, ADR:41)·결정 4(신선성을 "착지하는 판정 키" 단수로, ADR:43)·결정 9(단일 키·축소 감사, ADR:53)·결정 10("축3 스윕", ADR:55)과 대가/주의(ADR:88 "판정 키 대조는 재전송 방지")가 개정 전 단일키 문면으로 남아 스펙의 2026-07-17 2키 개정(판정 키 4성분 + 완전성 스윕 키·착지 두 키 삼자 일치·base SHA 포함 감사·별도 선언 완전성 마이그레이션)과 어긋난다. **ADR 전체에서 구 단일키 문면을 함께 스윕**해 현 2키 계약에 맞춘 뒤에만 `ADR-0009`를 `accepted`로 승급한다.
- **P2. `verify_ruleset_config` 감시 범위 정본 개정(필수).** 매트릭스가 기계판독 블록 **전량**을 값 일치로 대조하므로(§4.1 감시 열거보다 넓음), 정본 §4.1 감시 열거·**§8 522행**·**§10 요약(547행)**·§3 `verify_ruleset_config` 계약·`ports.py` docstring(스텁 docstring은 Task 1 구현 시 자연 갱신)을 이 블록에 맞추는 개정이 선행돼야 한다. (초과 감시는 fail-closed 강화라 개정 전에도 안전하나 정합을 위해 필수 전제.)
- **P3. 동결 계약 확장 승인(별도 승인 — 아래 전부).** 착수 전 승인받거나 동결 코어 밖 호스팅 래퍼에 둘지 결정한다.
  - (a) `merge_pull_request`의 `-> None → -> str`(§2.9 확정, Task 8).
  - (b) 두 키 취득 (ㄱ) base 복원 시 컨트롤러 감사·first-parent 이력 resolver 주입 계약(Task 6·9).
  - (c) `AuditRecord.base` first-parent SHA 취득 + **영속 intent/audit store 계약** — 현 감사 로그는 프로세스 메모리 리스트(controller.py:59)라 §2.9의 과거 base 복원용 불변 기록도, 재기동 reconcile도 만족 못 한다. **영속 저장소**(상태 전이: intent→머지→감사 append; intent에 **저장소·PR·head SHA + 평가 base·착지 두 키·감사 스냅샷을 결속** — 같은 PR/head라도 base가 전진하면 제안 머지 결과·착지 두 키가 달라져 과거 intent를 재사용할 수 없음)를 확정한다. reconcile는 재기동 스캔뿐 아니라 **결과 불명 오류 직후·새 머지 수용 전에도** 수행하고(원격 머지 성공했으나 `gh` 응답만 유실된 경우 감사 누락 방지), **pending intent 해소 전에는 후속 머지를 차단**한다. Task 8 파일/테스트·P4 운영 exit에 저장소를 넣는다.
  - (d) **Task 2 기동 점검·경보·실패 감사** — `controller.py:50-52` 유보 동작 변경. 성공 머지 전용 `AuditRecord`(controller.py:21-40)와 별개로 PR/base 없는 기동 실패 감사 스키마·경보 sink.
  - (e) **Task 4 잠금 안 사전 관문** — critical-paths 판독 실패 RED 신호를 컨트롤러 계약에 넣거나(§7 (ㅁ) "잠금 안", 잠금은 controller.py:114), 래퍼로 둘 경우 잠금 통합.
  - (f) **두 키 무효 표현 모델 개정(Task 6)** — 두 키 non-optional(`models.py:64-65`)이라 tagged union(유효 스탬프 vs 원시 결손) 또는 키 `Optional`+`stamp_valid` 불변식(None → 착지 키 불일치 → RED)을 택한다. 파급: `ApprovalEvent`·생성자·`gate.py`(소비 시)·`test_gate.py`·`FakeGatePorts`·강제-필수 분기(키 불요, 스펙 92행). optional 키는 코어 무변경, tagged union은 코어 소비 필요 — 선택 시 파일 목록 확정.
  - (g) **감사 내용 계약 불일치** — 스펙 116행 "머지에 반영된 결정 스냅샷" vs 동결 컨트롤러의 관측 결정 전량 append(controller.py:27·148). 정본을 "관측 전량"으로 바꾸거나 코어가 실제 winner/승인을 한 번 산출해 감사에 전달(컨트롤러 판정 재구현 금지).
  - (h) **컨트롤러 운영 계약** — 프로세스 로컬 `threading.Lock`(controller.py:58) 대신 **singleton 배포 보장 또는 프로세스 간 lease/분산 잠금** + 다중 worker 음성 시험, 저장소 밖 allowlist 초기값·변경 감사·주입 경로(§8 526행).

## Global Constraints

- **라이브 스키마 캡처 우선 (조기 동결 금지)**: 각 포트 Task는 Step 0으로 라이브 응답을 캡처·확인한 뒤 그 캡처로 red를 쓴다(스펙 §1·§8). 캡처는 P4의 도그푸드 셋업에서. (헬퍼 Task 0·배선 Task 2·4는 캡처 대상이 달라 각 Task가 명시.)
- **페이지네이션**: 목록 응답은 Task 0 헬퍼로 전 페이지 수집, 각 포트에 다중 페이지 red. 뒤 페이지 누락은 `touches_*` 오판이라 fail-closed상 필수(스펙 §2.6·§7).
- **동결 계약 확장 규약**: 동결 시그니처·동작을 바꾸는 Task는 P3에서 승인/래퍼 결정을 선행.
- **provisional 경계**: gh api 스키마·산출물 저장·제안 머지 결과 취득·두 키 취득·사람 판별·코멘트 삭제 감지·룰셋 TOCTOU·직렬화 잠금은 §8 미확정. Step 0 실측 전 동결 금지(스펙 §8·§10).
- **테스트 경계**: 순수 코어·컨트롤러 테스트는 `FakeGatePorts`(회귀 152 유지). `github.py`는 `FakeCommandBackend`(스펙 §6).
- **승인 두 키 재계산 금지**: **승인** 두 키(`approved_judgment`·`approved_completeness`)는 §2.3 (ㄱ)/(ㄴ)로 취득하고 머지 시점 재계산하지 않는다(스펙 54행). **착지** 두 키는 머지 직전 매 평가 신선 재계산이 정본이다(스펙 67행 신선성) — 이 금지 대상이 아니다.
- **포트는 판정하지 않는다**: `role_name`·사람 여부·`dismissed`·`deleted`·`stamp_valid` 등 원시 사실만 채우고, 판정(결정권 논리곱·유효성)은 코어(스펙 §2.7·§3·§2.6 항목10). 포트는 `allowlist`를 받지 않는다(`ports.py:45`).
- **사람/기계 판별(§2.7·§8)**: 공통 identity resolver로 author·approver 양쪽 채우고 판별불능→`False`(코어 fail-closed).
- **선언 단일 진실원**: 룰셋 대조 값은 `ENFORCEMENT_MATRIX.md`의 `axdt-enforcement-matrix` 블록(신뢰 컨트롤러 배포본). `verify_ruleset_config`가 블록 전량을 값 일치로 대조(손사본 금지, Task 1).

---

## Task 0: CommandBackend 주입 + gh api JSON/페이지네이션 헬퍼

**Files:** Modify `hosts/github.py`; Test `tests/test_hosts_github.py`(신규).

**Interfaces:** Consumes `CommandBackend`·`FakeCommandBackend`·`GitHostError`. Produces `GitHubGatePorts(backend, repo, ...)`; `_api_json(*args) -> dict|list`(exit≠0·malformed JSON·빈 stdout·top-level 타입 불일치 → `GitHostError`); `_api_paginated(*args) -> list`.

- [ ] **Step 0(라이브): 페이지네이션 출력 형태 캡처**(도그푸드).
- [ ] **Step 1: 실패 테스트** — 정상 JSON; exit≠0·malformed·빈 stdout·타입 불일치 → `GitHostError`; `_api_paginated` 2페이지 합침.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과(`cd WIP && py -3 -m pytest axdt/sot_gate/tests/test_hosts_github.py -v`) → 커밋** `feat(phase6): 주입 + JSON/페이지네이션 헬퍼`.

---

## Task 1: verify_ruleset_config — 블록 파싱 + 블록 전량 값 대조 + actor 결합

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §4.1·§8):** `rulesets` + `rulesets/{id}`. 블록 파싱(코드 상수 금지)해 대조 규칙 5항목(매트릭스, `enforcement=active`·`require_code_owner_review=false` 포함)을 블록 전량 값 일치로 검사.

- [ ] **Step 0(라이브): rulesets 캡처 + 결정** — (i) `enforcement`·`rules[].parameters`·`bypass_actors` 필드 경로; (ii) actor ID 획득(신뢰 구성 주입 vs 토큰 `/user`); (iii) 라이브 룰셋→선언 대응 식별(이름 vs 구조); (iv) 정본 파라미터 투영 vs API 부가 기본 필드 규칙; (v) **룰셋 TOCTOU 대응**을 §8 522행의 **두 보장**(변경 이벤트 감시 / 머지 직후 재확인) 중 하나로 채택한다 — 정본(스펙 363행)의 현행 자세는 "TOCTOU 창은 잔여 위험이며 다음 머지 점검이 사후 검출"이므로, 두 보장으로 좁히는 것은 **계획 차원의 fail-closed 강화**다(정본 금지가 아니라 강화; 정본 수준으로 올리려면 P2 개정에 §4.1 363행 문면 정합을 연결). 선택 결과가 이벤트 서비스·컨트롤러/래퍼 변경이면 구현 위치·실패 시험·필요한 P3 동결 변경을 연결한다.
- [ ] **Step 1a: 파서 red** — 정상 파싱; 매트릭스 fail-closed 거부 조건 전부.
- [ ] **Step 1b: 대조 red** — 정상→`True`; `enforcement: disabled`/`evaluate`→`False`; 승인수 2·dismiss-stale false·`require_last_push_approval` false·`require_code_owner_review` true·squash→각 `False`; RS-B `non_fast_forward`/`deletion` 누락→`False`; RS-B bypass 있음→`False`; RS-A `rules`≠`[update]`·bypass 추가/다른 actor→`False`; RS-A 부재/합쳐짐→`False`; RS-C 부재·`pull_request` 추가·bypass 비어있지 않음→각 `False`; 선언 외 추가→`False`; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): verify_ruleset_config — 블록 전량 대조 + actor`.

---

## Task 2: 룰셋 점검 배선 — 기동 + 매 머지 실패 경보·감사 (호스팅, P3-d/h)

**Files:** Modify `controller.py` 또는 래퍼(P3-d/h); Test `test_controller.py` 또는 호스팅 테스트.

- [ ] **Step 0: 배선 위치·기동 실패 감사 스키마·경보 sink·직렬화 보장 결정(P3-d/h)**.
- [ ] **Step 1: 실패 테스트** — 기동 시 `verify==False`→차단 + 기동 실패 감사 + 경보; 매 머지 점검 실패→경보 + 실패 감사; `True`→정상 기동(부트스트랩 불일치 대기 정상); 다중 worker→단일 직렬화 음성 시험.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과(회귀 152) → 커밋** `feat(phase6): 룰셋 점검 — 기동+매 머지 경보·감사·직렬화`.

---

## Task 3: read_pr_metadata — PR 메타데이터 + touches_sot (rename)

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

- [ ] **Step 0(라이브): PR 조회·변경분·rename 캡처**(도그푸드).
- [ ] **Step 1: 실패 테스트** — 필드 매핑; SoT 변경→`True`; `README.md`만→`False`; rename 구경로 projection 내→`True`; 2페이지 SoT 감지; state 매핑.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_pr_metadata — touches_sot(전 페이지·rename)`.

---

## Task 4: critical-paths 잠금 안 사전 관문 → touches_enforcement_surface (P3-e)

**Files:** Modify `hosts/github.py`; Modify `controller.py` 또는 래퍼(P3-e); Test `test_hosts_github.py`·`test_controller.py`.

**규칙(스펙 §7·506행):** `axdt-critical-paths` 블록을 신뢰 base(`main`)에서 읽는다. glob `protected-paths.md:50-53`. rename 이전·이후 합집합(근거 `protected-paths.md:48`; 블록 문법 절엔 rename 의미 없어 정본 역기입은 사용자 게이트). 블록 부재·기형·유효행0→`evaluate_gate` 이전 잠금 안 fail-closed RED(§7 (ㅁ)).

- [ ] **Step 0: 잠금 통합 결정(P3-e)** + **Step 0b(라이브): base 블록 읽기(base64) 캡처**.
- [ ] **Step 1~2: 파싱·매칭 red + 관문 배선 red** — glob·rename 매칭; 부재/기형→잠금 안 RED; enforcement_surface만 참 PR이 포크 거부+결정권자 승인 통과/차단.
- [ ] **Step 3~5: 실패 확인 → 구현 → 통과(회귀 152) → 커밋** `feat(phase6): critical-paths 잠금 안 관문 + glob(rename)`.

---

## Task 5: read_channel_decisions — 코멘트 + role_name + 사람 판별 + 삭제 감지 + 버전 스탬프

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §2.7·§4.1·§8):** `issues/{n}/comments`(전 페이지) → 구조화 코멘트 → `ChannelDecision`. `author_role`=`role_name`. `author_is_human`=공통 resolver(판별불능→`False`). 편집·삭제 흔적 채움. 버전된 스탬프 문법을 **먼저 승인·게시** 후 round-trip 캡처.

- [ ] **Step 0: 스탬프 문법 승인·게시 → 코멘트·permission·계정유형 캡처 + 삭제 감지 결정** — §8 519행: 삭제를 현재 스냅샷 부재로 처리 vs 이벤트/tombstone으로 `deleted=True` 복원 중 택일.
- [ ] **Step 1: 실패 테스트** — 구조화 코멘트→매핑; `updated_at != created_at`→편집; 삭제→결정 방식대로(round-trip); `role_name`→`author_role`; 사람/봇/판별불능(`False`); **기형 스탬프(unknown version·중복 필드·부분 키·키/결정 미파싱)는 작성자 무관하게 비구조화로 무시**(포트는 `allowlist`가 없어 작성자 자격을 모르므로 자격별 처리 금지 — 스펙 99행 판정은 코어 몫). 무시해도 fail-open 없음: 기형이 닫아야 했던 blocking은 §2.6 항목8 미대조로 코어가 RED, 결정권자는 올바른 스탬프를 새로 단다. (유자격 기형에 fail-closed가 필요하면 기형 원시 사실을 코어로 나르는 모델·포트 확장을 P3 신설 — 현재는 일괄 무시로 통일.) 비구조화 무시; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_channel_decisions — 삭제 감지·기형 일괄 무시·버전 스탬프`.

---

## Task 6: read_approvals — 스트림 전량 + 두 키(라이브 결정) + dismissed·무효(P3-f)

**Files:** Modify `hosts/github.py`(+ P3-b/f 파일); Test `test_hosts_github.py`.

- [ ] **Step 0: 두 키 취득·무효 표현 라이브 결정(P3-b/f)** — (ㄱ) base 복원(resolver) / (ㄴ) 구조화 스탬프. 무효 표현은 P3-f 모델 개정(tagged union 또는 optional 키+`stamp_valid`)으로(임의 센티널 금지). reviews·스탬프 캡처.
- [ ] **Step 1: 실패 테스트** — 전량 반환(대표 선정 금지); dismissed→`dismissed=True`; approver 사람/봇/판별불능(`False`); (ㄴ) 두 키 스탬프 하나라도 결손→무효 표현(단일 스탬프도 무효), 둘 다 있으면 유효; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_approvals — 전량+dismissed·무효(P3-f)+두 키`.

---

## Task 7: read_ci_artifacts — 조회 + 쓰기 신뢰 통제

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §4.2·§8):** 두 신뢰 산출물을 산출물 저장소에서 읽는다(커밋 상태 금지). 없거나 파싱 실패→`None`. 쓰기 신뢰 모델이 진짜 방어선(ACL/서명; 스펙 401·521행). **이 Task는 산출물 독자만 구현한다 — 산출물을 쓰는 ② CI 생산자는 P4-3 선행조건이다.**

- [ ] **Step 0(라이브): 저장 위치·형식·쓰기 통제 선택·실증**(② CI 생산자와 형식 합의).
- [ ] **Step 1: 실패 테스트** — 정상→매핑; 정합성만→`(a, None)`; 파싱 실패→`None`; `FullBindingKey` 매핑; 위조 산출물·잘못된 서명·일반 PR 신원 쓰기→fail-closed 음성 시험.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_ci_artifacts — 쓰기 신뢰·음성 시험`.

---

## Task 8: merge_pull_request — head 고정 머지 + SHA + base 취득 + 멱등 복구 (P3-a/c/g)

**Files:** Modify `hosts/github.py`·`ports.py`(ABC·docstring)·`FakeGatePorts`·`controller.py`(감사) + P3-c 영속 store; Test `test_hosts_github.py`·`test_ports.py`·`test_controller.py`.

**Interfaces:** Produces **`merge_pull_request(...) -> str`** — §2.9 확정 `None→str`. `MergeResult(merge_sha, base_sha)`는 §2.9 문면 초과라 채택 시 별도 §2.9 개정 필요.

**gh 매핑(스펙 §2.5·§2.9·§8):** `PUT .../merge`, `merge_method=merge`, `sha={head_sha}`. 응답 머지 커밋 SHA 반환. `AuditRecord.base`=first-parent는 P3-c로 취득 + **머지 전 durable intent(영속 store) → 재기동 시 PR/head SHA 멱등 키로 원격 결과 reconcile**. head 이동→`HeadMovedError`. 감사 내용은 P3-g 결정.

- [ ] **Step 0(라이브): merge 응답·거부 코드·payload·parent 캡처** — `405`가 승인 부족(실증)에도 나므로 HTTP 코드 + payload 함께 캡처해 head SHA 불일치만 `HeadMovedError`, 승인·룰셋 위반은 `GitHostError`.
- [ ] **Step 1: 실패 테스트** — 정상 머지→argv + 반환=머지 SHA; head 불일치→`HeadMovedError`; 승인 부족 `405`→`GitHostError`; `FakeGatePorts` SHA 반환; 감사 `base`=first-parent; **머지 전 intent 영속 기록 후 프로세스 종료→재기동 reconcile**(중복 머지·유실 없음) 음성 시험; `test_ports` 회귀.
- [ ] **Step 2~5: 실패 확인 → 구현(`None→str`: github·ports·Fake·controller·test_ports·영속 store) → 통과 → 커밋** `feat(phase6): merge None→str(§2.9) + base·영속 멱등 복구`.

---

## Task 9: compute_landing_keys — 두 키 + trusted epoch + 공유 정규화 + 골든 벡터

**Files:** Modify `hosts/github.py`; **Create 공유 canonical calculator 모듈**(`WIP/axdt/sot_gate/**` critical glob 안 + 실행기 manifest (a) 등재·변경 측 통보, `protected-paths.md:75`); Test `test_hosts_github.py`·신규 conformance 테스트.

**규칙(스펙 §2.3·§4.2, `sot-readiness.md` 32·35·41·42·43·46·49·50·52·53·55·56행):**
- 신뢰 base = 실행기(하니스·판정 키 계산기)만; 완료 규칙·검토 스킬 내용은 후보 정책이라 머지 결과에서 해시해 epoch에 결속(규칙 52·55행).
- **manifest (a)/(b) 경계**: epoch에 넣는 것은 실행기 revision **(a)만**(규칙 50행). **`sot-lint`는 (b) 보호 전용**이라 epoch에 안 넣는다(규칙 56행) — (a)/(b) 변경의 키 변화 분리 시험.
- `review_policy_epoch` = trusted 환경 성분(모델·실행기 revision·프롬프트·추론; 규칙 41·46행)을 trusted epoch provider가 공급 + 완료 규칙·검토 스킬 digest(머지 결과) 조립.
- **공유 정규화 계산기 신설 필수**: `keys.py` 기존 정규화는 finding digest용(ASCII 길이+US, `keys.py:58-87`)이라 규칙의 record-set(uint32 big-endian·합성 키 태그·순서, 규칙 43행)과 다르다. ② CI와 공유할 계산기를 새 모듈로 만들고 규칙 42행 골든 벡터(preimage 바이트 + 기대 hex, 키별 태그·성분 순서 분리)로 고정.
- 적용 rule = active global + 선언된 active local(규칙 32행); 완전성 입력 = active rule 전량(규칙 35행).

- [ ] **Step 0(라이브): 제안 머지 결과 취득·trusted epoch provider 확정 + 골든 벡터 산출**.
- [ ] **Step 1: 실패 테스트(테스트표 분리)** — 결정성; projection 트리 변경→두 키 모두; active+적용 본문→판정 키·완전성 키 모두; active+미선언 active local 본문→완전성 키만(규칙 35행); deprecated/superseded 본문→어느 키도 불변; active↔deprecated/superseded 전이→manifest(판정)·active 입력(완전성) 모두(규칙 53행; `inactive`는 상태값이 아니라 `deprecated`/`superseded`가 허용 status); 검토 스킬·완료 규칙 편집→두 키 모두; 실행기 revision (a) 변경→두 키 모두 / `sot-lint` (b) 변경→키 불변; 활성 카탈로그 입력 digest→완전성 키만; 골든 벡터 preimage·hex·키별 태그·순서; **fail-closed 값 도메인(규칙 42행 — 오타 값이 적용·활성 집합에서 조용히 빠지는 fail-open 차단) — `scope` 부재·null→`global` 정규화; 정규화 후 `scope`∉{local,global}·`status`∉{active,deprecated,superseded}·`id` 규약 위반(빈 문자열·오타 `globla`/`activ` 포함)→오류; 비문자열 `scope`(리스트·맵)도 기형 오류; `path`는 값 도메인 제약 없이 기형만 오류**·uint32 초과; NFC 정규화 후 같아지는 두 경로 공존→fail-closed; 경로 NFC·내용 비-NFC·BOM 1회·CRLF/단독 CR·종단 개행·UTF-8 실패·uint32 프레이밍·raw-digest 합성; README/_TEMPLATE 제외.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): compute_landing_keys — 공유 정규화·(a)/(b) 경계·값 도메인·골든 벡터`.

---

## P4. Phase 9 활성화 (코드 이후 — exit criteria + 순서 + rollback)

전제조건 P1~P3 처리 + 아래 exit 확인 후 순서대로 활성화한다.

- **P4-1 (exit) 인프라**: 저장소 public·컨트롤러 신원·최소 권한 토큰·**P3-c 영속 store 배치**(`ADR-0009` 결정 1·12).
- **P4-2 (exit) critical 블록 착지**: `axdt-critical-paths`가 신뢰 base(`main`)에 착지·파싱 가능(실행기 manifest 경로 — Task 9 신설 계산기 포함 — · 허브 게이트 실행 폐쇄 전체 등재, `protected-paths.md:71-75·91-93`; 스펙 §7 (ㅁ)).
- **P4-3 (exit) ② 검토 CI 생산자 준비**: **이 계획 밖의 별도 Phase 9 산출물** — **각 검토를 자기 키당 1회** 실행하는 CI 워크플로(판정 키가 바뀌면 정합성 검토만, 완전성 스윕 키가 바뀌면 완전성 검토만; 스펙 396·398행). **없으면 SoT PR이 산출물 `None`으로 계속 RED이므로 활성화 필수 선행조건.** exit로 확인할 것: 키별 발화·키당 1회 재사용·두 산출물 형식(Task 7 독자와 합의)·쓰기 신뢰(신뢰 CI 신원)·종단 round-trip. **`ConsistencyArtifact.format_ok`의 ① 결정적 검사(`sot-lint`)는 현재 제안 머지 결과에 대해 별도로 신선 실행해 정합성 산출물에 조립**한다 — `sot-lint`는 (b) 보호 전용이라 두 키를 안 바꾸므로(Task 9), ① 결과를 LLM 검토 키 캐시에 묶으면 낡은 `format_ok`가 재사용된다(스펙 60·396행, `sot-readiness.md:56`).
- **P4-4 (활성화 순서)**: 워크플로 전제 실증(force-push 미사용) → **RS-C 적용** → RS-B 적용 → 컨트롤러 배포(저장소 밖이라 룰셋 무관 — 순서의 실제 귀결은 "컨트롤러 준비 전 모든 머지 정지") + 영속 감사 store·bootstrap mode(RS-A·기동 점검 불일치라 머지 미수용 대기) → **초기 마이그레이션 실행**(선언 완전성 검사[완전성 스윕 키 결속·별도 검토, 스펙 502행] + baseline finding 결정 종료 + 전용 마이그레이션 PR 스냅샷 감사 이관·PR 닫기, 스펙 503·504행 — consumer/감사 이관/PR 종료는 별도 Task 또는 승인된 호스팅 래퍼로 정의) → **maintenance freeze(마이그레이션 시작부터 RS-A 적용까지 승인받은 사람 머지도 외부 `main` 갱신을 막는다 — 이 구간은 RS-B만 있어 컨트롤러 밖 사람 머지가 가능하고, baseline·완전성 스윕 키를 만든 뒤 SoT/rule 변경이 착지하면 낡은 baseline으로 활성화되기 때문; 스펙 66·70행) + RS-A 적용 직전 착지 두 키·baseline 최종 재검증** → **RS-A 적용** → strict 기동 점검(전 룰셋 일치) → 종단 스모크. (스펙 505행 고정분은 RS-B→컨트롤러 확인→RS-A뿐; RS-C 시점·마이그레이션 위치는 계획 합성이며 §4.1 명문화는 P2류 후속. 마이그레이션이 감사 이관을 하므로 컨트롤러 배포·영속 감사 준비 뒤·RS-A 전에 둔다.)
- **P4-5 (분리) 캡처 vs 운영**: 각 Task Step 0 라이브 캡처는 별도 도그푸드 저장소/수동 셋업에서 하고 운영 활성화와 분리(순환 제거).
- **P4-6 (rollback) 비상 되돌리기(스펙 508행)**: 컨트롤러 장애 시 **RS-A 제거로 사람 머지 복구** + 강제 상실 감사 기록. RS-A 제거 동안 사람 머지가 생기면 "모든 `main` 갱신은 컨트롤러 머지이고 영속 감사에 남는다"는 §2.3 (ㄱ)·§2.9 전제가 깨지므로, **rollback 시작·종료 경계를 영속 기록**하고, **재활성화 전에 그 구간의 `main` first-parent 이력·pending intent를 reconcile**하며 **그 구간에 걸친 승인·base 복원을 무효화(재승인) 또는 재baseline**한 뒤에만 base resolver를 다시 신뢰한다(재활성화 조건 = 컨트롤러 복구 ∧ strict 룰셋 점검 ∧ rollback 구간 정리 완료). RS-A 제거 권한·절차를 명시한다.
- 활성화 완료 후 각 Task "라이브 확정 항목"을 확정 스키마로 메꿔 provisional 표기를 제거한다. **`ADR-0009`만** (P1-ㄴ 개정 후) proposed→accepted로 올린다; `ADR-0007`은 "허브 콘텐츠·경로 게이트 CODE(Phase 3) 착지" 조건이라(`ADR-0009:15`) 그 조건 충족 시 별도 승급. 정본 역기입은 대상별 게이트로: `docs/sot/rule/**`는 사용자 게이트 SoT PR(`protected-paths.md:27`), ADR은 그 경로 소관 게이트(`protected-paths.md` 해당 행)로 한다.

## Self-Review (계획 대 스펙)

- **스펙 커버리지**: 7개 포트 Task 1·3·5~9, 두 사전 관문 Task 2·4; P1~P3 착수 전제·P4 활성화 절차; ② CI 생산자·마이그레이션은 P4 선행조건으로 명시.
- **provisional 명시**: 포트 Task마다 Step 0·"라이브 확정 항목"으로 §8 목록을 조기 동결 없이 표기.
- **동결 계약 존중**: 동결 변경을 P3 (a)~(h)에 전부 열거; 머릿글 동결 집합에 `controller.py`; `MergeResult`·tagged union·영속 store는 각각 §2.9·모델 개정·P3 계약으로.
- **정본 정합**: 검토 스킬=머지 결과(규칙 55행), manifest (a)/(b)(규칙 50·56행), 미선언 active local vs inactive(규칙 35·53행), 완전성=별도 검토(스펙 502행), ADR 2키 드리프트(결정 3·4·9·10·88)를 P1 전제로, 승인 두 키만 재계산 금지(착지 키는 신선 재계산).
