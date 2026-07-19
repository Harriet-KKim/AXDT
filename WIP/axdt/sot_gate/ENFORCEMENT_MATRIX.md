# ENFORCEMENT_MATRIX — main·sot/* 룰셋 선언 상태

`verify_ruleset_config`(`ports.py`·`hosts/github.py`)가 라이브 호스트 룰셋을 대조할 **선언 상태의 단일 진실원**이다. 컨트롤러는 기동 시와 매 머지의 직렬화 잠금 안에서 라이브 룰셋을 이 문서의 선언과 대조하고, 불일치하면 fail-closed로 머지를 거부한다(스펙 §4.1, `ADR-0009` 결정 2·8).

- **정본 관계**: 파라미터의 근거·실증은 스펙 `WIP/specs/2026-07-08-phase6-enforcement-host-branch-protection-design.md` §4.1과 `ADR-0009`에 있다. 대조에 쓰는 선언 값은 이 문서가 정본이며, 스펙은 그 근거다. 값이 갈리면 이 문서를 스펙 §4.1에 맞춰 정정한다(손사본 금지).
- **출처**: 아래 파라미터는 2026-07-09 GitHub 개인 저장소 라이브 실증으로 확정됐다(스펙 §4.1·`ADR-0009` 실증 표).
- **provisional 경계**: 라이브 룰셋을 `gh api rulesets`/`rulesets/{id}`로 읽어 이 선언과 대조하는 **조회 스키마·필드 매핑은 Phase 9 라이브 도그푸딩에서 확정**한다(스펙 §8). 이 문서가 고정하는 것은 대조 대상 값이지 조회 방식이 아니다.
- **자기 강제**: 이 파일은 `rule-protected-paths`의 `axdt-critical-paths` 블록에 `WIP/axdt/sot_gate/**`로 등재돼 강제-필수 경로에 든다. 활성화 후 이 문서를 바꾸는 PR도 포크 거부 + 결정권자 승인을 거친다(스펙 §2.6 세 번째 분기).

## 전제조건

- 대상 저장소는 **공개(public)**여야 한다. 개인 소유 private 저장소 + 무료 플랜은 룰셋도 구식 브랜치 보호도 `403`으로 거부된다. AXDT 저장소는 2026-07-09 공개 전환으로 이 전제를 충족했다. private 유지가 필요하면 GitHub Pro 이상이 필요하다(`ADR-0009` 결정 12).
- **컨트롤러 신원**: `main` 갱신 권한을 가진 지정 계정 하나. 대상 저장소 밖에 살고, 머지 토큰은 컨트롤러에만 최소 권한으로 발급한다(일반 CI 시크릿에 넣지 않는다). 아래 `<controller-actor-id>`는 라이브 셋업에서 이 계정의 수치 `actor_id`로 치환한다(값 확정 = Phase 9).

## 룰셋 — 반드시 세 벌로 분리

두 `main` 룰셋(RS-A·RS-B)을 하나로 합치면 안 된다. GitHub의 우회(bypass)는 **룰셋 단위**라, `update`를 통과시키려고 컨트롤러를 우회 신원으로 넣는 순간 같은 룰셋의 승인 요구까지 함께 건너뛴다(실증: 승인 0개 PR이 머지됨). 분리는 선택이 아니라 정확성 조건이다.

### RS-A — main 갱신 제한 (컨트롤러만 우회)

| 항목 | 선언 값 |
|---|---|
| `target` | `main` |
| `rules` | `[{ "type": "update" }]` |
| `bypass_actors` | `[{ "actor_type": "User", "actor_id": <controller-actor-id>, "bypass_mode": "always" }]` |

효과: 컨트롤러 외 누구도 `main`을 갱신하지 못한다(실증: 소유자 머지도 `Cannot update this protected ref`로 거부).

### RS-B — main 승인·감사 (우회 신원 없음)

| 항목 | 선언 값 |
|---|---|
| `target` | `main` |
| `rules` | `[{ "type": "pull_request", "parameters": { "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": true, "require_last_push_approval": true, "allowed_merge_methods": ["merge"] } }, { "type": "non_fast_forward" }, { "type": "deletion" }]` |
| `bypass_actors` | `[]` (반드시 빈 배열) |

- `require_code_owner_review`는 **현 1인 구성에서 켜지 않는다**. 코드오너 = 작성자 1인이면 GitHub이 자기 PR의 코드오너 승인을 인정하지 않아, 우회 허용 시 관문이 공허하고 우회 차단 시 자기 PR을 승인 못 해 교착이다. 작성자 아닌 코드오너가 1인 이상인 다인 구성으로 전환할 때 `true`로 켠다(스펙 §4.1).
- `allowed_merge_methods: ["merge"]`는 저장소 전역이 squash를 허용해도 룰셋이 머지 커밋만 남기게 강제한다(실증). 감사 이력에서 승인 head가 `main` 이력에 부모로 보존된다.
- 효과: 컨트롤러도 승인 관문·머지 방식 제한에 걸린다(실증: 컨트롤러 REST 머지가 `405 New changes require approval from someone other than the last pusher`로 거부). 승인은 PR 작성자가 아닌 사람이 해야 한다(`require_last_push_approval`) — SoT PR은 에이전트가 열고 사람이 승인하므로 성립한다.

### RS-C — sot/* 소스 브랜치 단조 전진 (우회 신원 없음)

| 항목 | 선언 값 |
|---|---|
| `target` | `sot/*` |
| `rules` | `[{ "type": "non_fast_forward" }, { "type": "deletion" }]` (**`pull_request` 룰 없음**) |
| `bypass_actors` | `[]` (반드시 빈 배열) |

- `pull_request` 룰을 담지 않으므로 에이전트의 일반 fast-forward push는 그대로 통과하고, force-push(history 재작성)·브랜치 삭제만 막는다. `sot/*` head가 이전 SHA로 되돌아올 수 없어(단조 전진) 컨트롤러 read-set의 ABA 창이 닫힌다(force-push 롤백 A→B→A 방어, 스펙 §2.8·`ADR-0009` 결정 8).
- **전제(활성화 전 확인)**: 에이전트가 `sot/*`에 rebase·amend(force-push)를 쓰지 않고 새 커밋만 얹어야 한다. 이 전제가 깨지면 RS-C 대신 스펙 §2.8의 (가) 대안(읽기를 head SHA에 결속)으로 재검토한다.
- **RS-B와 분리하는 이유**: RS-B의 `pull_request` 룰을 `sot/*`로 넓히면 `sot/*` push마다 PR을 강제해 에이전트 워크플로가 막힌다.

## verify_ruleset_config 대조 규칙

컨트롤러가 라이브 룰셋을 위 선언과 대조할 때 `True`(정상)를 내는 조건. 하나라도 어긋나면 `False` → 컨트롤러가 fail-closed로 머지를 거부하고 경보·감사 기록을 남긴다(스펙 §4.1·§3).

1. **RS-A와 RS-B가 별개 룰셋으로 분리**돼 있다(한 룰셋으로 합쳐지지 않았다).
2. **RS-B의 `bypass_actors == []`**이다(우회 신원이 비어 있다).
3. **RS-B의 필수 파라미터가 존재**한다: `required_approving_review_count`(≥1)·`dismiss_stale_reviews_on_push`·`allowed_merge_methods: ["merge"]`·`non_fast_forward`·`deletion`.
4. **RS-C가 존재**하고 대상이 `sot/*`이며 `non_fast_forward`·`deletion`을 담고 **`bypass_actors == []`**이다.

> **잔여 위험(TOCTOU)**: 이 대조는 컨트롤러 자신의 평가~머지만 직렬화한다. 외부 admin이 웹 UI·API로 룰셋을 바꾸는 것은 이 잠금이 막지 못하므로, 점검 통과 후 머지 착지 전에 구성이 약화되는 창이 남는다. 다음 머지의 점검이 이를 사후 검출한다. 이 창을 좁히는 호스트 수준 보장(룰셋 변경 이벤트 감시·머지 직후 재확인)은 Phase 9 provisional이다(스펙 §4.1·§8).

## 켜지 않는 것 (의도적 배제)

| 기능 | 배제 이유 |
|---|---|
| `required_linear_history` | 머지 커밋을 금지해 감사 이력 보존과 충돌한다. |
| `merge_queue` | 개인 소유 저장소에서 룰 생성이 거부된다(실증 `422`). 직렬화는 컨트롤러가 한다. |
| `required_status_checks` | 강제 수단으로 쓰지 않는다. ② 검토 CI 산출물은 컨트롤러가 직접 읽는다(스펙 §2.4·§4.2). |
