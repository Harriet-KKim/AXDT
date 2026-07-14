# 핸드오프 — §8.3b 라이브 측정 (항목 11~13, 컨테이너 이미지 전제)

> 작성: phase2 세션(역할·통신 프로토콜 설계) · 대상: **Phase 3 세션**(phase3-isolation-infra)
> 근거: 스펙 §4.1(신뢰 상태 이미지 굽기)·§9(교차-Phase 계약: 컨테이너 이미지 = Phase 3 substrate) · `WIP/axdt/agent_runner/tests/live_probe_protocol.md` §4(항목 11~13)·`live_probe.py`(§8.3b 스텁)

## 0. 무엇을 넘기나

Phase 2는 §8.3a 라이브 측정(맨몸 CLI, 항목 1~10)을 `WIP/axdt/agent_runner/tests/live_probe.py`로 구현하고 다중 모델 리뷰로 수렴시켰다. 그러나 항목 11~13(§8.3b)은 **컨테이너 이미지를 빌드해야만** 잴 수 있고, 이미지 생성은 Phase 3의 substrate이므로 Phase 2 범위 밖이다. `live_probe.py`는 이 세 항목을 SKIP 스텁으로만 낸다(`verdict="SKIP"`, `evidence.note="requires built container image (§8.3b) — deferred"`, `live_probe.py:2115-2132`).

넘기는 것은 draft 코드가 아니라 **측정 명세 + 측정이 확정할 Phase 3 결정 목록**이다. Phase 3가 이미지 빌드 파이프라인을 만들 때 이 세 항목을 측정하고, 그 결과로 §4.1의 이미지 굽기 설계를 확정한다.

## 1. 왜 Phase 3인가

- **스펙 §9 교차-Phase 계약**: "Phase 3(`leader.up` substrate·cron·**컨테이너 이미지**)". 이미지는 Phase 3이 제공하는 토대다.
- **스펙 §4.1**: 항목 12(`/tmp` tmpfs) 결과가 "덮임"이면 `config.CONTAINER_HOME`을 옮겨야 하며, 이는 "Phase 3 코드를 건드린다. §8.3 측정 항목이고, 결과에 따라 Phase 3 수정이 딸려온다."
- **주의(귀속 구분)**: 측정 스크립트·프로토콜(`live_probe.py`, `live_probe_protocol.md`) 자체는 Phase 2 산출물이다. Phase 3로 귀속되는 것은 **이미지 생성**이고, §8.3b 측정은 그 이미지 위에서 수행된다. (프로토콜 문서가 한때 "Phase 2가 이미지를 빌드한 뒤"로 적었던 것은 오기로 phase2에서 정정했다 — `live_probe_protocol.md:182`.)

## 2. 무엇을 재나 — 세 항목

측정 절차 초안은 `live_probe_protocol.md:184-185`에 있다.

| # | 항목 | 무엇을 확인 | 측정 방법 | 오라클 성격 |
|---|---|---|---|---|
| 11 | 무프롬프트 IDLE 도달 | 이미지에 구운 신뢰·온보딩 설정만으로, 별도 프롬프트 없이 컨테이너가 IDLE에 도달하는가. **온보딩 완료 표시 키 이름**(신뢰 다이얼로그와 별개의 최초 실행 안내, §4.1)을 여기서 확정. | 실제 `docker run --user <uid>:<gid>`로 컨테이너를 띄워 화면 관측. | IDLE 도달·키 이름은 **화면 관측 → NEEDS_HUMAN**. |
| 12 | `/tmp` tmpfs 덮임 | 컨테이너 실행 시 `/tmp`가 tmpfs로 덮여 이미지 레이어에 구운 내용이 사라지는가. | 컨테이너 안에서 `mount \| grep /tmp`, 또는 파일 생성 후 재실행 시 잔존 여부. | mount 결과·파일 잔존은 **OS 사실 → 자동 판정 가능**. |
| 13 | 임의 uid로 HOME 접근 | 아무 uid로 띄워도 이미지에 구운 HOME(`/tmp/axdt-home` 또는 대체 경로)을 읽고 쓸 수 있는가. | `docker run --user <임의 uid>`로 띄워 HOME 읽기/쓰기 시도. | 접근 성공/실패·exit code는 **OS 사실 → 자동 판정 가능**. |

## 3. 측정 결과가 확정·변경하는 것 (§4.1)

- **11 결과** → 온보딩 완료 키 이름 → 이미지 빌드 스크립트가 그 키를 굽는다. Claude Code는 `~/.claude.json`의 `hasTrustDialogAccepted`, Codex는 `config.toml`의 `[projects.'/work'] trust_level="trusted"`와 함께.
- **12 결과가 "덮임"** → `config.CONTAINER_HOME`을 `/tmp` 밖(`/axdt-home` 등)으로 옮긴다. **Phase 3 코드 변경**이며, `container.run_args`의 `-e HOME=...`도 따라온다.
- **13 결과** → HOME 경로 권한을 임의 uid가 쓸 수 있게(`chmod 0777` 또는 sticky bit), 굽는 파일은 world-readable로 만든다.
- **공통 제약(§4.1)**: 자격증명은 굽지 않는다 — `ANTHROPIC_API_KEY`는 `docker run -e`로 주입한다(이미지에 넣으면 이미지가 곧 자격증명이 된다).

## 4. 측정 도구·방법론 계승

§8.3a에서 확립한 **§0 CAPTURE-not-JUDGE 원칙을 이어받는다.**

- 측정 도구는 SUT(CLI·컨테이너 동작)에 자동 PASS/FAIL을 찍지 않는다. 자동 판정은 도구 자신의 버그(`FAIL`)와 측정 전제 실패(`SETUP_FAILED`)뿐.
- 11~13은 §8.3a보다 자동 판정 여지가 크다 — 12(mount 결과)·13(파일 쓰기 exit code)은 **OS 사실**이라 자동 판정할 수 있다. 반면 11(IDLE 도달·온보딩 키 이름)은 화면 관측이므로 `NEEDS_HUMAN`으로 사람에게 넘긴다.
- 구현은 `live_probe.py`의 SKIP 스텁(`:2115-2132`)을 실측 구현으로 대체하거나, 별도 스크립트/수동 절차서를 만든다. 어느 쪽이든 §8.3a의 secret redact·무예외 정리 같은 안전 장치가 필요한지 재검토한다(항목 13이 임의 uid·권한을 다루므로).

## 5. Phase 3 세션이 할 것

- **귀속 수용**: §8.3b 11~13 측정과 그 결과에 딸린 §4.1 확정을 Phase 3가 소유하는지 확인.
- **파이프라인 통합**: 이미지 빌드 파이프라인(신뢰 상태 굽기 포함)에 11~13 측정을 게이트로 넣어, 측정을 통과하지 못한 이미지를 신뢰하지 않는다.
- **§4.1 확정**: `config.CONTAINER_HOME` 위치·권한, 온보딩 완료 키, trust 굽기 방식.
- **매트릭스 반영**: 확정 결과를 `WIP/axdt/agent_runner/PLATFORM_MATRIX.md`에 옮긴다 — `live_probe_protocol.md` §5 절차(확정 시점 CLI 버전 병기, 버전 달라지면 재측정)와 정합시킨다.

## 참조

- `WIP/axdt/agent_runner/tests/live_probe_protocol.md` §4(항목 11~13 절차)·§5(매트릭스 갱신)
- `WIP/axdt/agent_runner/tests/live_probe.py:15-17`(§8.3b 범위 명시)·`:2115-2132`(SKIP 스텁)
- 스펙 `WIP/specs/2026-07-09-phase2-roles-and-protocol-design.md` §4.1(:663-678, 신뢰 상태 이미지 굽기)·§9(:9, 교차-Phase 계약)
- `config.CONTAINER_HOME`·`config.CONTAINER_WORKDIR`·`container.run_args`(Phase 3 인프라 코드)

---

## 부록 — Phase 3 착수 프롬프트 (제안)

> 새 Phase 3 세션(`phase3-isolation-infra` 브랜치)을 열 때 줄 프롬프트 초안. 프로젝트 상황에 맞게 다듬어 쓴다.

```
너는 AXDT의 Phase 3(격리 & 인프라) 세션이다. 브랜치 `phase3-isolation-infra`에서
작업한다 — main 직접 커밋·push 금지, 한 브랜치=한 phase.

[배경]
Phase 2가 §8.3a 라이브 측정(맨몸 CLI, 항목 1~10)을
`WIP/axdt/agent_runner/tests/live_probe.py`로 구현·수렴시켰다. 항목 11~13(§8.3b)은
컨테이너 이미지가 있어야 재는데, 이미지 생성이 Phase 3 몫이라 Phase 2에서는 SKIP
스텁으로만 남겼다. 인계 문서 `WIP/handoff-83b-container-measurement.md`를 먼저
정독하라. 스펙 §4.1(신뢰 상태 이미지 굽기)·§9(교차-Phase 계약), 그리고
`live_probe_protocol.md` §4·§5도 함께 읽는다.

[과제]
1. 컨테이너 이미지 빌드 파이프라인(§4.1 신뢰 상태 굽기 포함)을 설계·구현할 때,
   §8.3b 항목 11~13 라이브 측정을 그 파이프라인의 게이트로 통합한다.
2. 측정은 live_probe.py의 §0 CAPTURE-not-JUDGE 방법론을 계승한다 — 컨테이너·CLI
   동작에 자동 PASS/FAIL을 찍지 말고, OS 사실(mount 결과·파일 접근 exit code)만
   자동 판정하고, 화면 관측(IDLE 도달·온보딩 키 이름)은 NEEDS_HUMAN으로 사람에게 넘긴다.
3. 측정 결과로 §4.1을 확정한다: (a) /tmp tmpfs 여부 → config.CONTAINER_HOME 위치,
   (b) 임의 uid HOME 접근 → 권한(chmod 0777/sticky·world-readable),
   (c) 온보딩 완료 키 이름 → 이미지에 굽기. 자격증명은 굽지 말고 -e로 주입한다.
4. 확정 결과를 WIP/axdt/agent_runner/PLATFORM_MATRIX.md에 반영한다
   (live_probe_protocol.md §5 절차: 확정 CLI 버전 병기, 버전 달라지면 재측정).

[제약]
- 공유 계약(runner/adapters/state/backend, config.CONTAINER_HOME 등)을 바꿀 땐
  단일 진실원에서 고치고 소비자에 통보한다(손사본 금지).
- 구현 착수 전 측정·이미지 설계를 다중 모델(Codex + Opus 등)로 검토한다.
- 실측 없이 값을 확정하지 않는다 — Windows엔 tmux/docker가 없으니 실제 Linux
  호스트에서 측정한다.

[먼저 할 일]
handoff 문서와 위 스펙 절을 읽고, §8.3b 측정 설계 초안을 제시하라 — 무엇을 자동
판정하고 무엇을 NEEDS_HUMAN으로 둘지, 이미지 빌드 파이프라인의 어느 지점에 게이트를
걸지, live_probe.py의 SKIP 스텁을 실측 구현으로 대체할지 별도 절차서로 갈지.
```
