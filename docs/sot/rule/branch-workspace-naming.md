---
id: rule-branch-workspace-naming
title: branch·workspace·container는 wave.task 단일 식별자로 동일하게 명명한다
status: active
scope: local
related: [rule-leader-coordination-via-maintainer]
---

# branch·workspace·container는 wave.task 단일 식별자로 동일하게 명명한다

## 규칙문
> 한 작업 단위(task 하나 = Leader 하나 = workspace 하나 = container 하나)는 **단일 식별자 `w<n>.t<n>-<slug>`** 로 명명한다. 이 식별자가 **branch · workspace 디렉터리 · 컨테이너 이름을 일관되게** 결정한다 — branch와 workspace 디렉터리 이름은 식별자와 **동일**, 컨테이너만 `axdt-` 네임스페이스 접두를 붙인다. 슬래시(`/`)는 쓰지 않는다.

식별자 규격:

| 구성 | 의미 |
|---|---|
| `w<n>` | wave 번호 (w1, w2, …) |
| `t<n>` | task 번호 (t1, t2, …) |
| `<slug>` | 소문자 kebab-case 작업명 |

| 산출물 | 이름 (예) |
|---|---|
| branch | `w3.t12-auth-login` (= 식별자) |
| workspace 디렉터리 | `w3.t12-auth-login` (= 식별자, 경로는 `workspaces/<식별자>`) |
| container | `axdt-w3.t12-auth-login` (`axdt-` + 식별자) |

## 근거
- workspace는 branch와 1:1이고, task:Leader:workspace:container도 1:1이다(D3). 이름이 여러 개일 이유가 없다 — **한 식별자가 전부를 가리키면** 추적·정리·검증이 단순해진다.
- 식별자에 wave를 넣으면 어떤 task가 **어느 마일스톤에 속하는지 이름만으로** 드러난다.
- 슬래시 배제 이유: 컨테이너·디렉터리 이름은 `/`를 허용하지 않는다. 셋을 한 식별자로 묶으려면 branch도 슬래시 없이 간다(`w`/`t` 접두가 wave/task 작업 브랜치임을 표시).

## 적용범위
- **대상**: Leader가 작업하는 모든 task의 branch·workspace·container. `w<n>`/`t<n>`/`<slug>` 값은 plan(wave/task) 문서의 id·제목을 따른다.
- **예외**: `main` 등 long-lived 통합 브랜치는 본 규칙 대상이 아니다. SoT 변경용 `sot/<slug>` 브랜치도 본 규칙이 아니라 `rule-sot-change-user-gate`가 규정한다.

## 예시
**준수 (✓)**
- wave 3의 task 12(로그인 인증) → branch `w3.t12-auth-login`, workspace `workspaces/w3.t12-auth-login`, container `axdt-w3.t12-auth-login` (셋 동일).

**위반 (✗)**
- branch는 `task/auth`인데 workspace는 `workspaces/t12`로 따로 명명(이름 불일치) / `w3/t12`처럼 슬래시 사용(컨테이너 이름 불가).
