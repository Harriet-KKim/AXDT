# docs/interim/plan/ — 작업 분해 (Plan)

> 일을 **wave(마일스톤) → task(Leader 작업 단위)** 로 분해한 문서. **상태 필드를 두지 않는다.**

## 목적
무엇을 어떤 순서·의존으로 할지 구조를 정의한다. plan은 "할 일의 형태"만 담고, **진척 상태는 progress.md(Maintainer)와 report(Leader)** 가 담는다 — plan에 상태를 넣으면 권위가 갈라진다.

## 필수 내용
- **`wave/`** — 마일스톤(= task 묶음). wave 간 의존·종료기준.
- **`task/`** — Leader 1명이 맡는 작업 단위. workspace/branch와 1:1.

## 네이밍
- wave/task id는 `branch-workspace-naming` 규칙의 식별자 체계를 따른다: wave `w<n>`, task `w<n>.t<n>-<slug>`.

## 참고
- 식별자 규격: `../../sot/rule/branch-workspace-naming.md`
- 상태는 여기가 아니라: `../progress.md`, `../report/`
