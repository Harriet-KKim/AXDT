# §8.3b 후속 — seed+copy 운영 설계와 §4.1 반영 (검토용 초안 v11)

> 지위: **검토용 작업 초안**(job tmp, repo의 ADR/SoT 아님). 실측 확정 vs 미측정을 구분 표기.
> 대상 스펙: `WIP/specs/2026-07-09-phase2-roles-and-protocol-design.md` §4.1(:663-678)·§9(:1281) — **origin/phase2 브랜치에만 존재**(이 워크트리 미병합). 인용은 phase2 기준.
> 대상 코드: `WIP/axdt/infra/config.py:38`, `container.py:73-86`(run_args)·`:82-83`(env→argv), `backend.py`(SessionBackend `is_alive`/`exit_code`/`status`/`send_text`/`read_new_output`·`start_capture`·`:98-105`), `tmux.py:28-37`, `leader.py:14,27`(command/PLACEHOLDER)·`:24`(seed_from), `docker/leader.Dockerfile`.
>
> **v2~v5(1~4차 리뷰, 요약)**: 자격증명 env→ro 파일 마운트→복사(blocker), ADR Claude 한정 잠정(blocker), 측정 게이트 재정착·seed provenance, ENTRYPOINT 이행·HOME 생성·run_args 공유계약, 마운트 파일 내용을 §3.1 분기에 결속, 값 미노출 vs 경로 노출, 모드 인지 fail-closed, env 비밀 금지 계약, 무결성<digest 정직, R13·R11·CAPTURE-not-JUDGE(§0)·unknown 명령 fail-closed.
> **v6(대안 자문 — Codex-Sol·Fable)**: R7/R9/R3/R10 실측 편입, 무중단 장기세션 요구화, 단일 파일 :ro 마운트 회전 불가(inode), 중앙 lease 관리자, R12 tmpfs, R13 전용 GID, R14·R14c·R14d.
> **v7(v6 재검토)**: "무중단"="세션 지속(짧은 재시작 허용)"(사용자) → 재시작 롤오버=주·hot-handoff=최적화, R8=참 분기, ADR IDLE 한정, 감독자(claude≠PID1) 기본·R14c/R14c′, R2 골격 blocker, R15 등록.
> **v8(v7 재검토)**: 재시작 바닥의 fresh AT 전달을 요구 인프라 재분류(push→R14c, in-process 재독 R14는 최적화만), backend.py 생존 계약 영향, R8=참 다중세션 바닥 한정, R15 요구 게이트 승격, 감독자 계약 상세, R12/R12′ 등록, R2 폴백 예외.
> **v9 변경(v8 재검토 — Codex 0B·Fable 1B 수렴 수정)**: ㉑ **주 경로 확정 — 감독자(A) 기본, 재생성(B)은 게이트된 폴백**(§4·§5의 공유계약 결과를 A-우선으로, B 결과는 폴백 비용으로 병기 — "발의 시 동등 택1" 철회, 문서 정합). ㉒ **재시작 제어 채널 핸드셰이크 명시**(호스트 lease 관리자↔감독자: stop→push ack→신선도 검증→재기동/거부, fail-closed; push 전달을 R14c의 형제 게이트로 분리). ㉓ **backend.py 입출력 경로 편입**(`send_text` 재시작 창 버퍼/거부·`read_new_output` 재시작 흔적 경계 — 생존 3종과 함께). ㉔ **R8=참 공급단 분기**(갱신 구동기가 사용자 호스트 로그인이면 같은 세대 → 사용자 사용이 컨테이너 AT 무효화 → 전용 계정 분리/격리 로그인; "호스트 상용 흡수" 이점은 R8=거짓 전제) + R15 폴백 사람 개입 주기 병기.
> **v10 변경(v9 재검토 — Codex 0/0·Fable 0B/3non 수렴, 발의 전 다듬기)**: ㉕ push 명령을 **절대경로**(`/tmp/axdt-home/.claude/.credentials.json` = `config.CONTAINER_HOME`)+`-e HOME=`으로 고정해 임의 uid `$HOME` 빈-전개(passwd 부재) 회피(§3.2). ㉖ **`--continue` 복원(R14c-복원)을 감독자·재생성 두 바닥의 공통 급소**로 명시, 요구 충족을 그 통과 전제로 한정, §5 최우선 측정. ㉗ **R8을 함대 토폴로지 요구-임계 측정으로 승격**(정상 토폴로지=한 계정 공유 N 컨테이너에서 R8=참이면 형제 롤오버가 동족 살해 → 무거운 구현 전 측정·발의 경고).
> **v11 변경(측정 라운드 반영 — 요구 blocker 실측 종료·R1 유예 결정)**: ㉘ **요구 blocker 6게이트 실측 통과를 §1에 편입**(R2 accessToken-only·R4 동시성·R8=참[단일 활성 AT]·R14c-복원·R14c-전달[push 소생]·R15[갱신 유발] — 상세 원본 `WIP/handoff-phase3-seedcopy-measurement.md`), §2 표에서 내리고 요구 blocker "모두 닫힘". ㉙ **R1(회전·재사용 처벌) 측정 유예 + 최악 가정 확정** — 측정에 전용 유료 계정 필요·실측 자체가 계정 잠금 위험이라 유예하고, 최악 가정에서 설계가 이미 방어(컨테이너 refresh 차단·정품 claude 경로만·원자적 저장=계정-잠금 회피 불변식). 요구 blocker에서 결정 항목으로 이동(§3.1·§4·§5). ㉚ **R8=참 확정 반영** — "분기/IF" 헤지를 확정 문구로.

---

## 1. 실측으로 확정된 것 — 측정된 구성 명시 (AX-DEV, docker 29.4.3, claude 2.1.209)

측정값은 **관측값이다**(계약값·버전 불변값이 아님). 설계 상수로 동결하지 않는다.

- **항목 11(무프롬프트 IDLE)**: **통짜 seed**(설정+자격증명 함께 복사)로 임의 uid에서 테마·로그인·신뢰 프롬프트 없이 IDLE 도달. → 분리 구성은 이후 **R9로 재측정·통과**.
- **항목 12(/tmp)**: 컨테이너 `/tmp` = overlayfs(tmpfs로 안 덮임). → 런타임 복사 방식에선 HOME 위치를 더는 게이트하지 않음(§3.4).
- **항목 13(임의 uid)**: **사전 생성 0777 HOME**에 임의 uid(4242)가 읽기·쓰기 성공. → entrypoint가 uid로 HOME 생성하므로 0777 전제가 바뀜(R10 재측정·확인).
- **파일 분리(관측)**: `~/.claude.json`(온보딩 `hasCompletedOnboarding`·신뢰 `projects["/work"].hasTrustDialogAccepted`·`oauthAccount` 메타 — 토큰 없음, 계정 식별자(이메일·조직) 가능성) vs `~/.claude/.credentials.json`(600, `claudeAiOauth.{accessToken,refreshToken,expiresAt,refreshTokenExpiresAt,...}`).
- **토큰 수명(파일 필드 관측)**: accessToken ~8h, refreshToken ~29d. **관측값**.

**추가 실측(대안 자문 라운드 직전, AX-DEV — probe 이미지 `axdt/leader:probe`=`node:22-slim`+`npm i -g @anthropic-ai/claude-code`, 실토큰·값 미출력, mtime/size/화면만).** probe 설치 claude 버전은 §1 상단 2.1.209와 다를 수 있음(관측값, 버전 병기 대상).

- **R9 통과(분리 구성 IDLE)**: 설정 seed(자격증명 제외) + 자격증명 파일 별도 `:ro` 마운트 → entrypoint가 설정 복사 + `install -m600` 자격증명 → 프롬프트 없이 IDLE 도달·간단 질의 응답. → **파일 마운트 부팅 한정**(push 부팅은 미측정).
- **R3 통과(600 수용)**: entrypoint가 uid로 쓴 mode 600 credentials를 claude가 native와 동일 수용.
- **R10 확인(uid HOME 생성)**: entrypoint가 컨테이너 uid로 `mkdir -p $HOME` 성공.
- **R13 필요성 실증**: 임의 uid(4242)로 host-owned 600 자격증명 마운트 시 `Permission denied` — 임의 uid 미독·비-root 호스트 임의 uid `chown` 불가 → 전용 GID·root chown·world-readable 폴백 중 택일(§3.2/R13).
- **R7a 측정(모의 만료 — 자가 복구 실패)**: accessToken 훼손 + 로컬 `expiresAt` 과거화, 유효 refreshToken 동봉 기동 → `Login expired · Please run /login`, credentials **재작성 안 함**(mtime 불변), 헤드리스 `/login` 실패. 독립 2회 일치. → **자연 만료(R7b) 미측정**(훼손+과거화라 "미시도"와 "시도·실패" 구분 불가). 결론(정직): 컨테이너 자가 갱신 **미보장**(≠불가), **의존 금지**.
- **파일 사실(projects 키)**: `.claude.json`의 `projects`는 **호스트 절대경로로 키**됨(`/work` 아님) → seed 생성 시 `/work`로 재작성해야 신뢰 선수용(§3.4).

**요구 blocker 측정 라운드 통과(AX-DEV, 컨테이너 claude 2.1.209 관측 — 상세 원본 `WIP/handoff-phase3-seedcopy-measurement.md`).** CAPTURE-not-JUDGE: 값(토큰·PII) 미기록, 증거(exit code·서버 응답·mtime)만.

- **R2 통과(accessToken-only 동작)**: refreshToken 제거 seed로 claude 인증·응답(pong, rc=0). → 컨테이너 지급은 accessToken만으로 충분 — §3.1 "accessToken-only" 전제 성립.
- **R4 통과(동일 AT 동시 사용, 충돌 없음)**: 같은 accessToken을 상자 2개에 동시 호출 → 각 rc=0. → 서버가 동시성 자체를 막거나 이상탐지로 끊지 않음(R8과 별개 축).
- **R8 참(단일 활성 AT — 새 발급이 구 것 무효화)**: 새 토큰 발급 직후 구 토큰 상자 → `401 OAuth access token has been revoked`(rc=1). → §3.1 "R8=참" 확정: 공유 계정 형제 롤오버=동족 살해, 갱신 구동기 세대 결속, **선제 갱신 금지·반응형**.
- **R14c-복원 통과(`--continue` 대화 복원)**: 새 claude 프로세스가 이전 대화 암호어 회상, transcript(`.jsonl`) 존재. → 감독자(A)·재생성(B) 두 바닥의 공통 급소가 열림.
- **R14c-전달 통과(push 소생 + `--resume` 복원)**: 컨테이너 사본 손상으로 서버 401(Invalid bearer token) 사망 재현 → 호스트 유효 자격증명을 `docker exec` stdin(절대경로·umask 077·원자적 mv·내용 검증)으로 push → `--resume`로 인증 소생 + 대화 복원, **호스트 무변경**. → §3.2/§3.3 전달·복원 게이트가 열림.
- **R15 통과(R8로 실증)**: R8 갱신 단계에서 호스트 저비용 호출이 새 토큰 발급(mtime 변경·이후 새 토큰으로 동작). → 바닥의 fresh AT 공급 전제 성립.

## 2. 미측정 — 값 확정 금지, 측정 게이트

**CAPTURE-not-JUDGE(§0 계승).** probe는 증거(화면·`mount`·exit code·파일 mode)를 **capture**, verdict는 NEEDS_HUMAN/SKIP/SETUP_FAILED. R1-R15 어느 것도 probe에 판정 로직을 넣지 않는다.

**측정 안전장치(공통)**: R1-R4·R7-R9·R12-R15는 실토큰을 다룸 → secret redact + 무예외 정리. PII redact는 `oauthAccount`를 만지는 모든 probe·artifact에 적용.

| ID | 미측정 질문 | 좌우 결정 | 상태·우선순위 |
|---|---|---|---|
| **R1** | refresh 시 refreshToken **회전**? 재사용 탐지 → 패밀리 **revoke**? | 3.1 회전 | **측정 유예 — 최악 가정(회전+재사용 처벌) 확정**(§3.1 방어; 요구 blocker 아님) |
| R14c′ | **재생성 복구(B 폴백 형상)** — 컨테이너 재생성 + 영속 트랜스크립트(또는 오케스트레이터 복원) + `--continue` | 3.1/3.3 폴백 | 폴백 게이트 |
| R14 | **claude가 실행 중 재독**(요청/401 시). *하위*: 유효 토큰+과거화 expiresAt로 동작? **무재시작 hot-handoff에만 필요** | 3.1/3.2 최적화 | 최적화 |
| R14d | **`apiKeyHelper` 훅**이 구독 OAuth AT로 호출·동작? *판정*: OAuth cred 유/무, 재호출 시 진행 세션 자격 전환, 반환값 AT/API key | 3.1/3.2 최적화 | 최적화 |
| R5 | **Codex**(config.toml `trust_level`) 대칭 동작 | 3.4 | arm |
| R6 | 베이스 이미지 `python:3.12-slim` → node·claude 설치(probe=`node:22-slim`) | 3.3/3.4 | 빌드 |
| R7b | **자연 만료** AT(훼손 아님) 자가 복구 거동 — R7a 인과 확정 | 3.1 문구 | 비-blocker |
| R11 | 설정 seed `oauthAccount`(PII) 제거·재작성 수용 / 노출 수용선 | 3.2/seed | PII |
| R12 | **자격증명 잔존** — 정지·실패 컨테이너 HOME에 `.credentials.json` 잔존·회수(docker cp/commit) | 3.2/3.3 | 잔존 |
| R12′ | **tmpfs 옵션 수용** — `--tmpfs $HOME:uid=/gid=/mode=/size=` 수용·양립·swap 유출 | 3.3 | 잔존 완화 |
| R13 | **부팅 자격증명 전달** — 전용 GID(`0640 :gid` + `--group-add`) 읽기 성립 | 3.2 | 권한 |

> **측정 완료(§1 편입)**: R2·R3·R4·R7a·R8(참)·R9(파일마운트 부팅 한정)·R10·R14c(복원+전달)·R15. R13은 필요성 실증(전달 수단 확정은 미측정).
> **요구 blocker: 모두 닫힘**(R2·R14c 전달+복원·R15 통과 — handoff). **R1은 측정 유예·최악 가정 확정**(§3.1 방어, 요구 blocker 아님 — 측정 blocker에서 결정 항목으로 이동). R14/R14d는 무재시작 hot-handoff 최적화. R8=참(§1 확정) → 다중세션 바닥·공급단 세대 분기(§3.1).

## 3. 운영 고려 4 — 권고

### 3.1 토큰 수명·회전 → 자격증명 갱신 전략

**요구사항(사용자 확정).** AXDT는 accessToken 수명(~8h 관측)을 넘는 **세션 지속**을 요구한다 — "중단 0"이 아니라 "세션의 작업·대화가 토큰 경계를 넘어 지속". 토큰 경계에서 claude를 잠깐 재시작하고 `--continue`로 이어가는 것은 허용(진행 중 도구호출 유실·순간 재적재 수용). → **재시작 롤오버(바닥)가 요구를 충족**(단 **R14c-복원 통과 전제** — 아래). hot-handoff(무재시작 교체)는 짧은 재시작마저 없애는 **최적화**. 비상수단(헤더 주입 중계기 등)은 **측정 후 결정**(현재 미확정, 자리만). **`--continue` 복원(R14c-복원)은 감독자(A)·재생성(B) 두 바닥의 공통 급소**(단일 미측정 가정) — 실패 시 A·B 어느 쪽도 요구를 못 채우고 설계가 다시 열리므로, 전달·핸드셰이크와 무관하게 §5에서 **최우선**(가장 싸게 무효화 가능)으로 측정한다.

**작동 방식.** 세션이 accessToken 잔여 수명을 넘기면 갱신 필요 — **R7a 실측: 컨테이너 claude는 모의 만료에서 자가 복구 못 함**. 설계는 자가 복구를 **의존 금지**(근거 1순위 R1/R8 최소권한, R7 아님).

**권고 — 중앙 갱신기 = "lease 관리자"(발급기 아님).** refresh를 **중앙(호스트) 국한**, 컨테이너는 refresh 안 함(최소권한: 컨테이너 refresh 차단 → 패밀리 revoke·회전 race 원천 차단). 컨테이너엔 **accessToken만**(R2 전제).
- **갱신기 구현 — 새 OAuth 클라이언트 금지**: 정품 claude 갱신 경로 구동(만료 임박 시 저비용 호출로 파일 갱신 유발 — **R15**), leader는 갱신 파일에서 accessToken·expiresAt만 프로세스 내부로(argv 경유 금지) 읽어 지급.
- **⚠ 공급단(갱신 구동기)의 세대 결속(R8=참 — §1 확정)**: 갱신 구동기가 **사용자 호스트 로그인**이면 컨테이너와 **같은 refreshToken 패밀리**다. R8=참이면 **사용자의 호스트 claude 사용이 새 세대를 낳아 컨테이너 accessToken을 무효화**한다(전역 세대 전환 프로토콜은 사용자의 즉흥적 호스트 사용을 정렬 못 함). → R8=참이면 구동기를 **사용자와 분리된 전용 계정**으로 두거나 컨테이너별 격리 로그인. **"RT 만기(~29d)를 사용자 호스트 상용으로 흡수" 이점은 R8=거짓 전제**.
- **원자적 저장(불변식 — 반드시 성립)**: RT 회전 시 "새 RT 수신 성공·저장 실패"는 계정 잠금급 치명이다. **최악 가정(R1 유예) 하에서 이 원자성은 계정-잠금 회피의 필수 불변식**(옵션 아님) — 수신·저장을 원자적으로(temp write→fsync→atomic rename) 묶어 부분 실패 창을 없앤다.
- **R15는 요구 게이트**: 바닥(재시작)도 fresh AT 공급이 전제 — R15 실패면 바닥도 성립 안 함. **R15 실패 운영 폴백(사람 개입 주기 병기)**: 수동 호스트 재로그인 유도(≈8h마다 사람 — 무인 지속과 배치) / 사용자 호스트 claude 사용 유도(R8=거짓 전제) / 컨테이너별 격리 로그인(무인이나 초기 로그인 N회) 중 택일(발의 시 명시).

**장기세션 메커니즘(요구=세션 지속).**
1. **주 = 재시작 롤오버(바닥, 요구 충족)**: AT 만료 전 작업 단위를 끊고 **fresh AT를 실행 중 컨테이너에 push**(핸드셰이크 §3.3) → 감독자가 claude 재기동(기동 시 재독, §3.2) + `--continue`. 게이트 **R14c**(전달+복원). 폴백 형상은 R14c′.
2. **부 = hot-handoff(최적화, 요구 아님)**: **재시작 없이** fresh AT를 집게 함. 성립 = 회전 전달(디렉터리 마운트+rename) + **claude in-process 재독(R14)** 또는 apiKeyHelper 재호출(R14d). 실패해도 바닥이 요구 충족.

세션 예산은 고정 "8h"가 아니라 **기동 시점 지급 토큰 `expiresAt` 잔여 수명**에서 동적 산정.

**위험(회전·공유) 및 R8=참(§1 확정) 귀결.**
- **최악 가정 확정(R1 측정 유예)**: refresh가 refreshToken을 **회전**시키고 **재사용을 처벌**(패밀리 revoke, RFC 9700)한다고 **가정**한다 — 측정에 전용 유료 계정이 필요하고 실측 자체가 계정 잠금 위험이라 유예하고 최악을 확정값으로 둔다. 이 가정에서 설계는 이미 방어한다: **컨테이너 refresh 차단**(refresh는 중앙 한 곳, 컨테이너엔 accessToken만 → 회전·재사용 트리거 원천 차단), **정품 claude 갱신 경로만**(새 OAuth 클라이언트 금지 → 비정상 재사용 패턴 미유발), **원자적 저장**(위 불변식). RT는 고가치 표적.
- **R8=참(구 AT 무효화):** 새 AT(세대 G2) 발급이 구 G1을 즉시 무효화.
  - **바닥은 단일 컨테이너에만 견고**: 한 컨테이너가 자기 만료 경계에서 새 세대로 재시작하는 것은 성립(짧은 재시작이 유일 중단).
  - **⚠ 다중 컨테이너 공유 AT는 바닥으로 불충분**: 한 컨테이너의 새 세대 발급이 아직 G1을 쓰는 **다른 컨테이너를 끊는다**. R8=참이면 공유 AT 운영은 **전역 세대 전환 프로토콜**(모든 공유-계정 컨테이너를 세대 경계에 정렬) 또는 **컨테이너별 격리 로그인**이 필요. 공급단(위)까지 포함해 R8=참이면 **단일 계정 공유가 근본적으로 취약**. **AXDT 정상 토폴로지(workspace마다 컨테이너 1개를 사용자 한 계정으로)에선 형제 컨테이너 롤오버가 동족 살해**가 된다. **R8=참으로 측정 확정**(§1) → 단일-공유-계정 전제가 실제로 취약함이 확인됨: 함대 토폴로지 운영은 **전역 세대 전환 프로토콜 상세화 또는 격리 로그인 아키텍처 전환**이 필요(발의 경고). R4=충돌 없음(동시성 자체는 안전)이라 남은 대응은 세대 정렬이지 동시성 차단이 아니다. → **함대 토폴로지 대응 설계가 후속 과제**.
  - **최적화(hot-handoff)는 갈림**: 401 재독(R14)은 세션당 401 한 번=순간 중단(세션 지속엔 수용, "진짜 무중단" 아님). 완전 무중단은 apiKeyHelper 선제 폴링(R14d) 특정 요구.
  - **갱신 타이밍 반응형**: R8=참이면 "선제 갱신"이 아직 G1을 쓰는 세션을 죽임 → 수요 기반 반응형(tmux `capture_log` 만료 문구 감시 재사용).
  - **직렬화는 교차-컨테이너 한정**: 여러 컨테이너를 세대 경계에 정렬하는 것 — 단일 장기세션의 자기 경계 넘김엔 무효(재시작 롤오버 또는 R14d).

**R2 실패 분기.** accessToken-only가 R2에서 불가면, 지급에 refreshToken 포함하되 **컨테이너별 격리 로그인**(각 컨테이너가 자기 RT 패밀리, 중앙은 초기 로그인·추적)으로 폴백. **명시적 예외**: 격리 로그인에선 공유-패밀리 근거가 사라지므로 **컨테이너 자기 갱신 허용**(revoke 위험이 격리 패밀리 국한) — "컨테이너 refresh 금지" 일반 규칙의 명시적 예외. 비용은 §4 결과.

**§3.2가 나르는 지급 파일 내용은 이 절이 결정**: accessToken-only(R2 전제) — 공유·회전 위험(R1/R8)으로 refreshToken 미포함. 안전으로 나오면 재고.

### 3.2 자격증명 분리 + 안전한 운반·회전

**작동 방식.** 설정(`.claude.json`)·자격증명(`.credentials.json`)은 파일이 갈린다. 항목 13의 world-readable 요구는 설정에만, 자격증명은 좁은 권한.

**운반 메커니즘(v1 env 폐기).** v1 "env JSON 주입"은 `-e K=v`가 argv→`tmux new-window`로 호스트 `ps`/`/proc/*/cmdline`·`docker inspect Config.Env`에 노출. → 폐기.

**부팅 전달(요구 경로) = 측정된 파일 마운트(R9) + 전용 GID(R13).** 부팅은 R9로 실측된 파일 `:ro` 마운트(push 부팅은 미측정 → R9 재측정 전 보류). 임의 uid 읽기 문제(R13)는 **전용 호스트 GID**: `0640 leader:axdt-cred` + 컨테이너 `--group-add <gid>`(숫자 gid는 컨테이너 `/etc/group`에 없어도 동작). 경계가 "로컬 사용자 전체"→"그룹 구성원 + root/데몬"으로 축소. **나빠지는 점**: 그룹 명단이 새 보안 경계 → 관리 규율. **이 GID 파일은 부팅용 상존이라 R13은 '소멸'이 아니라 '축소'.**

**재시작 전달(요구 인프라) = push(실행 중 컨테이너로 fresh AT 기입).** 바닥은 매 세대 경계에서 **살아 있는 컨테이너에 fresh AT를 넣어야** 한다. 단일 파일 `:ro` 마운트는 inode 고정이라 이걸 못 하므로: `docker exec -i -u <uid> -e HOME=/tmp/axdt-home <c> sh -c 'umask 077; cat > /tmp/axdt-home/.claude/.credentials.json'`로 **push**(값이 argv·`docker inspect`·`docker events`에 안 실림; leader가 아는 **절대경로**(`config.CONTAINER_HOME`)를 직접 써 임의 uid의 `$HOME` 빈-전개[passwd 부재]에 의존하지 않음) → **감독자가 (핸드셰이크 후) claude 재기동**, 새 claude가 **기동 시 재독**(§3.3). 이 경로는 **in-process 재독(R14) 불요**(새 프로세스가 시작 시 읽음). **이 push 전달은 최적화가 아니라 R14c에 포함되는 요구-경로 게이트**(권한·동기화·부분 주입을 비밀 없는 sentinel로 측정). 순서 경쟁은 §3.3 핸드셰이크가 다룬다.

**무재시작 hot-handoff 전달(최적화 경로만).** 재시작조차 없애려는 최적화에서만: **단일 파일 `:ro` 마운트는 회전 불가**(마운트 시점 inode 고정 — man7 `mount(2)`·`rename(2)`, docker 문서; `ro`는 컨테이너 쓰기 방지일 뿐 호스트 교체 비동기화). → 디렉터리 `:ro` 마운트 + 내부 temp/rename(claude 재open 시 반영, 단 **in-process 재독 R14** 필요). **정직 표기**: socket 계열은 호스트 정규 파일 문제는 없애나 **UDS/FIFO 권한·docker exec stdin 경로·데몬 소켓 신뢰·부분 주입**은 별도 게이트로 잔존(전체 위험 소멸 아님).

**entrypoint 규율(공통).** 설치는 `install -m 600`(권한 창 제거). 자격증명 **자식 env 미주입**(env 상속→`capture_log` 유출 차단). **env 채널 봉인**: `run_args(env=)` 비밀 금지(문서 계약+리뷰, 자동 강제는 키 화이트리스트 별도). 파일 방식 임시 파일은 bind mount 성립 후 IDLE·종료 트리거에 제거(노출 창 최소화 R13).

**잔여 노출(정직).** ① 파일 방식: 전용 GID 성공 시 소유자·그룹 구성원·데몬만 창 동안 읽음. ② 컨테이너 내 복사본은 단일 uid 그 에이전트용. ③ 정지 컨테이너 HOME 잔존 → docker cp/commit 회수(R12) → `--tmpfs $HOME` 완화(§3.3).

**설정 seed 민감도.** `oauthAccount`가 PII면 world-readable seed는 need-to-know → 생성 시 제거/최소화(R11), 못 빼면 호스트-경계 내 노출 수용선 명시.

§4.1:672 "자격증명 비-정적화·런타임 주입" 원칙 계승, 운반은 "env 값 1개"→"**파일 마운트 부팅 + push 재시작 전달(요구) + (최적화) 무재시작 회전**"으로 구체화.

### 3.3 entrypoint·감독자 배치 + 재시작 아키텍처 + 잔존(tmpfs)

**권고: 이미지 ENTRYPOINT(exec-form) — 실 에이전트는 감독자, 그 외는 직접 exec.**

**재시작 바닥 아키텍처 — 감독자(A) 기본, 재생성(B) 게이트된 폴백.** 재시작 롤오버가 요구를 충족하므로 PID1↔tmpfs 충돌을 기본값으로 해소한다.
- **기본 = 감독자(A) entrypoint**: 감독자가 PID 1, claude는 **자식**(claude≠PID1). **재시작 시퀀스**: [감독자가 claude 종료] → [호스트가 push로 fresh AT 기입, §3.2] → [감독자가 새 claude fork/exec, 기동 시 재독] → [`--continue` 복원]. claude만 재시작(R14c)이 성립하고 tmpfs HOME 대화 기록이 **컨테이너 생존 동안 유지**돼 `--continue`가 읽는다(컨테이너 정지 시 tmpfs와 함께 소멸 — 잔존 없음). **채택 이유**: 대화내용 잔존 없음·tmpfs 재사용·컨테이너 교체 없음.
- **제어 채널 핸드셰이크(호스트 lease 관리자 ↔ 감독자, fail-closed)**: 두 프로세스(컨테이너 안 감독자·컨테이너 밖 호스트)를 번갈아 부르므로 순서 경쟁을 막는 계약을 둔다 — (1) 호스트 **stop 요청** → (2) 감독자가 claude 종료 확인 → (3) 호스트 **push 완료 + ack** → (4) 감독자 **신선도 검증**(지급 파일 `expiresAt`·세대 표식이 새 세대일 때만) → (5) **재기동 또는 거부**(낡음·실패·부분 주입·타임아웃이면 재기동 거부, fail-closed — 낡은 토큰 재시작 차단) → (6) 실패 상태 표면화. 이 핸드셰이크를 **R14c 계약에 명시**하고, **push 전달을 R14c(--continue 복원)에서 분리한 형제 게이트**로 두어 "전달 실패"와 "복원 실패"를 구분 측정.
- **감독자 계약(구현 의무, 과소서술 금지)**: (i) **초기화**(tini/`--init`류: 좀비 회수·신호 전달). (ii) **재시작 의무**(tini는 안 함 — 별도 컴포넌트: 트리거 감지·핸드셰이크·claude fork/exec). (iii) **PTY·신호·종료 전달**: `-it`(tmux, `backend.py.start_capture`)라 감독자가 PTY를 쥐면 SIGWINCH·SIGINT·SIGTERM을 자식 claude로 전달, **claude 자연(비-재시작) 종료코드를 컨테이너 종료코드로 전파**. (iv) **감독 범위 = 실 에이전트만**: placeholder/pytest는 **직접 `exec`(비감독)** — 감쌌다가 정상 종료를 재시작하면 무한 루프. 재시작은 외부 트리거에만, 자식 자연 종료는 코드 전파. 현행 pytest·tmux 공존을 실증 게이트로.
- **backend.py 계약 영향(공유 계약 변경, A 형상)**: claude≠PID1이면 claude가 죽거나 재시작 중이어도 컨테이너(감독자)는 running →
  - `is_alive()`(=`container.is_running()`)·`exit_code()`·`status()`가 **claude 부재 중 참을 내거나 감독자 코드를 낸다** → 감독자가 claude 자연 종료코드를 전파, 재시작 창 생존 의미(감독자 running ≠ claude ready) 정의.
  - **입출력도 같은 근원**: 재시작 창 동안 `send_text()`는 입력을 **버퍼링 또는 거부**(재시작 중 claude로 보내면 유실), `read_new_output()`은 **재시작 흔적 경계를 표시**(새 claude 기동 산출물이 스트림에 섞임 방지).
  - → **§4 공유 계약 변경에 `is_alive`/`exit_code`/`status` + `send_text`/`read_new_output` 의미 변화 편입**(소비자 agent_runner/leader 통보·계약 테스트).
- **폴백 = 재생성(B, R14c′)**: A의 push 전달(R14c) 또는 보안 측정이 실패할 때의 **게이트된 폴백**. claude=PID1 허용, 세대마다 컨테이너 재생성 + 새 부팅 파일 마운트(실행 중 전달 회피) + `--continue`. **B의 계약 결과(비대칭)**: backend.py 생존·입출력 계약은 **안 바꾸는 대신** "세션당 컨테이너 1개" 생애주기 가정을 바꾼다(세대마다 교체), tmpfs HOME이 죽으므로 **영속 트랜스크립트 볼륨**(대화 내용 잔존 — 자격증명 아님, 수용선) 또는 오케스트레이터 문맥 복원 필요. R14c는 감독자 형상, R14c′는 재생성 형상에서 각각 측정.

**이행(파손 방지).** 복사·주입·감독은 **조건부·모드 인지, 기본 fail-closed**: 실 에이전트·unknown은 seed/자격증명 미장착 시 기동 거부, placeholder/test는 skip+직접 exec. 판별은 allowlist(skip)+기본 deny. HOME은 uid로 `mkdir -p`(0700, R10). `$HOME` 비었거나 `/`면 중단. `--entrypoint` 오버라이드는 우회(운영 탈출구, 문서화).

**잔존 완화 — `--tmpfs $HOME` 기본(R12/R12′).** 정지·실패 컨테이너 HOME의 `.credentials.json` 회수(docker cp/commit)를 막는다(tmpfs는 stop 시 비영속, commit 미포함). `--tmpfs $HOME:uid=<uid>,gid=<gid>,mode=0700,size=<N>` — R10 uid `mkdir`·0700과 양립(옵션 수용은 버전 종속 **R12′**). 본체는 비정상 경로("실패로 rm 안 된 컨테이너"; 정상은 `backend.py` stop+rm). **나빠지는 점**: tmpfs는 **swap 설정에 따라 디스크로 샐 수 있음**(docker 문서 — swap 비활성·size 상한 검토), 정지 후 디버깅 상태 소멸. **감독자(A) 정합**: claude 재시작 시 컨테이너가 살아 tmpfs HOME(트랜스크립트)이 유지돼 `--continue`와 양립(재생성 B는 R14c′ 영속 볼륨이 tmpfs 밖).

**기본 CMD 미동결.** `leader.up`은 항상 명령 명시 전달 → Dockerfile `CMD`는 死경로. claude는 아직 이미지에 없음(R6). ENTRYPOINT/감독자 메커니즘만 지금, `CMD ["claude"]` 동결은 R6·Phase5 이후. container.py=provisioning(seed ro 마운트 + HOME + user + tmpfs + 감독자 스크립트).

### 3.4 §4.1 반영 형태 — Claude 한정 잠정 ADR, 게이트 재정착

**작동 방식.** §4.1·§9 계약을 seed+copy가 바꾼다 → ADR, `sot/<slug>` 사용자 게이트, 발의는 Maintainer/사용자.

**과승격 금지.** 실측은 Claude만. Codex `trust_level`(R5)·node(R6) 미해결 → **"Claude 한정 잠정"**. 요구 blocker(R2·R14c·R15)는 통과했으나, Codex arm·비잠정화는 R5/R6 및 잔여 저위험 게이트(R7b·R11·R12/R12′·R13·R14c′) 종료 후.

**측정 게이트 재정착.** 굽기(이미지 digest 고정) → seed+copy(가변 호스트 산출물). 이미지 arm: ENTRYPOINT·감독자 동작·claude 버전(R6) 빌드 게이트. seed arm: provenance/무결성(매니페스트+해시), `leader.up`이 seed 버전==이미지 버전 확인. 복합을 R9로 통과(파일마운트 부팅 완료), 바닥은 R14c/R14c′.

**seed 생성 파이프라인(신설).** 포함/제외(자격증명 제외, PII 최소화 R11), `projects` 키 호스트경로→`/work` 재작성, 호스트 보관 위치(`config.py` 헬퍼), 원자적 갱신. workspace `seed_from`(`leader.py:24`)과 구분 — "HOME provision seed".

**귀속 분리.** 측정 사실=Phase 3 → `PLATFORM_MATRIX.md`(CLI 버전). 설계 변경=SoT → ADR.

## 4. ADR 초안 골자 (발의 대기 — 번호·브랜치는 사용자 게이트)

- **제목**: 컨테이너 신뢰·자격증명 provision을 "이미지 굽기"에서 "seed+copy + 중앙 lease 갱신"으로 (Claude arm, 잠정)
- **상태**: Proposed — **Claude 한정 잠정**(잔여 게이트 종료 전 값 동결·Codex 확장 금지)
- **맥락**: §4.1은 신뢰·온보딩을 이미지에 굽고 자격증명만 런타임 주입(:672). 실측으로 항목 11-13 + R2·R3·R4·R7a·R8(참)·R9(파일마운트 부팅)/R10/R13(필요성)·R14c(복원+전달)·R15 — **요구 blocker 모두 통과**. **장기세션 요구 = "세션 지속(짧은 재시작 허용)"**(사용자) → 재시작 롤오버가 요구 충족, hot-handoff는 최적화.
- **결정**:
  1. 이미지에 굽지 않고 **read-only HOME provision seed 마운트→entrypoint가 uid HOME 복사**. 대체 요구는 무프롬프트 IDLE 관측 invariant — **파일 마운트 부팅 R9 충족**(push 부팅은 R9 재측정 대기).
  2. **자격증명 분리, accessToken-only**(refreshToken 미포함 — R1/R8). **부팅 = 파일 `:ro` 마운트 + 전용 GID(R13)**; **재시작 전달 = push(요구 인프라, R14c 포함, 핸드셰이크 fail-closed)**; 무재시작 회전은 최적화(디렉터리 마운트/R14). **R2 실패 시 컨테이너별 격리 로그인 폴백(그 경우 컨테이너 자기 갱신 허용 — 일반 규칙의 명시적 예외).**
  3. **이미지 ENTRYPOINT — 실 에이전트는 감독자(A, claude≠PID1) 기본, 그 외 직접 exec**. 감독자 계약(초기화·재시작·PTY/신호/종료코드 전달·감독 범위) 명시. **재생성(B)은 R14c 전달·보안 측정 실패 시 게이트된 폴백**. container.py=provisioning. CMD=claude 동결은 R6/Phase5 이후.
  4. **토큰 수명 = 중앙 lease 갱신기**(정품 claude 구동·원자적 저장, RT 중앙 한 곳). **요구 충족 = 재시작 롤오버(R14c, 전달·복원·공급 포함)**; hot-handoff(R14/R14d)는 최적화. **R15는 공급 전제 요구 게이트**(통과 — 실패 시 폴백·사람 개입 주기 명시). R8=참(확정)이므로 갱신은 반응형·최적화는 R14d 특정·**공급단 구동기도 같은 세대라 전용 계정 분리 필요**·공유 AT 다중 컨테이너는 전역 세대 전환/격리 로그인(R8=참·R4=통과 확정 → 함대 토폴로지 후속 설계).
  5. `config.CONTAINER_HOME=/tmp/axdt-home` **유지** — **위치 선택은 파일시스템 독립**(항목 12 무관). **별도로** 잔존 완화 위해 `--tmpfs $HOME`(uid/gid/mode/size) 추가(R12/R12′) — 두 결정은 구분.
- **결과(consequence)**:
  - 장점: 온보딩 키 확정 불요, 공유 쓰기 해결, accessToken-only로 RT 위험 중앙 국한, 재시작 롤오버가 미측정 hot-handoff 없이 요구 충족(부팅은 측정된 R9 재사용).
  - **공유 계약 변경(경로별)**: **(감독자 A 기본)** `container.run_args` argv에 seed·cred `:ro` + tmpfs + 감독자 스크립트 추가; **`backend.py` SessionBackend `is_alive`/`exit_code`/`status`/`send_text`/`read_new_output` 의미 변화**(claude≠컨테이너·재시작 창) → 소비자(agent_runner/leader) 통보·계약 테스트. **(재생성 B 폴백)** backend 생존·입출력 계약은 무변경, 대신 "세션당 컨테이너 1개" 생애주기 가정 변화·영속 트랜스크립트 볼륨 추가. → §9:1281 Phase 2 계약 변경.
  - **비용**: seed 생성·갱신·무결성 파이프라인 + 중앙 lease 갱신기(crown jewel — 감시·경보·원자적 저장·RT 만기 재로그인). 감독자 구현(PTY/신호/재시작·핸드셰이크). push 전달 경로. **R2 실패 폴백(격리 로그인) 시 대화형 로그인 N회·중앙 RT N배 관리**. **R8=참이면 전용 구동기 계정 운영**.
  - **보안 표면**: 중앙 갱신기 단일 장애점·최고가치 표적. accessToken bearer라 만료 전 탈취 유효. tmpfs **swap 유출**·정지 후 상태 소멸. **재생성 B 폴백 채택 시 영속 트랜스크립트 볼륨의 대화 내용 잔존**(자격증명 아님, 수용선). 전용 GID 구성원 경계·마운트 경로 노출(값 아님). push/socket 권한·부분 주입 별도 게이트. `run_args(env=)` 비밀 금지.
  - **측정 게이트**: seed provenance+버전 일치. **요구 blocker 모두 통과**(R2·R14c 전달+복원·R15 — handoff). **R8=참 확정**(단일 활성 AT) → 함대 토폴로지(한 계정 공유 N 컨테이너)에서 형제 롤오버=동족 살해, 공급단 구동기 세대 결속·반응형 갱신·전용 계정 분리 필요(발의 경고). **R1은 측정 유예·최악 가정 확정**(설계 방어, 요구 blocker 아님). 최적화 = R14/R14d. 남은 저위험 측정 = R7b·R11·R12/R12′·R13(전달수단)·R14c′.
  - **무결성 한계(정직)**: seed 무결성은 이미지 digest보다 약함 → 호스트 신뢰 경계 의존.
- **대체/무효화**: §4.1:663-678 Claude arm 대체(잠정). §9:1281을 "seed+copy + 중앙 갱신"으로. `leader.Dockerfile:2` 주석 정정 — P3/P5 귀속 모순 완전 해소 아님(R6 존속).
- **미해결(측정 게이트)**: R5·R6·R7b·R11·R12·R12′·R13(전달수단)·R14·R14c′·R14d + redact/PII. **측정 유예(결정) = R1**(최악 가정 확정, 설계 방어). **측정 통과(§1) = R2·R3·R4·R7a·R8·R9·R10·R14c(복원+전달)·R15.** 종료 전 값 동결·비잠정화 금지.
- **인용·병합**: 스펙·`live_probe*`는 phase2 브랜치 전용. ADR main 착지 시 병합 선후 명시.

## 5. 이행 순서(제안)

1. **요구 blocker: 모두 통과(§1·handoff) — 요구 측정 단계 종료.** R14c-복원·R2·R14c-전달·R15·R8(참 확정)·R4 통과. **R1은 측정 유예(최악 가정 확정, 설계 방어)** — 전용 유료 계정 확보 시 실측 후보. **남은 저위험 측정 배치(계정 무관)**: R7b(자연 만료)·R11(PII)·R12/R12′(잔존·tmpfs·swap)·R13(전용 GID 전달수단)·R14c′(재생성+영속 트랜스크립트). **최적화 게이트**: R14(재독+expiresAt 하위)·R14d(apiKeyHelper). **arm/빌드**: R5(Codex)·R6(node·claude 설치). **감독자 호환성 계약 테스트**(placeholder/pytest 비감독 exec, `sh -c` 종료코드·신호·stdout/stderr·tmux 관측, `send_text`/`read_new_output` 재시작 창 거동, `--entrypoint` 우회). — redact/PII.
2. 결과를 `PLATFORM_MATRIX.md`에 버전 병기.
3. container.py run_args 확장(seed·cred ro 마운트 + tmpfs + 감독자 스크립트) + ENTRYPOINT/감독자(조건부 복사·주입·실 에이전트 감독/그 외 직접 exec·핸드셰이크·claude fork/exec) — TDD, placeholder/pytest 공존 유지, backend.py 생존·입출력 계약 갱신·소비자 통보.
4. 중앙 lease 갱신기(정품 claude 구동·원자적 저장·핸드셰이크 호스트측) + seed 생성/갱신/무결성 도구 + `config.py` 경로 헬퍼.
5. ADR 발의(Claude 한정 잠정) → `sot/<slug>` 사용자 게이트.
