# 회신 — 강제-필수 경로 보호 (CODEOWNERS 커버리지 · 코드오너 검토 강제)

> 작성: phase3-isolation-infra 세션(Phase 3) · 대상: **Phase 6 세션**(phase5-agent-runner)
> 응답 대상: `WIP/handoff-phase6-enforcement-critical-paths.md`(phase6-enforcement 브랜치, 커밋 3202f45) §5 네 항목 + §6 미결.
> 상태: Phase 3 소관 항목 처리 완료(정본 반영은 미커밋·사용자 게이트 PR 대기). 아래는 결정·근거·Phase 6가 가정할 수 있는 것.

## 요약

| handoff §5 항목 | Phase 3 회신 |
|---|---|
| 5.1 귀속 수용 | 수용. 경로 정책·커버리지 대상 경로 정의는 Phase 3 소유. CODEOWNERS 파일 생성·룰셋 설정은 Phase 6/9. |
| 5.2 커버리지 반영 | 강제-필수 경로를 `rule-protected-paths`의 `axdt-critical-paths` 블록으로 반영. CODEOWNERS 파일은 아직 저장소에 없어(계획 단계) 파일 생성·경로 문자열 확정은 게이트 코드 정식 이관 + 룰셋 활성화 시점으로 미룸. |
| 5.3 코드오너 검토 강제 확인 | `require_code_owner_review`는 이 저장소에서 기능 제약은 없으나 **현 1인 구성에선 실효 없음**(아래). 다인 구성 전환이 전제조건. 그전까지 방어는 게이트 세 번째 분기의 결정권자 명단 검사에 의존 — handoff §3.2 전제 유효. |
| 5.4 경로 집합 단일 정의 | `axdt-critical-paths` 블록을 권위 정의로 확정. Phase 6 게이트가 이 블록을 읽는다. 손사본 금지, 변경 측(Phase 3)이 소비 측(Phase 6)에 통보. |

## 5.1 귀속 수용

수용한다. `.github/CODEOWNERS`의 내용·경로 커버리지, 경로 정책(`rule-protected-paths`), 코드오너 검토가 걸리는 대상 경로의 정의는 Phase 3 소유다. CODEOWNERS **강제**(호스트 룰셋 `require_code_owner_review`)와 게이트 코어(세 번째 분기)는 Phase 6 몫이라는 §4 층 경계도 그대로 받는다.

## 5.2 커버리지 반영

§2 강제-필수 경로를 `rule-protected-paths`(`docs/sot/rule/protected-paths.md`)에 **`axdt-critical-paths` 기계용 블록**으로 반영했다. 현재 등재:

- `critical docs/sot/rule/**` — 판정 키(규칙 지문)의 원천.
- `critical .github/workflows/**` — handoff §2는 "② 검토 CI 워크플로"만 지목했으나 **전체로 넓혔다**(보수적 확장). 이유: 워크플로 파일명 변경·신규 악성 워크플로 추가에 강건하고, 보안 통제는 과포함 쪽 오류가 안전하다. ② CI 파일명이 확정되면 좁힐 수 있다. — **이 확장을 변경 측 통보로 알린다**(§5.4 통보 규약).
- `critical .github/CODEOWNERS` — 자기 자물쇠.
- `critical WIP/axdt/infra/hubgate.py` — Phase 3 게이트 코드(hubgate)의 구현 예정 경로를 **잠정** 포함해 과도기 공백을 지금 닫는다(파일 생성 전엔 매칭 없음).

**CODEOWNERS 파일 자체는 아직 저장소에 없다**(main·phase3-followup·phase6-enforcement 어느 브랜치에도 없음 — 실측). handoff §3.1이 말한 "sub-spec이 커버리지를 적는다"는 계획 단계다. 그래서 이번에 파일을 만들지 않았다. 근거는 두 가지다.

1. 커버리지의 **권위 정의**를 파일이 아니라 `axdt-critical-paths` 블록에 둔다(§5.4). 파일을 별도로 만들면 손사본이 생긴다.
2. 코드오너 검토가 현 구성에서 실효가 없다(§5.3). 실효 없는 CODEOWNERS 파일을 지금 두면 "커버리지가 걸려 있다"는 거짓 안전감만 준다.

따라서 실제 `.github/CODEOWNERS` 파일 생성·경로 문자열 확정은 **(ㄱ) 게이트 코드 정식 이관 위치 확정 + (ㄴ) 저장소가 다인 구성으로 전환되어 코드오너 검토가 유효해지고 + (ㄷ) Phase 6 룰셋(`require_code_owner_review`) 활성화** 시점에 맞추며, 그때 `axdt-critical-paths` 블록을 소스로 삼아 커버리지를 생성한다. 이 대응은 `protected-paths.md`의 블록 하단에 명시돼 있다.

**게이트 코드 경로**: Phase 3 hubgate는 `WIP/axdt/infra/hubgate.py`(잠정)로 등재했다. Phase 6 게이트·컨트롤러 코어의 정식 이관 위치가 확정되면 **Phase 6가 변경 측으로서** 그 경로를 블록에 추가·통보한다(블록 주석에 자리표시). WIP/ 밖 정식 위치로 이관되면 task-push 축(`axdt-protected-paths`)의 `deny` 대상 여부도 함께 재검토한다.

## 5.3 코드오너 검토 강제 확인

`require_code_owner_review`가 이 저장소 구성에서 성립하는지 검증했다.

- **기능 제약 없음**: 저장소는 public·개인(User) 소유다. `require_code_owner_review`(브랜치 룰셋의 `required_reviewers` 계열)는 이 구성에서 사용 가능하다 — 조직·팀 플랜을 요구하지 않는다. CODEOWNERS 판정도 팀 없이 개인 계정 지정으로 성립한다.
- **그러나 현 구성에선 실효 없음**: 코드오너 = 저장소 소유자 1인이고 대부분의 PR 작성자도 그 1인이다. GitHub은 **자기 PR의 코드오너 승인을 셀프 승인으로 인정하지 않는다**. 결과는 둘 중 하나다.
  - 룰셋에서 코드오너 검토를 **우회(bypass) 허용**하면 → 관문이 공허하다(작성자가 그냥 통과).
  - 우회를 **끄면** → 자기 PR을 자기가 승인 못 해 **교착**(머지 불가). 봇/타인 리뷰어가 없으면 저장소가 잠긴다.
- **결론**: 코드오너 검토 강제는 **작성자 ≠ 코드오너인 리뷰어가 2인 이상 있을 때만** 비공허하다. 그전까지 이 관문은 실질 방어를 주지 못한다.

**Phase 6 활성화 전제조건 회신**: `require_code_owner_review`를 방어의 축으로 삼으려면 다인 구성(작성자 ≠ 코드오너) 전환이 선행돼야 한다. 그 전에는 handoff §1의 방어가 **게이트의 세 번째 분기(결정권자 명단 검사)** 하나에 걸린다 — 이는 handoff §3.2가 이미 인정한 상태("막히더라도 게이트의 명단 검사가 결정권을 좁히므로 설계는 성립")이며, 그 전제는 유효하다. 즉 Phase 6는 코드오너 검토를 **필수 전제로 가정하지 말고**, 결정권자 명단 검사를 1차 방어로 두고 코드오너 검토는 다인 구성 시 보강되는 2차 관문으로 설계하라.

## 5.4 경로 집합 단일 정의

§2 강제-필수 경로의 권위 정의를 `rule-protected-paths`의 **`axdt-critical-paths` 블록**에 둔다. 조율 결과는 다음과 같다.

- **단일 원천**: Phase 6 머지 게이트는 이 블록을 읽어 "이 PR이 강제-필수 경로를 건드리나"를 판정한다. 경로 목록을 Phase 6 쪽에 복제하지 않는다(손사본 금지).
- **두 축 분리**: 같은 파일에 **task-push 축**(`axdt-protected-paths`, 허브 pre-receive가 push 거부)과 **강제-필수 축**(`axdt-critical-paths`, 머지 게이트가 결정권자 승인 요구)을 별개 블록으로 둔다. 펜스 정보 문자열로 구분해 파서가 섞지 않는다. `docs/sot/rule/**`처럼 두 축에 함께 걸리는 경로는 **push 시엔 거부**(task 브랜치가 못 만짐)·**PR 시엔 결정권자 승인**(정식 절차로 바꿀 땐 승인 필요)으로 이중 적용되며, 강제 지점이 달라 모순이 아니다.
- **통보 규약**: 이 목록을 바꾸는 측(Phase 3)이 소비 측(Phase 6)에 통보한다. 이번 `.github/workflows/**` 보수적 확장이 그 첫 통보다(위 §5.2).
- **읽는 방식**: 게이트는 블록의 `critical <glob>` 줄만 취한다. glob 의미(`**`=구분자 포함 0+ 세그먼트, `*`=한 세그먼트 내)는 task-push 블록과 동일하며 그 문법 정의가 정본이다. 게이트 코어 로직(세 번째 분기: 포크 거부 + 결정권자 승인 확인)은 Phase 6 소관이므로 이 블록은 **입력 데이터만** 제공한다.

## §6 미결 대응

- **결정권자 명단 저장 위치**(handoff §6, 리뷰 발견 7): Phase 6 미결. 저장소 **안**에 둘 경우 그 경로도 `axdt-critical-paths`에 추가한다(블록 주석에 자리표시 등재). 저장소 **밖**(컨트롤러 도메인)이면 해당 없음. 확정 시 Phase 6가 변경 측으로 통보.
- **게이트·컨트롤러 코드 정식 이관 위치·배포 pin**(sub-spec §8): 확정되면 §2·`axdt-critical-paths` 경로를 갱신한다. **전제조건**: Phase 6 활성화 전에 반드시 실제 게이트·컨트롤러 코드 경로를 이 블록에 추가한다(현재는 hubgate 잠정 경로만 등재 — 블록 주석에 명시).

## 후속

- **`ADR-0009` 착지 정리**: `rule-protected-paths`는 현재 "강제 = 머지 컨트롤러" 결정을 `ADR-0009`로 **forward 표기**(Phase 6 신설 예정, phase6-enforcement 브랜치에 `proposed`)하고 `related`에서는 뺐다. `ADR-0009`가 `main`에 착지하면 이 forward 표기를 확정 참조로 정리하고 `related`에 등재한다.
- **경로 확정 시 재통보**: ② 검토 CI 파일명 확정 시 `.github/workflows/**` 확장 축소 여부 재검토, 게이트 코드 정식 경로 확정 시 잠정 경로 교체 — 둘 다 변경 측 통보 규약을 따른다.

## 참조

- `docs/sot/rule/protected-paths.md`(강제-필수 경로 `axdt-critical-paths` 블록 · task-push 축 `axdt-protected-paths` 블록).
- `WIP/adr/0007-layered-enforcement.md`(층별 강제 — (a) ref 허용목록 · (b) 콘텐츠·경로 게이트).
- `WIP/specs/2026-06-26-phase3-isolation-infra-design.md` §6.1a(hubgate 설계).
- 원 handoff: `WIP/handoff-phase6-enforcement-critical-paths.md`(phase6-enforcement, 3202f45).
