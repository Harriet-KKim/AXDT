# Phase 3 seed+copy — 측정 게이트 결과 로그

> 지위: Phase 3 seed+copy 설계(`WIP/reviews/phase3-seedcopy-provision/design-draft.md`)의 측정 근거. §2 게이트표·§5 순서의 실측 결과를 누적한다. 지금은 WIP 루트의 측정 워킹 문서이며, 설계가 리뷰 수렴 후 `WIP/specs/`로 승격될 때 이 문서도 설계와 같은 위치로 옮긴다. 값 동결·ADR 발의는 별도.
> 규율: CAPTURE-not-JUDGE — 증거(화면·exit code·필드 이름·mtime)만 수집, 값(토큰·PII) 미기록.
> 환경: AX-DEV(192.168.20.63, sst-ax-dev), docker 29.4.3, probe 이미지 `axdt/leader:probe`, 컨테이너 claude 2.1.209(R14c-전달 실행 시 관측). 확정 시점 CLI 버전 병기 — 버전 달라지면 재측정.
> 실행 방식: 실험 스크립트를 사용자가 `!`로 AX-DEV에 전달해 실행(호스트·자격증명 명령이 분류기에 막혀 사용자 대행). 스크립트 = job tmp `r*.sh`.

## 요약 표

| 게이트 | 질문(요지) | 판정 | 근거 | 스크립트 |
|---|---|---|---|---|
| R2 | accessToken만으로(refreshToken 없이) 세션 동작? | **통과** | refreshToken 제거 seed로 claude 인증·응답(pong, rc=0) | r2_at_only.sh |
| R4 | 같은 AT를 N상자 동시 사용 시 서버 충돌·이상탐지? | **통과(충돌 없음)** | 상자 2개 동시 호출 → alpha·bravo 각 rc=0 | r4_concurrent.sh |
| R8 | 새 AT 발급이 구 AT 무효화(단일 활성 AT)? | **참(무효화)** | 새 T2 발급 직후 구 T1 상자 → `401 OAuth access token has been revoked` | r8_rotation.sh |
| R14c-복원 | 새 claude 프로세스 넘어 `--continue` 대화 복원? | **통과** | 암호어 ZEBRA-4242-QUILL을 새 프로세스가 회상 | r14c_restore_v2.sh |
| R14c-전달 | 실행 중 상자에 fresh AT push → 새 claude가 읽어 동작 + 대화 복원? | **통과** | PRE 컨테이너 서버 401(Invalid bearer token)로 사망 확인 → push 후 `--resume`로 암호어 MAPLE-7731-RIVER 회상, 호스트 무변경 | r14c_deliver_safe.sh |
| R15 | 만료 임박 시 호스트 저비용 호출이 토큰 갱신 유발? | **통과(R8로 실증)** | R8 갱신 단계: 과거화→호스트 호출→새 토큰(mtime 변경·이후 T2로 동작) | r8_rotation.sh |
| R3 | uid가 쓴 mode 600 credentials 수용? | 통과 | design-draft.md §1 | (기존) |
| R7a | 모의 만료 시 컨테이너 자가 복구? | 실패(자가복구 못함) | design-draft.md §1 | (기존) |
| R9 | 분리 구성(설정+자격증명 별도)으로 IDLE 도달? | 통과(파일마운트 부팅 한정) | design-draft.md §1 | (기존) |
| R10 | 임의 uid가 자기 HOME 생성? | 통과 | design-draft.md §1 | (기존) |
| R13 | 임의 uid의 host-owned 600 마운트 읽기? | 필요성 실증(전달수단 미확정) | design-draft.md §1 | (기존) |

## 이번 라운드 상세 (값 미기록)

### R2 — accessToken-only 동작: 통과
- 방법: 호스트 자격증명 복사 후 `jq`로 `refreshToken`·`refreshTokenExpiresAt` 제거 → oauth 필드 = `accessToken`/`expiresAt`/`rateLimitTier`/`scopes`/`subscriptionType`. 그 seed로 상자 기동.
- 결과: `claude -p` 정상 응답(pong), rc=0.
- 함의: 컨테이너 지급은 accessToken만으로 충분 — 설계 §3.1 "accessToken-only" 전제 성립. refreshToken을 컨테이너에 넣지 않아도 됨(최소권한).

### R4 — 동일 AT 동시 사용: 통과(서버 충돌 없음)
- 방법: 같은 accessToken을 상자 2개에 넣고 동시(배경 실행) 호출.
- 결과: 두 상자 각각 alpha·bravo 응답, rc=0.
- 함의: 서버가 동일 AT의 동시 사용 자체를 막거나 이상탐지로 끊지 않음. R8(아래)의 "새 발급이 구 것을 죽인다"와는 별개 축 — 동시성 자체는 안전.

### R8 — 새 열쇠 발급이 구 열쇠 무효화: 참(확정)
- 방법: 상자 C1을 accessToken-only 정적 T1으로 기동·기준선 확인 → 호스트에서 `expiresAt` 과거화 후 호스트 claude 갱신으로 새 열쇠 T2 발급 → C1(여전히 T1)이 동작하는지 판정.
- 결과: 기준선 통과(C1이 T1으로 `baseline` 응답, rc=0) → T2 발급 성공(호스트 creds mtime 변경 관측) → C1 호출 시 `Failed to authenticate. API Error: 401 OAuth access token has been revoked.` rc=1.
- 판정: **R8=참.** 서버가 새 열쇠 발급 순간 구 열쇠를 폐기(단일 활성 AT 정책). 지역 만료 검사·네트워크 오류가 아니라 서버가 명시적으로 `revoked`라고 응답 — 직접 증거. (앞선 R14c 실험의 39분 토큰 사망 정황이 이번에 직접 확인됨.)
- 설계 영향: 설계 초안 §3.1 "R8=참 분기" 확정.
  1. 한 계정을 공유하는 다중 상자에서 형제 상자의 세대 롤오버가 **동족 살해**(아직 옛 열쇠 쓰는 상자를 끊음).
  2. 갱신 구동기가 사용자 호스트 로그인과 같은 계정이면 **사용자의 호스트 claude 사용이 상자 열쇠를 무효화** → lease 갱신기를 사용자와 분리된 **전용 계정**으로.
  3. **선제 갱신 금지**(옛 열쇠 쓰는 세션을 죽임) → 만료 임박 감지 후 갱신하는 **반응형**.
  - → ADR 발의 시 "단일-공유-계정 전제가 뒤집힐 수 있음" 경고 + 전역 세대 전환 프로토콜/격리 로그인 택일 상세화 대상.

### R14c-복원 — `--continue` 대화 복원: 통과
- 방법: 상자에서 claude로 암호어 저장(turn1) → **새 claude 프로세스** `--continue`로 회상(turn2). 자격증명은 호스트 파일 `:ro` 마운트(값을 새 디스크 파일로 쓰지 않음).
- 결과: 새 프로세스가 ZEBRA-4242-QUILL 회상, transcript(`.jsonl`) 존재 확인.
- 함의: 재시작 롤오버(감독자 A)·재생성(B) 두 바닥의 **공통 급소** 통과 — 설계 §3.1 최우선 게이트가 열림.

### R14c-전달 — push 소생 + `--resume` 대화 복원: 통과
- 방법: 호스트 자격증명을 **읽기만** 하는 안전변형(`r14c_deliver_safe.sh`). 컨테이너 부팅 후 설정·유효 자격증명을 `docker exec` stdin으로 주입(호스트 seed 파일 없음) → turn1로 암호어 저장 + `session_id` 캡처 → 컨테이너 사본 accessToken을 sentinel로 손상해 사망 재현 → PRE로 사망 확인 → 호스트의 현재 유효 자격증명을 push(주입, 절대경로·umask 077·원자적 mv·내용 검증) → POST에서 `--resume <session_id>`로 인증 소생 + 암호어 회상 확인.
- 결과: PRE에서 컨테이너 claude가 서버 401 `Invalid bearer token` 반환(rc=1) → 인증신호로 확증된 사망. push 후 POST가 `--resume 54068969`로 암호어 `MAPLE-7731-RIVER` 정확 회상(rc=0). 시작·끝 배너로 **호스트 자격증명 무변경** 확인. 총 16초, 우회(INCONCLUSIVE)·타임아웃 없음.
- 함의: R8=참(단일 활성 AT) 전제 하에 "push 없이는 죽고(서버 401), push로 되살아난다(인증 소생 + 대화 복원)"가 실증됨. 실행 중 상자에 fresh AT를 밀어넣는 **전달 수단**(`docker exec` stdin, 절대경로, umask 077, 원자적)이 작동하고, `--resume`가 자격증명 교체를 넘어 대화를 복원함. 설계 §3.2/§3.3의 전달·복원 게이트가 열림.
- 측정 안전: 계정 잠금 위험(무인 실제-자격증명 회전)을 구조적으로 배제한 변형. 사망은 컨테이너 사본에서만 재현하고, 소생은 호스트의 이미 유효한 자격증명을 읽어 전달했을 뿐 호스트를 write/mv/rm/chmod하지 않음. 실행 전 Fable·Codex 병렬 리뷰를 양쪽 "치명 없음"까지 7라운드 수렴(측정 타당성·안전 전제 검증).

## 남은 요구 blocker
- **없음** — 요구 blocker(R2·R4·R8·R14c-복원·R14c-전달·R15)가 모두 닫힘. R14c-전달 통과로 push 전달·복원 수단이 실증됨.
- 다음(설계 §5): 나머지 게이트(R1·R7b·R11·R12/R12′·R13·R14/R14d) 측정 → PLATFORM_MATRIX 기록 → 구현 → ADR 발의(`sot/<slug>`).

## 실험 안전성 메모 — 무인 회전 폐기, 호스트 무접촉 변형으로 측정
남은 R14c-전달을 무인(밤샘)으로 도는 러너(overnight.sh)로 만들어 Fable·Codex 다중 리뷰함.
- Fable: 치명 4건(복원이 새 토큰을 옛 백업으로 덮어써 계정 잠금 등) → v2에서 수정.
- Codex(xhigh): 수정 후에도 **호스트 실제 자격증명을 무인으로 반복 회전하는 접근 자체가 계정 잠금 위험이 불가역**이라 판정(실행 금지). 근거: 갱신의 서버 회전 ↔ 로컬 파일 기록 사이 desync, 비원자적 복원, 다른 claude와의 TOCTOU. 특히 **R1(갱신이 refreshToken을 회전시키고 재사용을 처벌하는가)이 미측정**이라 잠금 가능성 자체를 못 좁힘.
- 결론(실행 완료): 무인 실제-자격증명 회전은 폐기하고, **호스트 자격증명을 건드리지 않는 변형**(`r14c_deliver_safe.sh` — 컨테이너 안에서만 토큰 사망 재현 → 호스트의 유효 자격증명을 읽어 push로 소생)으로 재설계해 측정. 실행 전 Fable·Codex 병렬 리뷰를 7라운드 "치명 없음"까지 수렴, 사용자가 `!`로 attended 실행 → **R14c-전달 통과**(위 상세). 호스트 무변경 배너로 안전 전제 확인. R1(갱신이 refreshToken을 회전시키고 재사용을 처벌하는가)은 여전히 미측정 — 다음 라운드 후보.

## 측정 부산물 정리 대기
- 호스트 백업 3건: `.credentials.json.r8bak-r8-{1784302479,1784302838,1784303526}` — 모두 지금은 폐기된 옛 토큰(R8=참). 호스트 claude 정상 확인 후 제거.
- AX-DEV `/tmp/probe*` 옛 실험 잔재 확인·정리(각 스크립트 trap이 자기 것은 지우나 중단분 잔재 가능).
- AX-DEV `/tmp/r14c_deliver_safe.sh`(스테이징본)·`/tmp/r14c_safe.log`(값 미포함 결과 로그) — R14c-전달 측정 산출물, 확인 후 제거.
