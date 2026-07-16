---
id: ADR-0015
title: 베이스 규칙의 scope는 전부 local로 두고, global은 도메인 콘텐츠 규칙에 유보한다
status: accepted
date: 2026-07-13
decision: D31
related: [ADR-0014, rule-sot-readiness, rule-terminology, rule-adr-recording]
---

# ADR-0015: 베이스 규칙의 scope는 전부 local로 두고, global은 도메인 콘텐츠 규칙에 유보한다

## 상태
Accepted (2026-07-13) · 관련 결정 D31

## 맥락
규칙 frontmatter `scope`는 규칙이 바뀌었을 때 그 변경이 **적용 규칙 지문(판정 키 성분(2))에 들어가 완료 무효화를 유발하는지**를 게이팅한다 — `global`이면 항상 들어가고, `local`이면 그 규칙을 `rules`에 선언한 문서가 있을 때만, 미기재면 보수적으로 `global` 취급(ADR-0014). 무효화가 유발되면 재검토는 projection 전량 홀리스틱이다(부분 문서 타겟팅 없음). 그런데 `docs/sot/rule/`의 규칙 10종에 `scope`가 없어 전부 `global`로 취급되고 있었다(선례: `rule-adr-recording`만 `scope: local` 보유). 이들 중 하나만 편집해도 완료된 SoT 전량 재검토가 헛발화한다.

핵심 맥락: `docs/sot/`의 요구·사양·테스트설계는 **대상(target) 프로젝트의 콘텐츠**다(AXDT 자체 구현은 `WIP/`). 그래서 "이 규칙이 대상 프로젝트의 SoT 콘텐츠(요구·사양·테스트가 '무엇을' 말하는가)를 실제로 제약하는가"가 scope 판정의 관건이다. 10종은 모두 오케스트레이션(브랜치·워크스페이스 명명, 통신·상태 규범)이거나 거버넌스·완료정책(보호 경로, SoT 변경 게이트, 완료 판정)이다. 이들은 대상 콘텐츠가 '무엇을' 말하는지를 제약하지 않는다.

이 결정을 phase1 다중모델 리뷰(Codex-Sol·Fable)에 부쳤다. Fable은 10종 전부 local을 지지했다. Codex-Sol은 `terminology`·`sot-change-user-gate`·`sot-readiness`를 global 후보로 봤는데, 실질 우려는 "완료 판정·게이트 정책이 바뀌면 완료가 무효가 돼야 한다"였다 — 이는 `scope`(적용 규칙 지문 게이팅)가 아니라 판정 키의 정책 결속(ADR-0014)으로 다뤄야 할 문제다.

## 결정
1. **규칙 10종에 전부 `scope: local`을 부여한다.** `terminology`·`branch-workspace-naming`·`progress-single-writer`·`subagent-no-direct-communication`·`leader-coordination-via-maintainer`·`report-to-progress-authority`·`propagation`·`protected-paths`·`sot-change-user-gate`·`sot-readiness`. global은 없다.
2. **`global`은 미래의 도메인 콘텐츠 규칙에 유보한다** — 공용 용어집, 공용 식별자 명명처럼 대상 SoT 콘텐츠를 실제로 횡단 제약하는 규칙. 현행 10종에는 해당이 없다.
3. **분류 기준을 명문화한다.** 콘텐츠 규범(대상 SoT가 '무엇을' 말하는지 제약) → 횡단성에 따라 global/local. 거버넌스·완료정책(누가·어떻게 절차를 밟는지) → local. 이 기준을 `scope` 주석과 `docs/sot/rule/README`에 적는다.
4. **완료정책 규칙의 완료 결속은 `scope`가 아니라 판정 키가 담당한다.** `sot-readiness`·`sot-change-user-gate`가 바뀌면 완료가 무효가 돼야 하지만, 그 결속은 ADR-0014의 `review_policy_epoch`가 맡는다. 그래서 이 두 규칙도 local로 둘 수 있다.
5. `rule-sot-readiness`의 global 예시 문구 **"용어·네이밍 등 횡단"**을 **"도메인 공용 용어·공용 식별자 명명(브랜치 명명이 아님)"**으로 정정한다 — 현행 네이밍 규칙(`branch-workspace-naming`)은 오케스트레이션이라 global 예시로 부적절하다.
6. Codex-Sol이 제안한 `kind:` 필드 개편(규칙을 콘텐츠/거버넌스 종류로 명시 분류)은 **보류**한다. 현 global/local 이분에 분류 기준 문서화를 더하면 충분하다.

## 결과
**좋은 점**
- 오케스트레이션·거버넌스 규칙을 편집해도 **정합성** 완료 전량 재검토가 헛발화하지 않는다 — 이들은 어느 완료 문서도 `rules`에 선언하지 않아 그 본문 편집이 성분(2) 적용 규칙 지문에 안 들어간다(정합성 무효화가 발화하지 않음). 선언 완전성 검사는 완전성 스윕 키를 통해 이런 편집에도 재실행되지만, 새 의존이 없으면 `completeness_clear`라 완료를 유지한다.
- "이 규칙이 대상 콘텐츠를 제약하는가"라는 단일 기준으로 scope를 판정할 수 있어, 앞으로 규칙을 추가할 때 global/local 선택이 명확하다.

**대가 / 주의**
- 10종이 local이면 대상 SoT가 이들을 `rules`에 선언할 일이 거의 없어, 이 규칙 변경이 **정합성** 재검토를 촉발하지 않는다(완전성 스윕은 카탈로그 본문 변경으로 돌지만 새 의존이 없으면 clear). 이는 의도된 동작이다 — 이들은 콘텐츠 정합이 아니라 절차·강제의 문제이며, 규칙 목록 구조 변화는 ADR-0014의 카탈로그 manifest digest가, 완료정책·실행기 변화는 epoch가, 미선언 의존은 완전성 스윕 키가 잡는다.
- `kind:` 개편을 미루므로, 콘텐츠/거버넌스 구분은 필드가 아니라 문서화된 기준에만 의존한다. 규칙이 늘어 이분이 흔들리면 그때 `kind:` 도입을 재검토한다.

## global은 왜 존치하는가 (대상 프로젝트 계약 표면)
현행 11종이 전부 local이어서 `global`이 지금 비어 있지만, 이는 죽은 축이 아니라 아직 대상이 없는 축이다. `docs/sot/`의 규칙이 전부 local인 것은 이들이 AXDT라는 틀 자체를 규정하는 오케스트레이션·거버넌스라서이고, `global`이 걸릴 콘텐츠 규범은 AXDT로 만드는 **대상 프로젝트의 SoT**에서 나타난다 — 도메인 공용 용어집, 도메인 엔티티·필드 명명(브랜치 명명이 아님), 단위·표기 규약(예: 날짜 ISO 8601, 통화 ISO 4217), 규제·컴플라이언스 콘텐츠 의무 같은 것들이다. 이런 규칙은 전 문서가 예외 없이 지켜야 하고 문서별 `rules` 선언에 맡기면 하나만 빠뜨려도 규칙이 안 걸리므로(fail-open), 선언 없이 항상 적용되는 `global`이 맞다. 또한 이는 콘텐츠 부합 기준이라 판정 방법의 버전(epoch)이나 결정적 형식 검사(sot-lint)로는 다룰 수 없다. `rule-sot-readiness` 계약과 sot-lint는 대상 프로젝트에서 도는 엔진이므로, `global`은 'AXDT가 언젠가 쓸지 모를 기능'이 아니라 **엔진이 대상 프로젝트에 제공하는 계약 표면**이다. 이 축을 지금 제거하면 대상 프로젝트의 도메인 콘텐츠 규칙 지원을 포기하게 되고, `scope` 값 도메인이 `{local}`로 좁아져 오히려 특수화가 필요해진다.

## 검토한 대안
### 대안 A — terminology·sot-change-user-gate·sot-readiness를 global (Codex-Sol 초안)
완료·게이트·용어 규칙을 global로. · **기각**: `global`은 그 규칙 본문을 적용 규칙 지문에 넣어 재검토를 촉발할 뿐, 검토 스킬·모델·프롬프트 같은 실행 정책 버전을 키에 새기지 못한다. 이들은 대상 콘텐츠를 제약하는 콘텐츠 규범도 아니다. 완료·게이트 정책의 완료 결속이라는 실질 우려는 ADR-0014(epoch)로 정확히 해결된다.

### 대안 B — `kind:` 필드로 규칙 종류를 명시 분류 (Codex-Sol 제안)
frontmatter에 콘텐츠/거버넌스 `kind`를 두고 scope 규칙을 종류에 연동. · **기각(보류)**: 현 규모(10종)에는 과설계다. 분류 기준을 README·주석에 적으면 같은 효과를 얻는다. 규칙이 늘어 이분으로 부족해지면 재도입한다.

### 대안 C — 미기재 그대로(전부 global 취급) 유지
`scope`를 채우지 않고 보수적 global에 맡긴다. · **기각**: 오케스트레이션·거버넌스 규칙 편집마다 완료 전량 재검토가 헛발화한다. 문제의 출발점 그대로다.

## 촉발 근거 (rule-adr-recording 도그푸딩)
이 결정은 `rule-adr-recording`의 촉발 조건 중 **공유 계약(규칙 frontmatter `scope` 의미·분류) 변경**과 **대안 기각**(global 후보·`kind:` 개편)에 걸린다. 규칙 10종의 scope를 확정하고 분류 기준을 세우는 결정이므로 ADR로 기록한다. ADR-0014와 짝을 이룬다 — 완료정책 규칙을 local로 둘 수 있는 근거가 그 epoch다.
