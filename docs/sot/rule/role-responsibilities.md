---
id: rule-role-responsibilities
title: 역할별 책임 경계와 쓰기 경로는 이 표가 단일 명세다
status: active
scope: local
related: [rule-protected-paths, rule-adr-recording, rule-subagent-no-direct-communication, rule-progress-single-writer, rule-report-to-progress-authority, rule-sot-change-user-gate, rule-terminology, ADR-0007]
---

# 역할별 책임 경계와 쓰기 경로는 이 표가 단일 명세다

## 규칙문
> AXDT의 다섯 역할(**Maintainer·Leader·Developer·Reviewer·Tester**)의 책임 경계·실행 위치·능력 등급·쓰기 경로·강제 등급은 **아래 표가 단일 명세**다. `WIP/axdt/roles/`의 역할 선언(RoleSpec·시스템 프롬프트)은 자신이 근거한 규칙 id를 `rule_refs`로 이 문서에 명시하고, **역할 → 쓰기 경로 매핑은 이 표의 값과 등가(=)**여야 한다 — 계약 검사가 대조한다(스펙 §8.2). 역할 축 뷰의 권위본은 이 문서이며, `rule-protected-paths`는 경로 축 규칙으로 남는다(파싱 대상 아님). 두 문서의 명세가 겹칠 때는 **더 제한적인(더 좁은 권한) 쪽이 이긴다.**

Watcher는 이 표 밖이다 — 실행 형태도 시스템 프롬프트 유무도 확정되지 않았다(스펙 §2.4). 강제 등급 열의 일부 칸은 아직 측정 전이라 확정값이 아니라 `측정 대상`으로 두며, 그 근거와 예상치는 표 아래 각주에 있다. 한 파일 = 한 규칙(역할 축 단일 명세).

## 근거
- 역할별 쓰기 권한이 여러 규칙·프롬프트에 흩어지면 강제·검사가 참조할 **기계가 읽을 단일 목록**이 없다. 이 표가 역할 축의 그 목록이다.
- `rule-protected-paths`는 경로 축(무엇이 보호 대상이고 허브 게이트가 무엇을 막는가) 규칙이다. 역할 축 뷰를 거기서 기계적으로 뒤집으려면 한국어 산문을 해석해야 하고, 그 해석 로직 자체가 세 번째 사본이 된다. 그래서 역할→쓰기 경로는 이 표가, 경로→보호는 `rule-protected-paths`가 각각 단일 오라클이다. 두 문서가 겹치는 부분은 파서가 아니라 사람이 사용자 게이트 PR에서 대조한다.
- 설계 논증은 스펙 §2.2·§3, `ADR-0007`(신뢰 루트 모델)에 있다 — 규칙은 "무엇을", 스펙·ADR은 "왜 이렇게"를 담는다.

## 적용범위
- **대상**: 다섯 역할의 선언(`WIP/axdt/roles/spec.py`·`prompts/<role>.md`)과 그 계약 검사. **역할 id 열**과 **쓰기 경로 glob 열**이 기계 대조 대상이다.
- **예외**: Watcher는 대상이 아니다(스펙 §2.4 별도 작업). 역할 간 경로 구분(Developer는 주로 `src/**`, Tester는 `test/**`)은 이 표가 명세하되 기계 강제 대상이 아니다 — 아래 강제 등급 각주 참고.

## 역할 명세 (단일 명세)

기계 대조 열은 **역할 id**와 **쓰기 경로(glob)** 둘이다. 나머지 열은 사람이 읽는 명세다.

| 역할 id | kind | 실행 위치 | 능력 등급 | 쓰기 경로 (glob) | 강제 등급 |
|---|---|---|---|---|---|
| `maintainer` | SESSION | 호스트 | `HOST_CONTROL` | `docs/interim/progress.md`, `docs/interim/plan/**`, `docs/interim/sot-readiness-review.md`, `docs/interim/**/README.md`, `docs/interim/**/_TEMPLATE.md`, `docs/interim/ADR/*.md` ⁵ | **부재** ¹ |
| `leader` | SESSION | 컨테이너 | `WRITE_WORKSPACE` | `src/**`, `test/**`, `docs/interim/report/${task}.md` ² | 게이트 + 허브 경로 강제 |
| `developer` | SUBAGENT | Leader 세션 | `WRITE_WORKSPACE` | `src/**`, `test/**` | 권고 (역할 간 경로 구분) ³ |
| `reviewer` | SUBAGENT | Leader 세션 | `READ_ONLY` | (없음) | 측정 대상 ⁴ |
| `tester` | SUBAGENT | Leader 세션 | `WRITE_WORKSPACE` | `test/**` | 권고 (역할 간 경로 구분) ³ |

**강제 등급 열은 두 축을 겸한다**(스펙 §3): `reviewer` 행은 *능력 등급*의 강제를, `developer`·`tester` 행은 *역할 간 경로 구분*의 강제를 가리킨다. 능력 등급의 강제는 sub-agent에서 **현재 게이트로 서술**하되 — Reviewer는 §8.3a 항목 7의 측정 대상이라 측정 후 기계 승격이 열려 있는 **예상값**이고 확정이 아니다 — 역할 간 경로 구분은 모두 권고다.

**Watcher는 이 표에 없다.** `RoleSpec`이 아니며 스펙 §3에는 비-`RoleSpec` 항목으로만 적힌다(실행 형태·시스템 프롬프트 미확정, §2.4). 이 단일 명세 표의 기계 대조 대상은 다섯 역할뿐이다.

**각주**

¹ **부재 = 강제의 결여.** Maintainer는 호스트 정본 작업본에 직접 쓰고 허브 push를 거치지 않으므로(`ADR-0007`: main은 push가 아니라 fetch/update-ref로 갱신) 경로 강제도 허브 게이트도 적용되지 않고, 그를 검토할 상위 주체도 없다. 사후 통제는 사용자 게이트뿐이다. "권고"로 적으면 잡아줄 누군가가 있는 것처럼 읽히므로 **부재**로 표기한다. (Codex Maintainer의 `HOST_CONTROL` 번역 — `-s danger-full-access` + 승인 정책 — 이 실제로 호스트 제어를 주는지는 `측정 대상`이나(§8.3a-9), 그 결과는 이 강제 등급을 바꾸지 않는다.)

² **report 경로는 task 스코프다.** Leader는 **자신에게 배정된 task의** `docs/interim/report/<그 task>.md`만 쓴다(다른 task의 report 금지). ref↔경로 정합은 허브 게이트가 강제하고, ref 위장 차단은 하드닝 전까지 advisory다(`rule-protected-paths`·`ADR-0007`). 기계 대조 시 이 항목은 정적 glob이 아니라 배정 task로 파라미터화된다(`${task}`).

³ **역할 간 경로 구분은 권고다.** `rule-protected-paths`가 `src/**`·`test/**`를 "자유(보호 대상 아님)"로 두므로 허브 게이트가 모르고, 능력 등급도 Developer와 Tester를 가르지 않는다. 프롬프트가 지시하고 Leader의 리뷰가 잡는다(스펙 §2.2). 이 구분은 강제가 아니라 명세다.

⁴ **`측정 대상` — 예상: 게이트 (Phase 5 판정기 이후 측정 후 기계 승격 후보).** Reviewer의 `READ_ONLY`가 실제로 쓰기를 막는지는 §8.3a 항목 7의 측정 대상이다. `--tools`가 도구 집합에서 쓰기 도구를 제거하면 **기계** 등급이고, `--permission-mode plan`이 시도를 거부만 하면 **게이트**다(스펙 §2.3.1·§2.3.2). §8.3a 측정은 훅 기반 판정기 재설계 이후로 재-시퀀싱됐으므로(§8.3a 주 · `WIP/handoff-state-detection-redesign.md`), 확정값은 **Phase 5 이후 별도 사용자 게이트 PR**로 이 칸을 채운다. 그 전까지 이 칸을 참으로 적지 않는다(스펙 §10). 예상치("게이트, 기계 승격 후보")는 Phase 5가 확인·반증할 가설이지 확정이 아니다. **코드(`roles/spec.py`)의 `enforcement` 필드는 이 보수적 서술값(`GATED`)을 담고, 계약 검사는 강제 등급 열을 대조하지 않는다** — 역할 id·쓰기 경로만 대조하므로(§2.2) 표 칸의 `측정 대상`과 코드의 `GATED`는 이 규약으로 정합한다.

⁵ **ADR 기록은 Maintainer가 한다.** `docs/interim/ADR/*.md`(ADR 본문)의 작성 주체는 Maintainer다. Leader는 진행 중 내린 설계 결정을 ADR로 남길 필요가 있으면 자기 report로 **제안**하고, Maintainer가 기록한다 — `plan`과 같은 "제안(Leader) → 기록(Maintainer)" 패턴이다(스펙 §2.6). 이 표는 ADR 파일의 **쓰기 권한**(누가 쓰나)만 정한다 — ADR을 **언제·왜 남기고 어떻게 강제하는가**(기록 의무·촉발 조건·강제 수준)는 `rule-adr-recording`이 정하며, 두 규칙은 서로 다른 축이라 함께 성립한다. `rule-adr-recording`의 기록 의무는 역할 무관이고(누가 결정했든 큰 결정은 기록), Leader는 그 의무를 report 제안으로 충족한다(파일을 직접 쓰지 않는다). ADR 폴더의 `README.md`·`_TEMPLATE.md`도 `maintainer` 행의 `docs/interim/**/README.md`·`docs/interim/**/_TEMPLATE.md`가 소유한다. (초안은 ADR 본문을 `leader` 쓰기 경로에 뒀으나, plan과 같은 자가수정·조율 사유로 작성 권한을 Maintainer로 옮겼다.)

## 예시
**준수 (✓)**
- `WIP/axdt/roles/prompts/reviewer.md`가 `rule_refs`에 `rule-role-responsibilities`를 명시하고, `roles/spec.py`의 `reviewer.writable_paths`가 이 표의 `(없음)`과 등가 → 계약 검사 통과.
- `leader`가 `src/`와 자기 task의 report만 쓰고 progress·plan·sot는 손대지 않음 → `rule-protected-paths` 허브 게이트 통과.

**위반 (✗)**
- `roles/spec.py`가 `developer.writable_paths`에 `docs/**`를 넣음 → 이 표와 불일치, 계약 검사 실패.
- 강제 등급 각주 ⁴의 Reviewer 칸을 측정 없이 `기계`로 확정 기재 → 스펙 §10 위반(측정되지 않은 값을 참으로 적음).
- 역할 축 쓰기 권한을 `rule-protected-paths`에 새로 정의 → 단일 명세 이원화. 역할 축 오라클은 이 문서 하나여야 한다.
