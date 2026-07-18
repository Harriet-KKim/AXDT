# 핸드오프 — 강제-필수 경로 보호 (CODEOWNERS 커버리지 · 코드오너 검토 강제)

> 작성: phase5-agent-runner 세션(Phase 6 강제 증분 설계 중, 2026-07-13) · 대상: **Phase 3 세션**(phase3-isolation-infra)
> 근거: `ADR-0009`(강제 = 머지 컨트롤러) · Phase 6 강제 증분 sub-spec(`WIP/specs/2026-07-08-phase6-enforcement-host-branch-protection-design.md`) · 다중 모델 리뷰(Codex·Fable) 발견 3.
> 성격: draft가 아니라 **요구 전달 + 조율 요청**이다. Phase 6 브랜치는 CODEOWNERS·검증 코드를 손대지 않는다(그쪽이 그 데이터를 변경 중이므로 충돌 방지).

## 0. 무엇을 넘기나

Phase 6 강제(SoT 완료 ①②③를 머지 컨트롤러가 강제)의 다중 리뷰에서 나온 결함 하나가 CODEOWNERS·경로 정책·검증 코드에 걸린다. 그 데이터는 Phase 3 소관이고 지금 Phase 3가 변경 중이라, Phase 6가 그 위에서 무엇을 가정하는지와 무엇이 필요한지를 넘긴다. 게이트 코어의 로직(아래 세 번째 분기) 자체는 Phase 6가 구현한다.

## 1. 배경 — 결함과 결정

리뷰 발견 3: 컨트롤러는 저장소의 **모든** 머지를 수행한다. 완료 강제(①②③)는 SoT 문서 트리(`docs/sot/{requirements,specification,test-design}`)를 바꾸는 PR에만 적용하고, 그 외 PR은 열려 있기만 하면 통과시킨다(pass-through). 그런데 **강제 장치 자체**를 바꾸는 PR은 SoT 문서 트리를 건드리지 않으므로 이 pass-through에 걸려 무관문으로 머지된다. 포크 거부도 SoT PR에만 적용되어 여기엔 걸리지 않는다.

무관문으로 통과하면 안 되는 경로(아래 §2)를 바꾸는 PR은, 예컨대 ② 검토 CI를 "무조건 통과 산출물을 내는" 버전으로 교체할 수 있다. 그러면 이후 모든 SoT PR에서 ①②가 무력화되고 ③만 남는다.

결정(사용자 확정): 게이트 코어에 **세 번째 분기**를 둔다. 강제-필수 경로를 바꾸는 PR에는, 형식·검토(①②)는 요구하지 않되(규칙의 pass-through 조항과 충돌 회피), 최소한 (ㄱ) 포크 거부와 (ㄴ) 결정권자(저장소 권한 admin ∧ 지정 명단) 승인 존재를 요구한다. 아울러 CODEOWNERS 커버리지에 게이트 코드 경로를 더하고, 코드오너 검토 강제(`require_code_owner_review`)를 활성화 전제조건으로 올린다. 뒤 두 항이 Phase 3 접점이다.

## 2. 강제-필수 경로 집합 (Phase 6가 가정하는 것)

Phase 6가 "이 경로를 바꾸는 PR은 무관문 통과가 아니다"라고 가정하는 경로. 이 집합의 권위 정의를 어디에 둘지는 §5에서 조율한다.

- `docs/sot/rule/**` — 판정 키의 절반인 규칙 지문의 원천.
- `.github/workflows/` 중 ② 검토 CI 워크플로 — 판정 산출물을 만드는 주체.
- `.github/CODEOWNERS` — 아래 커버리지가 걸리는 파일 자신(자기 자물쇠).
- 게이트·컨트롤러 코드 경로(현재 `WIP/axdt/sot_gate/`, 정식 위치는 이관 예정). 컨트롤러는 저장소 밖에서 돌지만 코드 출처·배포 pin이 아직 미결(sub-spec §8)이라, 배포 방식에 따라 저장소 코드가 곧 실행 코드일 수 있다.
- 결정권자 명단의 저장 위치 — **저장소 밖(컨트롤러 도메인)으로 확정**(§2.7·§10, 2026-07-18)이라 이 블록·CODEOWNERS 커버리지엔 **해당 없다**. 저장소 안 구성으로 바뀌면 그때 포함(발견 7 해소).

## 3. Phase 3에 필요한 것

1. **CODEOWNERS 커버리지 확장.** 현재 sub-spec은 CODEOWNERS가 `docs/sot/**`·`.github/**`를 지정 admin에 묶는다고만 적는다. §2의 게이트 코드 경로가 빠져 있다(Fable 지적). 이 경로가 결정권자에 묶이도록 커버리지에 포함이 필요하다. 실제 경로 문자열은 코드 이관 위치가 확정되면 갱신한다.

2. **코드오너 검토 강제 확인.** `require_code_owner_review: true`가 개인 소유 public 저장소에서 허용되는지, 팀이 없는 저장소에서 CODEOWNERS 판정이 어떻게 이뤄지는지 미검증이다(sub-spec은 실증을 `false`로 돌렸다). 이것을 강제 활성화의 전제조건으로 확인해야 한다. 막히더라도 게이트의 명단 검사가 결정권을 좁히므로 설계는 성립하나, 이 관문이 없으면 §1의 방어가 게이트의 세 번째 분기 하나에만 걸린다.

3. **경로 집합의 단일 정의 조율.** §2의 강제-필수 경로는 Phase 6 게이트가 읽고, Phase 3의 경로 정책(`rule-protected-paths`)도 경로를 다룬다. 두 곳이 같은 경로를 각자 정의하면 손사본이 갈린다. 권위 정의를 어디에 둘지(예: `rule-protected-paths`에 강제-필수 축을 추가하고 Phase 6가 그것을 참조) 조율이 필요하다. 변경 측이 소비 측에 통보하는 규약을 함께 정한다.

## 4. 층 경계

- **Phase 3 몫**: `.github/CODEOWNERS` 파일 내용·경로 커버리지, 경로 정책(`rule-protected-paths`), 검증 코드, 허브 pre-receive(경로/ref). 코드오너 검토가 걸리는 대상 경로의 정의.
- **Phase 6 몫**: 호스트 브랜치 룰셋(RS-A/RS-B) 설정, 머지 컨트롤러와 게이트 코어, 세 번째 분기 로직(포크 거부 + 결정권자 승인 확인). 코드오너 검토 강제 자체는 RS-B의 `require_code_owner_review` 파라미터라 룰셋 설정(Phase 6/9)이지만, 그 대상 경로 커버리지는 Phase 3와 공유한다.

CODEOWNERS는 GitHub 호스트 기능이므로 강제는 호스트 층(Phase 6)이지만, 파일과 경로 커버리지는 Phase 3가 관리하는 데이터다. 두 층이 같은 경로 집합을 봐야 해서 이 handoff가 필요하다.

## 5. Phase 3 세션이 정할 것

- **귀속 수용**: CODEOWNERS 커버리지·코드오너 검토 대상 경로를 Phase 3가 소유하는지 확인.
- **커버리지 반영**: §2의 경로(특히 게이트 코드 경로)를 CODEOWNERS 커버리지에 반영. 경로 문자열은 코드 이관 위치 확정 후 갱신.
- **코드오너 검토 강제 확인**: `require_code_owner_review`가 이 저장소 구성에서 성립하는지 검증하고, 결과를 Phase 6 활성화 전제조건에 회신.
- **경로 집합 단일 정의**: §2 강제-필수 경로의 권위 정의 위치와, Phase 6 게이트가 그것을 읽는 방식을 조율. 손사본을 만들지 않는다.

## 6. 미결 주의

이 handoff는 결정 3(세 번째 분기, 사용자 확정)에 근거한다. 다만 다음은 Phase 6에서 아직 확정 전이라, 확정되면 §2·§3의 경로가 갱신될 수 있다.

- ~~결정권자 명단의 저장 위치(저장소 안/밖) — 리뷰 발견 7, 반영 진행 중.~~ **해소(2026-07-18): 저장소 밖 확정(§2.7·§10)** — PR #17 블록도 반영("명단은 저장소 밖에 둔다").
- 게이트·컨트롤러 코드의 정식 이관 위치와 배포 pin — sub-spec §8(여전히 미결, Phase 9). PR #17 블록은 현재 위치 `WIP/axdt/sot_gate/**`를 잠정 등재했고, 정식 이관 시 Phase 6가 경로 갱신을 통보한다.

## 참조
- `ADR-0009`(강제 = 머지 컨트롤러) · sub-spec `WIP/specs/2026-07-08-phase6-enforcement-host-branch-protection-design.md`(§2.6 pass-through · §4.1 CODEOWNERS·`require_code_owner_review` · §5 패키지 레이아웃 · §8 provisional).
- 다중 모델 리뷰 발견 3·6·7(검토서 Artifact).
- 선행 handoff: `WIP/handoff-hub-main-ref-protection.md`(허브 `main` ref 보호, 같은 세션→Phase 3) · `WIP/handoff-sot-readiness-crossphase.md`(강제 층 귀속).
- `rule-protected-paths`(경로 정책, Phase 3) · `rule-sot-readiness`(완료 정의·강제 매핑).
