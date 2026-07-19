# ENFORCEMENT_MATRIX — main·sot/* 룰셋 선언 상태

`verify_ruleset_config`(`ports.py`·`hosts/github.py`)가 라이브 호스트 룰셋을 대조할 **선언 상태의 단일 진실원**이다. 컨트롤러는 기동 시와 매 머지의 직렬화 잠금 안에서 라이브 룰셋을 이 문서의 **기계판독 선언 블록**과 대조하고, 불일치하면 fail-closed로 머지를 거부한다(스펙 §4.1, `ADR-0009` 결정 2·8).

- **정본 관계**: 파라미터의 근거·실증은 스펙 `WIP/specs/2026-07-08-phase6-enforcement-host-branch-protection-design.md` §4.1과 `ADR-0009`에 있다. 대조에 쓰는 선언 값은 이 문서가 정본이며, 스펙은 그 근거다. 값이 갈리면 이 문서를 스펙 §4.1에 맞춰 정정한다(손사본 금지).
- **소비 방식(손사본 금지 이행)**: `verify_ruleset_config`는 아래 ` ```axdt-enforcement-matrix ` **기계판독 블록을 런타임에 파싱**해 대조 기준을 얻는다(사람용 표를 코드 상수로 옮기지 않는다). 블록은 후보 worktree가 아니라 **신뢰된 컨트롤러 배포본**에서 읽는다. 파싱·placeholder 해석·기형 시 fail-closed는 계획서 Task 1이 정의한다. 구현이 부득이 코드 상수를 두면 "상수 == 이 블록" 계약 테스트로 드리프트를 막는다.
- **대조 범위 = 블록 전량 값 일치**: `verify_ruleset_config`는 블록에 선언된 **모든 항목**(각 룰셋의 `enforcement` 상태·`target`·정확한 `rules`/파라미터·`bypass` 신원·`separated`·`forbid_rules`)을 라이브와 **정확히 일치**하는지 검사한다. 이는 스펙 §4.1 감시 열거(362·384행)보다 넓으며, 그 정합은 **전제조건 P2**(정본 §4.1·§3 `verify_ruleset_config` 계약·`ports.py` docstring 개정)로 처리한다 — 개정 전의 초과 감시는 fail-closed 강화 방향이라 허용한다.
- **출처**: RS-A·RS-B 파라미터는 2026-07-09 GitHub 개인 저장소 라이브 실증으로 확정됐다(스펙 §4.1·`ADR-0009` 실증 표). RS-C는 2026-07-18 설계 결정으로 신설됐고(`ADR-0009` 결정 8 개정), 라이브 검증은 Phase 9에서 한다.
- **provisional 경계**: 라이브 룰셋을 `gh api rulesets`/`rulesets/{id}`로 읽어 이 선언과 대조하는 **조회 스키마·필드 매핑(`enforcement` 상태 필드명 포함)은 Phase 9 라이브 도그푸딩에서 확정**한다(스펙 §8). 이 문서가 고정하는 것은 대조 대상 값이지 조회 방식이 아니다.
- **자기 강제**: 이 파일은 `rule-protected-paths`의 `axdt-critical-paths` 블록에 `WIP/axdt/sot_gate/**`로 등재돼 강제-필수 경로에 든다. 활성화 후 이 문서를 바꾸는 PR도 포크 거부 + 결정권자 승인을 거친다(스펙 §2.6 세 번째 분기).

## 전제조건

- 대상 저장소는 **공개(public)**여야 한다. 개인 소유 private 저장소 + 무료 플랜은 룰셋도 구식 브랜치 보호도 `403`으로 거부된다. AXDT 저장소는 2026-07-09 공개 전환으로 이 전제를 충족했다. private 유지가 필요하면 GitHub Pro 이상이 필요하다(`ADR-0009` 결정 12).
- **컨트롤러 신원**: `main` 갱신 권한을 가진 지정 계정 하나. 대상 저장소 밖에 살고, 머지 토큰은 컨트롤러에만 최소 권한으로 발급한다(일반 CI 시크릿에 넣지 않는다). 아래 블록의 `<controller-actor-id>`는 배포 문서를 편집하지 않고 **런타임에** 컨트롤러 계정의 수치 `actor_id`로 결합한다(값 획득·결합 방식 = Phase 9, Task 1 Step 0). 블록 문법의 fail-closed "placeholder 미해결/비수치" 판정도 이 런타임 결합을 전제한다.
- **정본 규칙 드리프트(활성화 차단, 반드시 선행)**: RS-C(`sot/*` force-push·삭제 차단)는 `ADR-0009` 결정 8의 2026-07-18 개정과 스펙 §4.1로 확정됐으나, 정본 규칙 `docs/sot/rule/sot-readiness.md`(`status: active`)의 강제 매핑 표(92행)와 근거(105행)는 아직 개정 전 문면("`sot/*` 소스 브랜치 자체 보호는 불요/요구하지 않는다")이다. 이 드리프트가 남으면 규칙을 따르는 셋업은 RS-C를 안 걸고 `verify_ruleset_config`는 RS-C 부재를 불일치로 거부해 **모든 머지가 막힌다**. 활성화 전에 `sot-readiness.md` 92·105행을 결정 8 개정(RS-C)에 맞추는 **사용자 게이트 SoT PR**이 선행돼야 한다(규칙 수정은 이 매트릭스·계획서 범위 밖 — 전제조건으로만 명기).

## 룰셋 — 반드시 세 벌로 분리

두 `main` 룰셋(RS-A·RS-B)을 하나로 합치면 안 된다. GitHub의 우회(bypass)는 **룰셋 단위**라, `update`를 통과시키려고 컨트롤러를 우회 신원으로 넣는 순간 같은 룰셋의 승인 요구까지 함께 건너뛴다(실증: 승인 0개 PR이 머지됨). 분리는 선택이 아니라 정확성 조건이다. 세 룰셋 모두 **실제로 적용돼 효과를 내는(`enforcement: active`)** 상태여야 한다 — 같은 룰·actor를 가진 `disabled`/`evaluate` 룰셋은 강제하지 못하므로 대조에서 불일치다.

### RS-A — main 갱신 제한 (컨트롤러만 우회)

| 항목 | 선언 값 |
|---|---|
| `enforcement` | `active` |
| `target` | `main` |
| `rules` | 정확히 `[{ "type": "update" }]` |
| `bypass_actors` | 정확히 `[{ "actor_type": "User", "actor_id": <controller-actor-id>, "bypass_mode": "always" }]` (추가 actor 불허) |

효과: 컨트롤러 외 누구도 `main`을 갱신하지 못한다(실증: 소유자 머지도 `Cannot update this protected ref`로 거부).

### RS-B — main 승인·감사 (우회 신원 없음)

| 항목 | 선언 값 |
|---|---|
| `enforcement` | `active` |
| `target` | `main` |
| `rules` | 정확히 `[{ "type": "pull_request", "parameters": { "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": true, "require_last_push_approval": true, "allowed_merge_methods": ["merge"] } }, { "type": "non_fast_forward" }, { "type": "deletion" }]` |
| `bypass_actors` | `[]` (반드시 빈 배열) |

- `require_code_owner_review`는 **현 1인 구성에서 켜지 않는다**. 코드오너 = 작성자 1인이면 GitHub이 자기 PR의 코드오너 승인을 인정하지 않아, 우회 허용 시 관문이 공허하고 우회 차단 시 자기 PR을 승인 못 해 교착이다. 작성자 아닌 코드오너가 1인 이상인 다인 구성으로 전환할 때 `true`로 켠다(스펙 §4.1).
- `allowed_merge_methods: ["merge"]`는 저장소 전역이 squash를 허용해도 룰셋이 머지 커밋만 남기게 강제한다(실증). 감사 이력에서 승인 head가 `main` 이력에 부모로 보존된다.
- 효과: 컨트롤러도 승인 관문·머지 방식 제한에 걸린다(실증: 컨트롤러 REST 머지가 `405 New changes require approval from someone other than the last pusher`로 거부). 승인은 PR 작성자가 아닌 사람이 해야 한다(`require_last_push_approval`) — SoT PR은 에이전트가 열고 사람이 승인하므로 성립한다.

### RS-C — sot/* 소스 브랜치 단조 전진 (우회 신원 없음)

| 항목 | 선언 값 |
|---|---|
| `enforcement` | `active` |
| `target` | `sot/*` |
| `rules` | 정확히 `[{ "type": "non_fast_forward" }, { "type": "deletion" }]` (**`pull_request` 룰 금지**) |
| `bypass_actors` | `[]` (반드시 빈 배열) |

- `pull_request` 룰을 담지 않으므로 에이전트의 일반 fast-forward push는 그대로 통과하고, force-push(history 재작성)·브랜치 삭제만 막는다. `sot/*` head가 이전 SHA로 되돌아올 수 없어(단조 전진) 컨트롤러 read-set의 ABA 창이 닫힌다(force-push 롤백 A→B→A 방어, 스펙 §2.8·`ADR-0009` 결정 8).
- **전제(활성화 전 확인)**: 에이전트가 `sot/*`에 rebase·amend(force-push)를 쓰지 않고 새 커밋만 얹어야 한다. 이 전제가 깨지면 RS-C 대신 스펙 §4.1 RS-C 전제 항목이 가리키는 대안(읽기를 head SHA에 결속하는 §3 계약 개정 — 스펙 §2.8 본문에 라벨 정의 보강 필요)으로 재검토한다.
- **RS-B와 분리하는 이유**: RS-B의 `pull_request` 룰을 `sot/*`로 넓히면 `sot/*` push마다 PR을 강제해 에이전트 워크플로가 막힌다.

## 기계판독 선언 블록 (verify_ruleset_config 대조 기준)

`verify_ruleset_config`는 아래 블록을 파싱해 대조 기준으로 삼는다.

```axdt-enforcement-matrix
version: 1
ruleset RS-A enforcement=active target=main separated=true rules=[update] bypass=[User:<controller-actor-id>:always]
ruleset RS-B enforcement=active target=main separated=true rules=[pull_request(required_approving_review_count=1,dismiss_stale_reviews_on_push=true,require_last_push_approval=true,require_code_owner_review=false,allowed_merge_methods=[merge]),non_fast_forward,deletion] bypass=[]
ruleset RS-C enforcement=active target=sot/* rules=[non_fast_forward,deletion] bypass=[] forbid_rules=[pull_request]
```

문법: 한 `ruleset` 당 한 줄. 필드 — `enforcement`(=`active`여야 함), `target`(적용 대상), `rules=[...]`(정확히 존재해야 할 룰·파라미터, 값 일치), `bypass=[...]`(우회 신원 집합; `[]`=비어야 함, `User:<id>:<mode>`=지정 신원만, 추가 신원 불허), `forbid_rules=[...]`(존재하면 불일치가 되는 룰), `separated=true`(다른 룰셋과 합쳐지지 않아야 함). `<controller-actor-id>`는 런타임에 컨트롤러 계정 `actor_id`로 결합한다(Task 1). `#`·빈 줄은 무시한다.

**fail-closed 거부 조건**: 블록 부재·중복·미종결 펜스, 유효 `ruleset` 행 0개, 지원하지 않는 `version`, 중복 `ruleset` ID, 필드 중복, unknown 필드·룰 타입·파라미터, `target`/`rules`/`bypass`/`enforcement` 누락, placeholder(`<controller-actor-id>`) 미해결 또는 비수치, `rules`/`bypass` 내 중복 룰·actor — 이 중 하나라도 있으면 파싱 실패로 대조를 `False`(fail-closed) 처리한다.

## 대조 규칙 (블록 전량 정확 일치)

컨트롤러가 라이브 룰셋을 위 블록과 대조해 `True`(정상)를 내는 조건은 **블록에 선언된 모든 항목이 라이브와 정확히 일치**함이다. 하나라도 어긋나면 `False` → fail-closed로 머지를 거부하고 경보·감사 기록을 남긴다(스펙 §4.1·§3). "존재만"이 아니라 **값 일치**로 검사한다(승인 수 2·dismiss-stale false·비활성 상태 등은 불일치).

1. **세 룰셋이 각각 `enforcement: active`로 실제 적용**돼 있다(`disabled`/`evaluate`면 `False` — 같은 룰이라도 강제하지 않는 fail-open 차단).
2. **RS-A와 RS-B가 각각 존재하며 별개 룰셋으로 분리**(합쳐지지 않았고, RS-A가 삭제되지도 않음)되고, **RS-A의 `rules`가 정확히 `[update]`**, **`bypass_actors`가 정확히 컨트롤러 단독**(추가 actor 불허)이다.
3. **RS-B의 `bypass_actors == []`**이고, **필수 파라미터가 선언값과 정확히 일치**한다: `required_approving_review_count == 1` · `dismiss_stale_reviews_on_push == true` · `require_last_push_approval == true` · `require_code_owner_review == false`(현 1인 구성 비활성, 스펙 §4.1 371행) · `allowed_merge_methods == ["merge"]`, 그리고 `non_fast_forward`·`deletion` 룰이 있다.
4. **RS-C가 존재**하고 대상이 `sot/*`이며 룰 집합이 정확히 `non_fast_forward`·`deletion`이고 **`pull_request` 룰을 담지 않으며** **`bypass_actors == []`**이다.
5. **선언 외 추가**(선언에 없는 룰·actor·대상 확장)가 없다.

> **감시 범위와 정본 정합(P2 필수)**: 위 대조는 기계판독 블록 **전량**을 값 일치로 검사하며, 이는 스펙 §4.1 감시 열거(362·384행: RS-A/RS-B 분리·RS-B `bypass_actors == []`·RS-B 일부 파라미터·RS-C 존재)보다 넓다(`require_last_push_approval`·RS-A `bypass`/`rules`·`enforcement` 활성 상태·초과 배제 포함). 이 초과는 fail-closed 강화 방향이라 안전하나, "선언 전체 대조"를 정본과 정합시키려면 **전제조건 P2**로 스펙 §4.1 감시 열거와 `verify_ruleset_config` 계약(§3·`ports.py` docstring)을 이 블록에 맞추는 정본 개정이 선행돼야 한다(이번 증분 범위 밖). 개정 전까지는 이 블록이 대조 기준이다.

## 켜지 않는 것 (의도적 배제)

| 기능 | 배제 이유 |
|---|---|
| `required_linear_history` | 머지 커밋을 금지해 감사 이력 보존과 충돌한다. |
| `merge_queue` | 개인 소유 저장소에서 룰 생성이 거부된다(실증 `422`). 직렬화는 컨트롤러가 한다. |
| `required_status_checks` | 강제 수단으로 쓰지 않는다. ② 검토 CI 산출물은 컨트롤러가 직접 읽는다(스펙 §2.4·§4.2). |
