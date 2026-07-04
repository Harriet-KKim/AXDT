---
id: ADR-0005
title: agent runner는 어댑터+백엔드 합성과 주입된 실행 백엔드로 구성한다
status: accepted
date: 2026-06-26
decision: D4
related: [ADR-0003]
---

# ADR-0005: agent runner는 어댑터+백엔드 합성과 주입된 실행 백엔드로 구성한다

## 상태
Accepted (2026-06-26) · 관련 결정 D4

## 맥락
D4는 공통 agent runner 인터페이스 + Claude Code·Codex 어댑터 양쪽 구현을 요구한다. 두 플랫폼의 세션 라이프사이클(기동→prompt 주입→출력 읽기→정지)은 동일하고, 차이는 (1) 어떤 CLI를 어떻게 띄우고 prompt/출력을 어떻게 포맷·파싱하는가, (2) 어디서 실행되는가(로컬/tmux/Docker)뿐이다. 또 Phase 5 시점엔 tmux/Docker substrate(Phase 3)가 없어 substrate 없이도 계약을 검증할 수 있어야 한다.

## 결정
- `AgentRunner`는 `PlatformAdapter`(플랫폼 지식)와 `SessionBackend`(실행 substrate)를 **합성**한다. 플랫폼별 runner 상속은 하지 않는다.
- `SessionBackend`는 **주입**된다. Phase 3가 `TmuxDockerBackend`를 구현하고, Phase 5는 `FakeBackend`로 계약을 단위 테스트한다.
- `read_output`/`poll_state`는 모니터링·liveness 전용이며 작업 결과의 권위 채널은 report 파일이다(ADR-0003).

## 결과
**좋은 점**
- 라이프사이클 로직이 한 곳에 있고 변하는 축(어댑터·백엔드)만 교체된다 — 중복 제거.
- substrate-독립적이라 tmux/Docker 없이도 결정적으로 테스트된다.
- 결과 권위가 report에 있어 stdout 파싱 결합을 피한다(ADR-0003·0004와 정합).

**대가 / 주의**
- 객체 3개(runner/adapter/backend)로 간접성이 늘어난다(수용 범위).
- CLI 플래그·출력 마커·tmux 제출 뉘앙스는 Phase 3 라이브 검증까지 provisional.

## 검토한 대안
### 대안 A — 플랫폼별 runner 상속 (ClaudeCodeRunner/CodexRunner)
각 플랫폼이 라이프사이클을 구현. · **기각 사유**: 동일 라이프사이클을 플랫폼 수만큼 중복시킨다.

### 대안 B — runner가 tmux/Docker를 직접 소유
substrate를 runner 내부에 박음. · **기각 사유**: Phase 3와 책임이 섞이고, mock하려면 monkeypatch가 필요해 계약 경계가 흐려진다.

### 대안 C — read_output을 권위 결과 채널로 사용
stdout 파싱으로 결과 수용. · **기각 사유**: ADR-0003의 report 권위 흐름과 충돌하고 출력 포맷에 강결합된다.
