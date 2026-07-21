---
id: ADR-0017
title: Codex 역할은 -p 프로파일 바인딩으로 전달하고 어댑터가 역할·권한을 계약으로 보증한다
status: accepted
date: 2026-07-21
decision: D4
related: [ADR-0005, ADR-0016]
---

# ADR-0017: Codex 역할은 -p 프로파일 바인딩으로 전달하고 어댑터가 역할·권한을 계약으로 보증한다

## 상태
Accepted (2026-07-21) · 관련 결정 D4

## 맥락
Claude Code는 역할 시스템 프롬프트를 `--append-system-prompt` argv로 싣지만 Codex CLI에는 그런 플래그가 없다. Codex 세션에 역할을 어떻게 전달할지가 문제였다.

처음 택한 런타임 주입(세션 첫 프롬프트로 시스템 프롬프트를 밀어넣기)에 두 결함이 있었다.
- `leader up`(세션 기동)과 `send`/`assign`(attach)이 별개 프로세스라, 주입이 기동 프로세스에 묶이면 attach 경로에는 역할이 실리지 않는다.
- 주입 내용과 `AGENTS.md` 자동 로드는 입력 계층상 `user`에 들어간다 — workspace의 `AGENTS.md`가 의미적으로 override할 수 있고, 역할 정체성 계층(`developer`)이 아니다(Codex 0.144.3 `debug prompt-input` 실측).

여기에 코드 리뷰가 한 축을 더했다. 역할 물질화를 Phase 3에 통째로 위임하면(어댑터의 `prepare_subagents`가 `NotImplementedError`) 어댑터 계약이 비대칭이 된다. Claude는 역할·권한이 argv·`--agents` JSON에 실려 어댑터가 보증하는데, Codex 쪽은 어댑터가 아무것도 보증하지 않는다.

## 결정
- `build_session_command`이 `-p <role.name>`으로 역할↔프로파일을 결정적으로 바인딩한다.
- 어댑터가 `role_artifacts(role, root)`로 역할 프롬프트·권한(sandbox 등급)을 담은 프로파일 명세를 계산한다 — 역할·권한 내용의 단일 진실원이 어댑터다. Claude는 argv·`--agents`로 자립하므로 `role_artifacts`가 빈 목록이다("보증 없음"이 아니라 "검증할 외부 아티팩트 없음").
- `verify_role_provisioned`가 기동 전 fail-closed 게이트로 아티팩트 존재·내용을 검증하고, `AgentRunner.start_session`이 `backend.start` 전에 이를 호출한다. `-p`만으로는 부재 프로파일에도 Codex가 기본값으로 진행하므로(0.144.3 실측) 어댑터 게이트로 보강한다.
- Phase 3는 이 명세를 디스크에 물질화만 한다(내용 생성이 아니라 배치·쓰기·권한 적용).

## 결과
**좋은 점**
- 역할·권한이 계약으로 보증된다. Claude/Codex 비대칭이 플랫폼 차이(실행 인자 주입 vs 설정 파일 로드)를 정직하게 반영한 것으로 정리된다.
- `up`↔`attach` 프로세스 분리가 낳던 부트스트랩 타이밍 문제가 사라진다 — 역할이 프로세스가 아니라 파일에 있다.
- fail-closed 게이트가 실제 기동 경로(`start_session`)에 배선된다 — `verify`가 받은 root에서 프로파일이 부재·불일치면 기동을 거부한다. 다만 이 게이트가 "실효"가 되려면 아래 대가의 성립 조건 두 가지가 필요하다.

**대가 / 주의**
- 정확한 프로파일 파일 스키마(`developer_instructions` 키 여부·최상위/중첩), 그 키가 실제 `developer` 계층으로 로드되는지, project config가 override하는지, Maintainer 호스트 물질화, `.rules` 형식은 슬라이스 B(실 CLI 측정)·Phase 3에서 확정한다.
- `start_session` 게이트는 SESSION 역할만 검증한다. 선택된 SUBAGENT 역할의 프로비저닝 검증 호출자는 Phase 3 `leader.up`이 소유한다.
- 게이트는 어댑터의 `artifact_root`(Codex는 env `CODEX_HOME`, 없으면 `~/.codex`)가 가리키는 프로파일 위치를 검사한다.
- **게이트·보증의 성립 조건 두 가지(Phase 5의 `FakeBackend`·단위테스트로는 확정 불가).** ⓐ 게이트는 `verify`가 받은 root의 파일을 검사하는 **메커니즘**이다 — 그 root가 세션이 실제 읽는 파일시스템 namespace와 같은지(컨테이너 세션에선 호스트 파일 ≠ 컨테이너 파일)는 Phase 3가 `CODEX_HOME` 정렬 또는 read-only bind mount로 보장한다(`FakeBackend`는 동일 호스트라 성립). ⓑ 프로파일은 project config(`.codex/config.toml`)보다 우선순위가 낮아 `developer_instructions`가 override될 수 있다(공식 문서) — 파일 바이트 일치는 프로파일 **내용**을 보증하나, **실효 역할 프롬프트**는 override 미발생 전제에서만 성립한다. 두 조건의 확정(버전 고정 라이브 음성 수용 테스트)은 슬라이스 B·Phase 3다(handoff §6 미결 1·4).

## 검토한 대안
### 대안 A — 런타임 주입 (세션 첫 프롬프트로 시스템 프롬프트 전달)
기동 시 시스템 프롬프트를 타이핑해 넣음. · **기각 사유**: `up`↔`attach` 프로세스 분리로 attach 경로에 역할이 안 실리고, 주입 내용이 `user` 계층이라 override 가능하며 역할 계층(`developer`)이 아니다(실측).

### 대안 B — `$CODEX_HOME`/전역 `AGENTS.md` 자동 로드에 역할을 담기
Codex가 자동 로드하는 `AGENTS.md`에 역할을 씀. · **기각 사유**: 그 내용이 `user` 계층에 들어가 workspace `AGENTS.md`가 override할 수 있고, 역할 정체성 계층이 아니다(실측).

### 대안 C — `-p` 바인딩만 하고 보증은 Phase 3에 위임
프로파일 선택만 어댑터가 하고 존재·내용 보증은 컨테이너 계층에 맡김. · **기각 사유**: 어댑터 계약이 비어 무엇을 보증해야 하는지 계약에 없고, Claude/Codex가 비대칭으로 남는다(코드 리뷰 지적).
