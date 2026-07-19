# Phase 6 강제 게이트 실행부(GitHubGatePorts) 라이브 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **착수 시점 = Phase 9 (라이브 도그푸딩).** 모든 Task는 실제 GitHub 저장소·`gh` CLI 응답을 봐야 스키마가 확정되는 provisional 구현이다(스펙 §1 비목표·§8·§9). **P1~P3는 구현 착수의 전제**(정본 개정·동결 계약 확장 승인), **P4는 코드 이후의 활성화 절차**(exit criteria + 순서)다. 순수 코어(`gate.py`·`keys.py`·`models.py`)·포트 계약(`ports.py`)·**머지 컨트롤러(`controller.py`)**의 시그니처·데이터 모델·기존 동작은 동결이며, 동결을 바꾸는 항목은 모두 P3의 승인 대상으로 열거한다(조용한 변경 금지).

**Goal:** `hosts/github.py`의 7개 포트를 실제 `gh api` 호출로 구현하고, 룰셋 점검·`axdt-critical-paths` 두 사전 관문을 컨트롤러 층에 배선한다.

**Architecture:** `github.py`는 `git_host`의 `CommandBackend`(ABC)를 주입받아 gh 호출을 격리하고(subprocess 직접 호출 금지), (b) 클라이언트의 adapter+backend 분리를 계승한다. 각 포트는 gh 응답 JSON을 파싱해 순수 코어 계약(`models.py`·`keys.py`)으로 매핑한다. 포트는 원시 사실만 채우고 결정권 논리곱은 순수 코어가 계산한다.

**Tech Stack:** Python 3(`py -3`), `gh` CLI, pytest. 재사용: `axdt.git_host.backend.{CommandBackend,FakeCommandBackend,SubprocessBackend}`, `axdt.git_host.models.{PullRequest,CommandResult,GitHostError}`. **pytest 기준 디렉터리 = `WIP`**: `cd WIP && py -3 -m pytest axdt/sot_gate/...`.

## 착수 전제 P1~P3 (구현 착수 전 필수)

정본 개정·동결 계약 확장을 포함해 이 계획의 라이브 코드 범위를 벗어난다(사용자 게이트/별도 승인).

- **P1. 정본 규칙·ADR 드리프트 정정(사용자 게이트 SoT PR).**
  - (ㄱ) `sot-readiness.md` 92·105행의 "`sot/*` 보호 불요/요구하지 않음"을 `ADR-0009` 결정 8 개정(RS-C 요구)·스펙 §4.1에 맞춘다 — 개정 전 활성화 시 규칙과 `verify_ruleset_config`가 반대를 가리켜 모든 머지가 막힌다.
  - (ㄴ) **`ADR-0009` 내부 드리프트** — 결정 3(단일 판정 키, ADR:41)·결정 9(단일 키·축소 감사, ADR:53)·결정 10("축3 스윕", ADR:55)이 개정 전 문면으로 남아 스펙의 2026-07-17 2키 개정(판정 키 4성분 + 완전성 스윕 키·base SHA 포함 감사·별도 선언 완전성 마이그레이션)과 어긋난다. 세 결정을 현 2키 계약에 맞춰 개정한 뒤에만 `ADR-0009`를 `accepted`로 승급한다.
- **P2. `verify_ruleset_config` 감시 범위 정본 개정(필수).** 매트릭스가 기계판독 블록 **전량**을 값 일치로 대조하므로(§4.1 감시 열거보다 넓음 — `require_last_push_approval`·`require_code_owner_review`·RS-A `bypass`/`rules`·`enforcement` 활성 상태), 정본 §4.1 감시 열거·**§10 요약(547행)**·§3 `verify_ruleset_config` 계약·`ports.py` docstring(`hosts/github.py:82-84` 스텁 docstring은 Task 1 구현 시 자연 갱신)을 이 블록에 맞추는 개정이 선행돼야 한다. (초과 감시는 fail-closed 강화라 개정 전에도 안전하나 정합을 위해 필수 전제.)
- **P3. 동결 계약 확장 승인(별도 승인 — 아래 전부).** 착수 전 승인받거나 동결 코어 밖 호스팅 래퍼에 둘지 결정한다.
  - (a) `merge_pull_request`의 `-> None → -> str`(§2.9 확정, Task 8).
  - (b) 두 키 취득 (ㄱ) base 복원 시 컨트롤러 감사·first-parent 이력 resolver 주입 계약(Task 6·9).
  - (c) `AuditRecord.base` first-parent SHA 취득 경로(Task 8) + **머지 전 durable intent 기록 + 재기동 시 PR/head SHA로 원격 머지 결과 reconcile(멱등 복구)** — merge SHA는 원격 성공 후에만 알려져 성공~outbox 기록 사이 프로세스 종료 창이 있으므로, 사후 outbox가 아니라 사전 intent로 닫는다.
  - (d) **Task 2 기동 점검·경보·실패 감사** — `controller.py:50-52`가 유보한 동결 동작 변경. 성공 머지 전용 `AuditRecord`(controller.py:21-40)와 별개로 PR/base 없는 **기동 실패 감사 스키마**(사유·시각·룰셋 diff)·경보 sink를 추가한다.
  - (e) **Task 4 잠금 안 사전 관문** — critical-paths 판독 실패 RED 신호를 컨트롤러 계약에 넣거나(§7 (ㅁ) "잠금 안" 요구상 `merge_if_green` 내부 잠금과 통합), 래퍼로 둘 경우 잠금 통합.
  - (f) **두 키 무효 표현 모델 개정(Task 6)** — 두 키가 non-optional(`models.py:64-65`)이라 `stamp_valid: bool`만 더하면 결손 키 자리에 임의 센티널이 필요하다. **유효 스탬프(두 키 보유)와 원시 결손을 구분하는 tagged union**, 또는 **키 필드를 `Optional`로 바꾸고 `stamp_valid`와의 불변식**(None → 착지 키 불일치 → RED)을 택한다. 파급 파일을 명시: `ApprovalEvent`(models.py)·생성자·`gate.py`(코어가 소비할 때)·`test_gate.py`·`FakeGatePorts`·강제-필수 경로 분기(키 불요, 스펙 92행). optional 키는 코어 무변경으로 성립(None이 자연히 불일치)하고 tagged union은 코어 소비가 필요 — 선택 시 파일 목록을 확정한다.
  - (g) **감사 내용 계약 불일치 해소** — 스펙 116행은 "머지에 **반영된** 결정 스냅샷"을 기록하라 하나, 동결 컨트롤러는 의도적으로 winner가 아닌 **관측 결정 전량**을 append한다(controller.py:27·148). 정본을 "관측 전량"으로 바꾸거나, 코어가 실제 사용한 winner/승인을 한 번만 산출해 감사에 전달하도록 확정한다(컨트롤러에서 판정 재구현 금지).
  - (h) **컨트롤러 운영 계약** — 현재 잠금은 프로세스 로컬 `threading.Lock`(controller.py:58)이다. §8(526행)이 호스팅·직렬화 잠금을 Phase 9 결정으로 남기므로, **singleton 배포 보장 또는 프로세스 간 lease/분산 잠금**과 다중 worker 음성 시험, 저장소 밖 allowlist의 초기값·변경 감사·주입 경로를 확정한다(동결 코어 변경 시 P3, 래퍼 보장 시 래퍼 계약).

## Global Constraints

- **라이브 스키마 캡처 우선 (조기 동결 금지)**: 각 포트 Task는 Step 0으로 라이브 `gh api` 응답을 캡처·확인한 뒤 그 캡처로 red를 쓴다(스펙 §1·§8). 캡처는 P4-5의 도그푸드 셋업에서. (헬퍼 Task 0·배선 Task 2·4는 캡처 대상이 포트 응답과 달라 각 Task가 명시 — 모든 Task에 동일 Step 0이 있다는 뜻이 아니다.)
- **페이지네이션**: 목록 응답은 Task 0 헬퍼로 전 페이지 수집, 각 포트에 다중 페이지 red. 뒤 페이지 누락은 `touches_*` 오판(pass-through)이므로 fail-closed상 필수(스펙 §2.6·§7).
- **동결 계약 확장 규약**: 동결 시그니처·동작을 바꾸는 Task(2·4·6·8·9)는 P3에서 승인/래퍼 결정을 선행하고 조용히 바꾸지 않는다.
- **provisional 경계**: gh api 스키마·산출물 저장·제안 머지 결과 취득·두 키 취득·사람 판별·코멘트 편집/삭제 감지·룰셋 TOCTOU 대응·직렬화 잠금 구현은 §8 미확정. Step 0 실측 전 동결하지 않는다(스펙 §8·§10).
- **테스트 경계**: 순수 코어·컨트롤러 테스트는 `FakeGatePorts`(회귀 152 유지). `github.py`는 `FakeCommandBackend`(스펙 §6).
- **두 키 재계산 금지**: 두 키는 §2.3 (ㄱ)/(ㄴ)로 취득, 머지 시점 재계산 금지.
- **포트는 판정하지 않는다**: `role_name`·사람 여부·`dismissed`·`deleted`·`stamp_valid` 등 원시 사실만 채우고, 판정은 코어(스펙 §2.7·§3·§2.6 항목10).
- **사람/기계 판별(§2.7·§8)**: 결정권 = admin ∧ 명단 ∧ 사람. `author_is_human`·`approver_is_human`을 공통 identity resolver로 author·approver 양쪽에 채우고, **판별불능은 `False`**(→ 코어 fail-closed).
- **선언 단일 진실원**: 룰셋 대조 값은 `ENFORCEMENT_MATRIX.md`의 `axdt-enforcement-matrix` 블록(신뢰 컨트롤러 배포본)이 정본. `verify_ruleset_config`가 블록 전량을 값 일치로 대조(손사본 금지, Task 1).

---

## Task 0: CommandBackend 주입 + gh api JSON/페이지네이션 헬퍼

**Files:** Modify `hosts/github.py`; Test `tests/test_hosts_github.py`(신규).

**Interfaces:** Consumes `CommandBackend`·`FakeCommandBackend`·`GitHostError`. Produces `GitHubGatePorts(backend, repo, ...)`(actor ID 주입 방식은 Task 1 Step 0에서 확정); `_api_json(*args) -> dict|list`(exit≠0·malformed JSON·빈 stdout·예상 밖 top-level 타입 → `GitHostError`); `_api_paginated(*args) -> list`.

- [ ] **Step 0(라이브): 페이지네이션 출력 형태 캡처**(도그푸드).
- [ ] **Step 1: 실패 테스트** — 정상 JSON; exit≠0·malformed JSON·빈 stdout·top-level 타입 불일치 → `GitHostError`; `_api_paginated` 2페이지 합침.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과(`cd WIP && py -3 -m pytest axdt/sot_gate/tests/test_hosts_github.py -v`) → 커밋** `feat(phase6): 주입 + JSON/페이지네이션 헬퍼`.

---

## Task 1: verify_ruleset_config — 블록 파싱 + 블록 전량 값 대조 + actor ID 결합

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §4.1·§8):** `rulesets` + `rulesets/{id}`. 블록을 파싱(코드 상수 금지)해 대조 규칙 5항목(매트릭스, `enforcement=active`·`require_code_owner_review=false` 포함)을 **블록 전량 값 일치**로 검사. `<controller-actor-id>`는 런타임 결합.

- [ ] **Step 0(라이브): rulesets 응답 캡처 + actor ID·룰셋 식별·TOCTOU 결정**(도그푸드) — (i) `enforcement` 상태·`rules[].parameters`·`bypass_actors` 필드 경로; (ii) **actor ID 획득**(신뢰 구성 주입 vs 컨트롤러 토큰 `/user` 응답); (iii) **라이브 룰셋을 각 선언(RS-A/B/C)에 대응시키는 식별 방식**(룰셋 이름 일치 vs 구조 일치); (iv) **정본 파라미터 투영 대 API 부가 기본 필드** 규칙(선언 필드만 비교하되 API 미선언 기본값으로 정상 구성이 거부되지 않게); (v) **룰셋 변경 TOCTOU 대응**(스펙 363·§8 522행: 변경 이벤트 감시 / 머지 직후 재확인 / 잔여 위험 명시 수용 중 택일).
- [ ] **Step 1a: 파서 red** — 정상 파싱; 매트릭스 fail-closed 거부 조건 전부(부재·중복·미종결·유효행0·미지원 version·중복 ID/필드·unknown 필드/룰/파라미터·필드 누락·placeholder 미해결/비수치·중복 룰/actor).
- [ ] **Step 1b: 대조 red(캡처 fixture)** — 정상→`True`; `enforcement: disabled`/`evaluate`→`False`; 승인수 2·dismiss-stale false·`require_last_push_approval` false·**`require_code_owner_review` true**·머지방식 squash→각각 `False`; RS-B `non_fast_forward`/`deletion` 누락→`False`; RS-B bypass 있음→`False`; RS-A `rules`≠`[update]`→`False`; **RS-A bypass에 추가 actor·다른 actor ID→`False`**; RS-A 부재/합쳐짐→`False`; RS-C 부재·`pull_request` 추가·bypass 비어있지 않음→각각 `False`; 선언 외 추가→`False`; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): verify_ruleset_config — 블록 전량 값 대조 + actor 결합`.

**라이브 확정 항목:** rulesets 필드 경로·`enforcement` 필드·actor ID 획득·룰셋 식별 방식·파라미터 투영 규칙·TOCTOU 대응은 Step 0 결정(스펙 §8).

---

## Task 2: 룰셋 점검 배선 — 기동 + 매 머지 실패 경보·감사 (호스팅, P3-d/h)

**Files:** Modify `controller.py` 또는 호스팅 래퍼(P3-d/h); Test `test_controller.py` 또는 호스팅 테스트.

**규칙(스펙 §4.1·363행):** "기동 시와 매 머지의 직렬화 잠금 안에서" 점검, 불일치 시 경보·감사.

- [ ] **Step 0: 배선 위치·기동 실패 감사 스키마·경보 sink·직렬화 보장 결정(P3-d/h)**.
- [ ] **Step 1: 실패 테스트** — 기동 시 `verify==False`→머지 수용 전 차단 + 기동 실패 감사 + **경보 발생**; 매 머지 점검 실패→경보 + 실패 감사; `True`→정상 기동(부트스트랩: RS-A 미적용 시점 불일치 대기가 정상, P4); **다중 worker 동시 기동→단일 직렬화 보장** 음성 시험.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과(회귀 152) → 커밋** `feat(phase6): 룰셋 점검 — 기동+매 머지 경보·감사·직렬화`.

---

## Task 3: read_pr_metadata — PR 메타데이터 + touches_sot (rename)

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §2.6·§8):** PR 조회 → 필드; 변경 경로 전 페이지 수집 → projection 교차 → `touches_sot`. **rename 이전·이후 합집합**(Task 4 헬퍼 공유).

- [ ] **Step 0(라이브): PR 조회·변경분·rename 응답 캡처**(도그푸드).
- [ ] **Step 1: 실패 테스트** — 필드 매핑; SoT 변경→`True`; `README.md`만→`False`; rename 구경로 projection 내→`True`; 2페이지 SoT 감지; state 매핑.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_pr_metadata — touches_sot(전 페이지·rename)`.

---

## Task 4: critical-paths 잠금 안 사전 관문 → touches_enforcement_surface (P3-e)

**Files:** Modify `hosts/github.py`; Modify `controller.py` 또는 래퍼(P3-e); Test `test_hosts_github.py`·`test_controller.py`.

**규칙(스펙 §7·506행):** `axdt-critical-paths` 블록을 신뢰 base(`main`)에서 읽는다. glob `protected-paths.md:50-53`. **rename 이전·이후 합집합**(근거 `protected-paths.md:48`; 블록 문법 절엔 rename 의미 없어 red 이전 §8 결정·라이브 역기입은 사용자 게이트). 블록 부재·기형·유효행0→`evaluate_gate` 이전 **잠금 안** fail-closed RED(§7 (ㅁ), 잠금은 controller.py:114).

- [ ] **Step 0: 잠금 통합 결정(P3-e)** + **Step 0b(라이브): base 블록 읽기(base64) 캡처**.
- [ ] **Step 1~2: 파싱·매칭 red + 관문 배선 red** — glob·rename 매칭; 부재/기형→잠금 안 RED; enforcement_surface만 참 PR이 포크 거부+결정권자 승인 통과/차단.
- [ ] **Step 3~5: 실패 확인 → 구현 → 통과(회귀 152) → 커밋** `feat(phase6): critical-paths 잠금 안 관문 + glob(rename)`.

---

## Task 5: read_channel_decisions — 코멘트 + role_name + 사람 판별 + 삭제 감지 + 버전 스탬프

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §2.7·§4.1·§8):** `issues/{n}/comments`(전 페이지) → 구조화 코멘트 → `ChannelDecision`. `author_role`=`role_name`. `author_is_human`=공통 resolver(판별불능→`False`). **편집·삭제 흔적 채움**(ports.py:46, `deleted` 모델 필드). 버전된 스탬프 문법을 **먼저 승인·게시** 후 round-trip 캡처.

- [ ] **Step 0: 스탬프 문법 승인·게시 → 라이브 코멘트·permission·계정유형 캡처 + 삭제 감지 결정** — §8 519행: 코멘트 삭제를 **현재 스냅샷의 부재로 처리** vs **이벤트/웹훅/영속 tombstone으로 `deleted=True` 복원** 중 택일.
- [ ] **Step 1: 실패 테스트** — 구조화 코멘트→매핑; `updated_at != created_at`→편집; **삭제→결정한 방식대로 `deleted=True` 또는 부재**(삭제 후 winner·미대조 동작 round-trip); `role_name`→`author_role`; 사람/봇/판별불능(`False`); **기형 스탬프 처리 — 무자격 작성(비결정권자) 기형은 무시(비구조화 취급), fail-closed 선택은 유효 후보(결정권자 작성) 한정**(스펙 §2.6 항목11·§2.7: 무자격 계정의 기형 코멘트로 SoT PR 영구 차단하는 서비스 거부 배제); unknown version·중복·부분 키는 이 한 규칙으로 고정; 비구조화 무시; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_channel_decisions — 삭제 감지·서비스거부 배제·버전 스탬프`.

---

## Task 6: read_approvals — 스트림 전량 + 두 키(라이브 결정) + dismissed·무효(P3-f)

**Files:** Modify `hosts/github.py`(+ P3-b/f 파일: `ports.py`·`models.py`·생성자·(tagged union 선택 시) `gate.py`·`test_gate.py`·`FakeGatePorts`); Test `test_hosts_github.py`.

**gh 매핑(스펙 §2.3·§8):** `pulls/{n}/reviews`(전 페이지) → 승인 스트림 **전체**를 반환. 유효성은 게이트가 판정(`ports.py:51-55`). `dismissed`→`dismissed=True` 전량. `approver_role`·`approver_is_human`은 공통 resolver.

- [ ] **Step 0: 두 키 취득·무효 표현 라이브 결정(P3-b/f)** — (ㄱ) base 복원(resolver 주입) / (ㄴ) 구조화 스탬프. **무효 표현**은 P3-f 모델 개정(tagged union 또는 optional 키+`stamp_valid` 불변식)으로 — 임의 센티널 금지. 선택에 따른 파급 파일 확정. reviews·스탬프 캡처.
- [ ] **Step 1: 실패 테스트(결정 후)** — 전량 반환(대표 선정 금지); dismissed→`dismissed=True`; approver 사람/봇/판별불능(`False`); (ㄴ) 두 키 스탬프 하나라도 결손→무효 표현(단일 스탬프도 무효), 둘 다 있으면 유효; 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_approvals — 전량+dismissed·무효(P3-f)+두 키`.

---

## Task 7: read_ci_artifacts — 조회 + 쓰기 신뢰 통제

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**gh 매핑(스펙 §4.2·§8):** 두 신뢰 산출물을 산출물 저장소에서 읽는다(커밋 상태 금지). 없거나 파싱 실패→`None`. **쓰기 신뢰 모델이 진짜 방어선**(ACL/서명; 스펙 401·521행).

- [ ] **Step 0(라이브): 저장 위치·형식·쓰기 통제 선택·실증**.
- [ ] **Step 1: 실패 테스트** — 정상→매핑; 정합성만→`(a, None)`; 파싱 실패→`None`; `FullBindingKey` 매핑; 위조 산출물·잘못된 서명·일반 PR 신원 쓰기→fail-closed 음성 시험.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_ci_artifacts — 쓰기 신뢰·음성 시험`.

---

## Task 8: merge_pull_request — head 고정 머지 + SHA + base 취득 + 멱등 복구 (P3-a/c/g)

**Files:** Modify `hosts/github.py`·`ports.py`(ABC·docstring)·`FakeGatePorts`·`controller.py`(감사)·Test `test_hosts_github.py`·`test_ports.py`·`test_controller.py`.

**Interfaces:** Produces **`merge_pull_request(...) -> str`(머지 커밋 SHA)** — §2.9 확정 `None→str`. `MergeResult(merge_sha, base_sha)`는 §2.9 문면(반환만 확장)을 넘어서므로 **채택 시 별도 §2.9 스펙 개정 필요**; 기본은 `-> str` + P3-c resolver.

**gh 매핑(스펙 §2.5·§2.9·§8):** `PUT .../merge`, `merge_method=merge`, `sha={head_sha}`(스냅샷). 응답의 머지 커밋 SHA 반환. `AuditRecord.base`=first-parent는 응답에 없어 P3-c로 취득 + **머지 전 durable intent + 재기동 reconcile**(멱등). head 이동→`HeadMovedError`. 감사 내용은 P3-g 결정(관측 전량 vs 반영 결정)에 따른다.

- [ ] **Step 0(라이브): merge 응답·거부 코드·payload·parent 조회 캡처** — `405`는 승인 부족(실증)에도 나므로 **HTTP 코드 + payload/message 함께** 캡처해 head SHA 불일치만 `HeadMovedError`, 승인·룰셋 위반은 `GitHostError`.
- [ ] **Step 1: 실패 테스트** — 정상 머지→argv + 반환=머지 SHA; head 불일치(코드+payload)→`HeadMovedError`; 승인 부족 `405`→`GitHostError`(오분류 금지); `FakeGatePorts` SHA 반환; 감사 `base`=first-parent; **머지 전 durable intent 기록 후 프로세스 종료→재기동 시 PR/head SHA로 reconcile**(멱등, 중복 머지·유실 없음) 음성 시험; `test_ports` 반환형 회귀.
- [ ] **Step 2~5: 실패 확인 → 구현(`None→str`: github·ports·Fake·controller·test_ports) → 통과 → 커밋** `feat(phase6): merge None→str(§2.9) + base·멱등 복구`.

---

## Task 9: compute_landing_keys — 두 키 + trusted epoch + 공유 정규화 + 골든 벡터

**Files:** Modify `hosts/github.py`; **Create 공유 canonical calculator 모듈**(record-set/합성 키 — ② CI·컨트롤러 공유; **`WIP/axdt/sot_gate/**` critical glob 안에 두고 실행기 manifest (a)에 등재·변경 측 통보** — `protected-paths.md:75`, 미등재 시 실행기 약화 무관문 통과); Test `test_hosts_github.py`·신규 conformance 테스트.

**규칙(스펙 §2.3·§4.2, `sot-readiness.md` 32·35·41·42·43·46·49·50·52·53·55·56행):**
- 제안 머지 결과에서 두 키 계산. **신뢰 base에서 읽는 것 = 실행기(하니스·판정 키 계산기)**; **완료 규칙·검토 스킬 내용은 후보 정책이라 머지 결과에서 해시해 epoch에 결속**(규칙 52·55행).
- **manifest (a)/(b) 경계**: `review_policy_epoch`에 넣는 것은 **실행기 revision (a)만**(규칙 50행: manifest (a) 실행기 = 보호 + epoch). **`sot-lint`는 (b) 보호 전용**(규칙 56행)이라 epoch에 넣지 않는다 — (a)/(b) 변경의 키 변화를 분리 시험한다.
- `review_policy_epoch` = trusted 환경 성분(모델 revision·실행기 revision·프롬프트·추론 설정; 규칙 41·46행)을 **trusted epoch provider**가 공급 + 완료 규칙·검토 스킬 digest(머지 결과) 조립.
- **공유 정규화 계산기 신설 필수**: `keys.py`의 기존 정규화는 finding digest용(ASCII 길이+US 프레이밍, `keys.py:58-87`)이라 규칙의 record-set(uint32 big-endian 프레이밍·합성 키 태그·순서, 규칙 43행)과 **다르다**. ② CI와 공유할 계산기를 새 모듈로 만들고 규칙 42행의 **골든 벡터(preimage 바이트 + 기대 hex, 키별 태그·성분 순서 분리)**로 고정(Phase 6 conformance).
- 적용 rule = active global + 선언된 active local(규칙 32행); 완전성 입력 = **active rule 전량**(규칙 35행).

- [ ] **Step 0(라이브): 제안 머지 결과 취득·trusted epoch provider 확정 + 골든 벡터 산출**.
- [ ] **Step 1: 실패 테스트(테스트표 분리)** — 결정성; projection 트리 변경→두 키 모두; **active+적용(선언 active local) 본문 편집→판정 키·완전성 키 모두**; **active+미선언 active local 본문 편집→완전성 키만**(규칙 35행); **deprecated/superseded(inactive) 본문 편집→어느 키도 불변**; **active↔inactive 전이→manifest(판정 키)·active 입력(완전성 키) 모두**(규칙 53행); 검토 스킬·완료 규칙(후보) 편집→두 키 모두; **실행기 revision (a) 변경→두 키 모두 / `sot-lint` (b) 변경→키 불변**(경계 분리); 활성 카탈로그 입력 digest→완전성 키만; **골든 벡터 preimage·hex, 키별 태그·성분 순서**; **fail-closed 값 도메인 — `scope`∉{local,global}·`status`∉{active,deprecated,superseded}·`id` 규약 위반·null/비문자열 필드·uint32 초과→오류, `scope` 부재→`global` 정규화, NFC 정규화 후 같아지는 두 경로 공존→fail-closed**(규칙 42행); 경로 NFC·내용 비-NFC·BOM 1회·CRLF/단독 CR·종단 개행·UTF-8 실패·uint32 프레이밍·raw-digest 합성; README/_TEMPLATE 제외.
- [ ] **Step 2~5: 실패 확인 → 구현(공유 계산기 + 골든 벡터) → 통과 → 커밋** `feat(phase6): compute_landing_keys — 공유 정규화·(a)/(b) 경계·값 도메인·골든 벡터`.

---

## P4. Phase 9 활성화 (코드 이후 — exit criteria + 순서)

전제조건 P1~P3 처리 + 아래 exit criteria 확인 후 순서대로 활성화한다.

- **P4-1 (exit) 인프라**: 저장소 public·컨트롤러 신원·최소 권한 토큰(`ADR-0009` 결정 1·12).
- **P4-2 (exit) critical 블록 착지**: `axdt-critical-paths` 블록이 신뢰 base(`main`)에 착지·파싱 가능(실행기 manifest 경로 — Task 9 신설 계산기 포함 — · 허브 게이트 실행 폐쇄 전체 등재, `protected-paths.md:71-75·91-93`; 스펙 §7 (ㅁ)·506행).
- **P4-3 (exit) 초기 마이그레이션**: **선언 완전성 검사(완전성 스윕 키에 결속된 별도 검토 — 정합성 4축의 한 축[축3]이 아니다, 스펙 502행)** 실행 + baseline finding 결정 종료 + 감사 이관 완료(스펙 502-504행).
- **P4-4 (활성화 순서)**: 워크플로 전제 실증(force-push 미사용) → **RS-C 적용** → RS-B 적용 → 컨트롤러 배포(저장소 밖이라 룰셋과 무관 — 순서의 실제 귀결은 "컨트롤러 준비 전 모든 머지 정지") + bootstrap mode(RS-A·기동 점검 불일치라 머지 미수용 fail-closed 대기) → **RS-A 적용** → strict 기동 점검(전 룰셋 일치) → 종단 스모크. (스펙 505행이 고정한 것은 RS-B→컨트롤러 확인→RS-A뿐; RS-C 적용 시점·나머지는 계획 합성이며 RS-C 시점 §4.1 명문화는 P2류 후속.)
- **P4-5 (분리) 캡처 vs 운영**: 각 Task Step 0 라이브 캡처는 **별도 도그푸드 저장소/수동 셋업**에서 하고 위 운영 활성화와 분리한다(캡처-적용 순환 제거).
- 활성화 완료 후 각 Task "라이브 확정 항목"을 확정 스키마로 메꿔 provisional 표기를 제거한다. **`ADR-0009`만** 이 계획 몫으로 (P1-ㄴ 개정 후) proposed→accepted로 올린다; `ADR-0007`은 "허브 콘텐츠·경로 게이트 CODE(Phase 3) 착지" 조건이라(`ADR-0009:15`) 그 조건 충족 시 별도 승급한다. 정본 역기입(`docs/sot/rule/**`·ADR)은 **사용자 게이트 SoT PR로** 한다(`protected-paths.md:27`).

## Self-Review (계획 대 스펙)

- **스펙 커버리지**: 7개 포트 Task 1·3·5~9, 두 사전 관문 Task 2·4; P1~P3 착수 전제·P4 활성화 절차 분리.
- **provisional 명시**: 포트 Task마다 Step 0·"라이브 확정 항목"으로 §8 목록(gh 스키마·산출물·머지 결과·두 키·사람 판별·삭제 감지·TOCTOU·직렬화·actor ID·룰셋 식별)을 조기 동결 없이 표기.
- **동결 계약 존중**: 동결 변경을 P3 (a)~(h)에 전부 열거; 머릿글 동결 집합에 `controller.py` 포함; `MergeResult`·tagged union은 각각 §2.9·모델 개정 필요를 명기.
- **정본 정합**: 검토 스킬=머지 결과(규칙 55행), manifest (a)/(b) 경계(규칙 50·56행), 미선언 active local vs inactive(규칙 35·53행), 완전성=별도 검토(스펙 502행), ADR 내부 드리프트(결정 3·9·10)를 P1 전제로.
