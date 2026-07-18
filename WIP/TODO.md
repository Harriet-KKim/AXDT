# AXDT 프로젝트 완성 TODO

> **목표 범위**: 전체 비전 (6개 역할, Docker 격리, Tmux, Cron Watcher, Claude Code + Codex 동시 지원, GitHub/GitLab/Forgejo 연동, Local Web 브리핑, 메신저 양방향 연동)
>
> AI Agent들이 역할을 분담하여 문서(SoT) 기반으로 소프트웨어 개발을 자동 수행하는 워크플로 템플릿.
>
> 작성일: 2026-06-26 · 갱신: 2026-07-17 (최신 main을 phase6-enforcement에 병합·통합 — phase1 SoT 2키 완료판정 프레임워크[완료판정 계약·sot-lint·템플릿 재작성·ADR-0012~0015·확정 D23~D31] 위에 Phase 6 "SoT 완료 강제" 서브트랙[ADR-0009·머지 컨트롤러 강제]을 얹고, `sot-readiness.md`를 2키 판정 모델+머지 게이트 두 실현[(가) 집계 게이트 / (나) 머지 컨트롤러; Phase 6은 (나) 채택]으로 통합. ADR 0008~0010 등재) · 상태: 초안

---

## ✅ 확정된 결정사항

### D1. 오케스트레이터 실행 형태
- **Maintainer** = 프로젝트 시작~종료까지 **상시 실행되는 장기 tmux 세션**.
- **Watcher** = **Cron으로 주기 호출**되어 Maintainer의 **context 관리(압축/정리)** 만 담당.

### D2. Agent 간 통신
- **Maintainer → Leader**: tmux `send-keys`로 **prompt 직접 주입**. 별도 파일 채널 없음.
- **Leader → Maintainer**: **report 파일** (역방향 tmux 채널이 없으므로). 상향 통신 + 요약(summary) 겸용.
- **Leader ⇆ Leader**: 직접 통신 지양 → 의존성 조율은 **Maintainer 경유** (격리 원칙).
- **Leader ⇄ Developer/Reviewer/Tester**: Leader가 호출하고 결과를 돌려받는 **허브 구조**. sub-agent는 Leader에게만 응답하며 **상호 통신 없음**(sub-agent 간 직접 통신 불가) → Leader가 산출물을 중계하고 구현→리뷰→수정 루프를 매개.
- **사용자 ↔ Maintainer**: 메신저(양방향) + Local Web 브리핑.

### 상태 저장 — 별도 DB/큐 없음
- 영속 상태는 이미 **interim 파일** 안에 존재. 새 DB/큐/이벤트 로그를 만들지 않는다.
- 메신저 알림은 Maintainer가 상시 세션이므로 **결정 지점에서 직접 발송** (이벤트 큐 불필요).
- 메신저 inbound는 **stateless webhook 브릿지**가 받아 tmux `send-keys`로 Maintainer에 전달.

### D3. Docker 격리 수준
- **workspace당 컨테이너 1개** (Leader:workspace = 1:1). **해당 workspace만 read-write 마운트**, 그 외 차단.
- ⚠️ 구현 주의: `git worktree`는 메인 repo의 `.git`을 공유하므로, worktree 폴더만 마운트하면 컨테이너 내부에서 git이 안 됨 → Phase 3에서 **독립 `.git` 처리 또는 remote push 방식** 별도 설계.

### D4. Claude Code ↔ Codex 추상화
- 공통 **agent runner 인터페이스** + **Claude Code·Codex 어댑터를 둘 다 구현** (세션 기동/prompt 주입/출력 읽기).

### D5. 1차 Git 호스트
- **GitHub 우선** (`gh` CLI). GitLab·Forgejo는 어댑터로 확장.

### D6. 자동 개발 시작 트리거
- **세 트리거 모두 지원**: (주) **SoT PR이 main에 merge** / (보조) **명시적 시작 명령·플래그** / (보조) **마커 파일 존재**.

### D7. progress 파일 포맷
- **엄격 스키마 Markdown 테이블**. 파싱 안정성을 위해 **고정 컬럼 + 통제된 `status` 어휘**로 스키마를 엄격히 고정.

### D8. 1차 메신저
- **Discord** (webhook/봇). Slack·Lark는 어댑터로 확장.

### D9. 구현 언어 (Web 브리핑 + glue)
- **Python**. 브리핑 서버 + 메신저 브릿지 + workspace/docker/cron glue 스크립트를 한 언어로 통일.

### D10. progress git 추적
- **추적하되 wave/task 완료 마일스톤 경계에서만 커밋** (이력 보존 + churn 최소).

### D11. 디렉터리 문서화 방식
- 각 디렉터리에 **`README.md`** (목적 · 꼭 들어갈 내용 · 네이밍 규칙) + 문서를 담는 디렉터리엔 **`_TEMPLATE.md`** (Agent가 복제해 채우는 빈 양식).

### D12. src/·test/ 의 정체 & AXDT 자체 코드 위치
- **`src/`·`test/` = 이 템플릿으로 만들어지는 "대상 프로젝트"의 코드/테스트 자리.**
- AXDT 자체 구현(오케스트레이션 스크립트·웹서버·브릿지 등)은 **우선 `WIP/`에** 둔다(임시 위치).

### D13. 설계 결정 기록 방식 (ADR 정책)
- **비자명한 핵심 결정만 ADR**로 근거+대안 기록 (취향·1차 선택은 ADR 안 함 — rule/TODO로 충분).
- 규범적 규칙은 `docs/sot/rule/`(모든 프로젝트 전파), AXDT 자체 ADR은 `WIP/adr/`(D12 self-doc), 대상 프로젝트 ADR은 `docs/interim/ADR/`.
- **→ D19에서 규칙으로 구체화**: 촉발 조건 기반 `rule-adr-recording`로 승격(PR #8).

### D14. Branch/Workspace/Container 네이밍
- 한 작업 단위(task = Leader = workspace = container, 1:1)를 **단일 식별자 `w<n>.t<n>-<slug>`** 로 명명.
- 이 식별자가 **branch · workspace 디렉터리 · 컨테이너 이름을 일관되게** 결정 — branch·workspace 디렉터리 이름은 식별자와 동일, 컨테이너만 `axdt-` 접두. 슬래시(`/`) 미사용.
- 토큰 형식(`w<n>`/`t<n>`/`<slug>`)은 plan(wave/task) 템플릿의 id와 정합. 규칙: `docs/sot/rule/branch-workspace-naming.md`.

### D15. 규칙 강제 지점
- 강제는 **컨테이너가 손댈 수 없는 호스트/허브 층**에 둔다 — ① 물리 격리(유닛 간, D3) ② 로컬 pre-commit 훅(권고) ③ **호스트/허브 게이트**(강제: 허브 서버사이드 훅/branch protection, push 시 보호 경로·네이밍·SoT 위반 거부).
- 물리 마운트는 *유닛 간 격리*만 지킴 — `progress.md`·`sot/`·`plan/`은 clone 안에 들어오므로 **게이트가 유일 강제**. 게이트는 정책을 **신뢰 ref**에서 읽음. **런치 가드**로 격리 러너를 허브 자격의 유일 경로화(Maintainer는 호스트 상주 예외).
- 정확한 메커니즘은 두 갈래: **task-push 보호 = Phase 3**(`ADR-0007` accepted, 허브 모델 `ADR-0006` 의존, 명세 `rule-protected-paths`) · **SoT 완료 강제(①②③) = Phase 6**(`ADR-0009` proposed, 사양서 `WIP/specs/2026-07-08-phase6-enforcement-host-branch-protection-design.md`). 명세 = `docs/sot/rule/protected-paths.md`·`sot-readiness.md`.

### D16. 테스트 설계 = SoT 4번째 타입
- **테스트 설계**를 `docs/sot/test-design/`에 두고 requirements·specification과 **동급인 4번째 SoT 타입**으로 다룬다. 완료 판정에 포함 — 요구·사양과 함께 테스트 설계가 완료되어야 개발에 착수한다.
- 설계(SoT)/구현(`test/` 코드) 분리: SoT = 테스트 조건 · 블랙박스 커버리지 목표 · 스위트 구조 · 요구↔테스트 추적성 · 절차 원칙. `test/` = 구체 케이스 · 데이터 · 픽스처 · 스크립트 · 환경(D12, Tester 소관).
- 필수: 화이트박스 커버리지(결정/분기/MC-DC)는 SoT에서 제외(코드 없이 명세 불가 → 개발 전 완료 영구 미충족). 조건(SoT) vs 케이스(코드) 절단선을 template·rule에 명시.
- 근거·대안·대가: `WIP/adr/0008-test-design-as-sot-type.md`.

### D17. SoT 저술 역할 & PR 발의 모델
- **Author** = SoT(요구·사양·테스트설계) **저술 전용 역할** 신설. 개발 착수 이전 저술 단계의 행위자.
- SoT 변경 **PR 발의(생성)는 Maintainer만**. Author는 초안을 저술하고, 게이트에 올리는 것은 Maintainer가 대행.
- Leader는 SoT를 직접 push하지 않는다(요청만) — `rule-protected-paths`가 이미 `docs/sot/**` 직접 수정을 차단.
- 근거·대안: `WIP/adr/0011-sot-authoring-role-model.md`. 반영: `rule-sot-change-user-gate`(저술·발의 주체)·README 역할표.

### D18. SoT 작성 스킬(B-1) 방식
- **최선노력 단일 스킬** — 사람이 있으면 대화형으로, 없으면 Leader 요청문을 입력받아 초안→PR. ③ 사용자 게이트가 사람 개입의 불변점.
- SoT PR은 **요구·사양·테스트설계 3종을 항상 동반**한다(부분 SoT PR 금지) — 세 문서의 정합이 완료 판정의 전제라 함께 움직인다. **(→ D26/ADR-0013에서 '주제 신설·`covers` 변경 시'로 한정 개정.)**

### D19. 결정 근거 기록 규칙 (D13 구체화)
- 모든 PR은 핵심 결정·기각 대안을 요약(바닥선). 촉발 조건에 걸리는 지속적 결정은 ADR로 승격(권고).
- D13의 "비자명하면 ADR" 소프트 관행을 촉발 6종·비촉발 3종의 패턴 대조로 구체화 → `docs/sot/rule/adr-recording.md`(신설, `scope: local`).
- 강제는 "촉발을 PR에서 인정"까지(ADR 링크 또는 생략 사유). ADR 파일 존재는 기계 강제 안 함.

### D20. SoT 형식 검사기 (sot-lint)
- 완료 판정 ①(형식 검증)의 검사기 = **`sot-lint` Python 스크립트**. B-1 산출물로 지금 만들고, Phase 6에서 `axdt` 패키지로 승격 + CI 배선(단일 구현, drift 없음).
- Phase 6 이전 ②(정합성·공백 LLM 검토) 자동 실행 공백은 별도 장치를 두지 않는다 — CI 담당이며, 그전 공백은 AXDT dev/test 국한이라 무의미.

### D21. SoT 항목 선언 명시 (frontmatter `items`)
- SoT 항목 선언의 **정본을 본문 산문이 아니라 frontmatter `items` 목록**으로 둔다. 존재(①C1)·항목 ID·중복(①C2)·참조 무결성(①C3)이 frontmatter↔frontmatter 구조 대조가 되어, 산문 heuristic 분류의 취약성을 제거한다.
- 선언 유일 키 = 참조 해소 키 = `(topic, ID)`. 같은 `(topic, ID)`가 둘 이상 선언되면 형식 위반. 본문 볼드 표기는 `items`와 일치해야 한다(정합 검사).
- 반영: `docs/sot/{requirements,specification,test-design}/_TEMPLATE.md` frontmatter `items` 추가 + `rule-sot-readiness` ① 문구 정합화. **sot-lint 구현보다 먼저** 처리하는 SoT 개정(`sot/item-declaration` 게이트 PR).
- 기각 대안: 산문 heuristic 분류(선언/참조를 섹션·문맥으로 추정 — 취약), inline marker(본문 표식 — 파싱이 여전히 산문 의존).

### D22. sot-lint 세부 확정 (금지어·CLI·참조)
- **금지어**(①C5): 닫힌 최소 목록 `TBD·TODO·FIXME·미정·추후·나중에`, 코드 상수 단일 관리. ASCII는 대소문자 무시+단어 경계, 한글은 정확 매칭. 오검 시 후속 조정. (확장형 목록 대안 폐기 — 최소부터.)
- **CLI**: 독립 모듈 `python -m axdt.sot_lint`, 위치 `WIP/axdt/sot_lint/` 패키지. Phase 6에서 `axdt` 하위 명령 흡수. (단일 파일 `WIP/tools/sot_lint.py` 대안 폐기.)
- **참조 무결성**(①C3): spec.covers→요구 items, td.covers→요구·사양 items(`topic:FR-1` 교차 접두, 접두 없으면 같은 topic), `*.rules`→rule id 레지스트리(`rule/_TEMPLATE` 제외). 스펙 정리: `WIP/drafts/sot-lint-spec-draft.md`.
- 다중모델 리뷰(Codex·Fable)로 스펙 검증 후 Sonnet 구현 위임.

> 📌 D23~D31 = phase1 산출물(sot-lint·두 스킬·`rule-sot-readiness`)에 대한 **Codex-Sol·Fable 다중모델 리뷰** 확정 결정(리뷰 라벨 A1~C1). 각 항목은 "구현 대상"이며 강제(CI)는 여전히 Phase 6.

### D23. sot-lint C6 = 수용 기준 섹션 한정 (리뷰 A1)
- C6(수용 기준 채워짐)의 체크박스 스캔을 **`## 수용 기준` 섹션 안으로 한정**한다. 기존엔 본문 어디에 있든 항목 ID로 시작하는 체크박스를 그 항목의 수용 기준으로 인정해, 다른 섹션의 체크박스가 진짜 수용 기준 자리를 가로챌 수 있었다.
- 섹션 식별 = **레벨2 제목 `## 수용 기준` 정확 일치**(앞뒤 공백 제거 후 제목 텍스트가 `수용 기준`). 섹션 범위는 다음 레벨1/2 제목 전까지. 코드펜스 안 가짜 제목은 마스킹으로 무시.
- `items`가 선언됐는데 섹션이 없으면 항목별 "체크박스 없음" N건 대신 **`수용 기준 섹션 없음` 1건**으로 fail-closed(잡음 감소 + 구조 결함 명확화).
- 반영: `WIP/axdt/sot_lint/`(섹션 파서 추가) · `WIP/drafts/sot-lint-spec-draft.md` C6 · `rule-sot-readiness` ① C6 문구("수용 기준 섹션 하위 체크박스"). 세 콘텐츠 템플릿 모두 이미 `## 수용 기준`이라 마이그레이션 없음.

### D24. 플레이스홀더 문법 `<...>` → `{{...}}` (리뷰 A2)
- 템플릿의 미기재 자리 표기를 `<...>`에서 **`{{...}}`**로 바꾼다. sot-lint C4(미치환 플레이스홀더)·C6의 플레이스홀더 판정 정규식도 `{{...}}` 기준으로 교체한다.
- 사유: `<...>`는 Markdown 자동링크(`<https://…>`)·제네릭 타입(`Map<K,V>`) 같은 정당한 본문과 충돌해 오탐했다. `{{...}}`는 본문에 자연 등장하지 않아 오탐 표면을 없앤다.
- 반영: `docs/sot/{requirements,specification,test-design}/_TEMPLATE.md`(모든 `<...>` 치환) · sot-lint C4·C6 정규식 · `sot-lint-spec-draft` 플레이스홀더 절.

### D25. 추적성 `covers`는 문서 단위 flat 유지 (리뷰 A3)
- `covers`(요구·사양 ↔ 테스트 매핑)는 **문서 단위 평면 목록**으로 유지한다. 항목별 세분 매핑으로 구조를 바꾸지 않는다.
- 역할 분담: **①(형식)은 `covers` 참조가 실재하는지(존재)만** 검사하고, **매핑이 타당한지는 ②(정합성 검토)의 몫**이다. 추적성 표는 공백·고아를 눈으로 보는 뷰이며 `covers`와 일치해야 한다.
- 반영: 템플릿의 "이 표는 같은 매핑을 …" 문구를 정정 — `covers`는 평면 합집합(① 존재 검사용), 표는 항목 수준 뷰(② 판정용)로 성격이 다름을 분명히 한다.

### D26. SoT PR 3문서 강제 동반의 범위 한정 (리뷰 B1) — D18 개정
- D18의 "SoT PR은 요구·사양·테스트설계 3종을 항상 동반"을 **새 주제(topic) 신설 또는 추적 관계(`covers`) 변경 시로 한정**한다. 그 외 편집(오타·단일 문서 내 명료화 등)은 3종 강제 대신 **영향 범위 분석**으로 동반 문서를 판단한다.
- 사유: 세 문서의 정합이 완료 판정의 전제가 되는 지점은 "무엇을 다루는가(주제·커버리지)"가 움직일 때다. 문구 수정까지 3종을 묶으면 불필요한 동반 변경과 리뷰 부담만 커진다.
- 반영: `ADR-0013`(D18 개정 근거·대안) · `sot-authoring/SKILL.md` PR 번들 규칙.

### D27. ② 재검토는 판정 키 변경 시 전량 재실행 (리뷰 B2)
- ②(정합성·공백 LLM 검토)는 **판정 키가 바뀌면 전량 재실행**한다. 이전 회차 검토 결과(감사 로그)를 이월 입력으로 넣지 않는다.
- 사유: 이전 판정을 입력으로 받으면 바뀐 내용이 옛 판정으로 세탁(laundering)되는 우회가 생긴다. 판정 키는 이미 내용·적용 규칙에 결속되므로, 키가 바뀌면 처음부터 다시 본다(fail-closed).
- 반영: `sot-readiness-review/SKILL.md` 입력에서 감사 로그 이월 제거 · `rule-sot-readiness` ② 문구.

### D28. 완료 판정을 두 키로 결속 — 정합성 판정 키(+정책 epoch·카탈로그 digest) + 선언 완전성 스윕 키 (리뷰 B3·라운드4~5)
- 정합성 판정 키에 두 성분을 추가하고, 선언 완전성용 별도 키를 둔다(무효화·재검토는 각 키 단위 — 키가 바뀌면 projection 전량 홀리스틱 재검토, 부분 문서 타겟팅 없음).
  - **(i) `review_policy_epoch`**(두 키 공통) — 검토 정책·실행기 버전. **(저장소 파생) 완료 판정 규칙(`sot-readiness.md`·`sot-change-user-gate.md`)·검토 스킬 해시 + (실행 환경 파생) 검토 실행 모델 revision + 신뢰 실행기 버전 digest(하니스·직렬화기·파서·키 계산기·프롬프트 스캐폴드; 정본 열거는 `rule-protected-paths` 실행기 manifest) + 추론 설정 digest**. 프롬프트 digest는 정책 불변부만(대상 SoT·rule 입력·키 값·ref·시각 등 가변 데이터 제외 — 안 그러면 카탈로그 본문이 epoch로 판정 키에 새어들거나 재사용이 죽음). 규칙·스킬·모델·프롬프트·설정·실행기가 바뀌면 무효가 된다.
  - **(ii) rule catalog manifest digest**(정합성 키) — 규칙 카탈로그의 `{path, id, scope, status}` 다이제스트(`README`·`_TEMPLATE` 제외). 규칙의 **추가·삭제·이동(path)·id·scope·status**를 감지해, `scope: local` 규칙 신설로 아무 문서도 정합성 재검토 안 되는 공백과 활성 전이(deprecated·superseded)를 닫는다.
  - **(iii) 완전성 스윕 키**(별도 키) = (트리 해시, **활성 카탈로그 입력 digest**, epoch). 입력 digest = 완전성 검사에 실제 직렬화돼 들어가는 바이트(정규화 repo-relative `path` 정렬 `{path, frontmatter 포함 전체 내용}` canonical serialization; 활성 rule만, README·_TEMPLATE 제외 — `path` 포함이라 rename이, frontmatter 포함이라 scope 전환이, 활성 한정이라 status 전환이 각각 결속), PR·ref·시각은 LLM 컨텍스트 제외. 선언 완전성 검사(문서가 실제 의존하는 `scope: local` rule을 `rules`에 다 선언했는가; global은 선언 불요라 대상 아님)만 결속. 완전성은 활성 rule 본문 전량을 봐야 미선언 의존을 탐지하는데, 그 본문을 정합성 키에 넣으면 미선언 rule(대개 오케스트레이션) 편집마다 정합성이 헛발화(ADR-0015 위배)하므로, 입력이 다른 이 검사를 별도 키에 결속. 라운드4 리뷰의 "완전성 입력이 판정 키 밖 → 캐시 우회로 완료 잘못 열림" blocking을 이 키로 닫음.
- 사유: `scope`는 어느 규칙 변경이 적용 규칙 지문(성분2)에 들어가는지만 게이팅하므로, 완료 판정 규칙 자체나 규칙 목록 변화는 지문만으론 무효화 안 됨. 키에 명시 결속해 fail-closed. `scope: global`로 우회 못 함 = global은 규칙 파일 본문만 지문에 넣을 뿐 스킬·모델·프롬프트·실행기를 못 새김(epoch의 몫). 완전성 입력↔정합성 헛발화 방지는 두 키 분리로 둘 다 얻음.
- 반영: `rule-sot-readiness` §판정 키/완전성 스윕 키 정의·강제 매핑 · `ADR-0014` · 검토 스킬 보호경로(`rule-protected-paths`).

### D29. accepted/rejected 행위자 인증 = ③ 게이트 승인자 재사용 (리뷰 B4)
- 완료 상태를 `accepted`/`rejected`로 확정하는 행위자의 인증은 **③ 사용자 게이트 승인자(CODEOWNERS·지정 사용자)를 재사용**한다. 별도의 두 번째 "사용자" 개념을 만들지 않는다.
- 강제는 **호스트별(GitHub/GitLab/Forgejo) fail-closed** — 신뢰 집계 게이트가 호스트 이벤트의 actor를 읽어 승인자와 대조하고, 확인하지 못하면 거부한다.
- 반영: `rule-sot-readiness` §②/강제 매핑(행위자 인증 조항).

### D30. 트리 해시에서 README·_TEMPLATE 제외 (리뷰 B5)
- 완료 판정 키의 **SoT 트리 해시가 투영하는 경로에서 `README.md`·`_TEMPLATE.md`를 제외**한다(sot-lint의 검사 제외와 정렬). 정확한 path projection을 규칙에 명문화한다.
- 사유: README·템플릿은 대상 SoT 콘텐츠가 아니라 안내·빈 양식이다. 이들 편집이 완료 무효화·②·개발 착수 트리거를 헛발화시키지 않게 한다.
- 반영: `rule-sot-readiness` §적용범위/트리거(경로 투영 정의).

### D31. 베이스 규칙 `scope` 분류 = 전부 local (리뷰 C1)
- `docs/sot/rule/`의 `scope` 미기재 규칙 **10종에 전부 `scope: local`**을 부여한다(global 없음). global은 미래의 **도메인 콘텐츠 규칙**(공용 용어집·공용 식별자 명명 등 대상 SoT 콘텐츠를 횡단 제약하는 규칙)용으로 유보한다.
- `rule-sot-readiness`의 global 예시 "용어·네이밍 등 횡단"을 **"도메인 공용 용어·공용 식별자 명명(브랜치 명명이 아님)"**으로 정정한다 — 현행 오케스트레이션·거버넌스 규칙은 대상 콘텐츠를 제약하지 않아 local이다.
- 분류 기준(콘텐츠 규범 → 횡단성에 따라 global/local, 거버넌스·완료정책 → local)을 `scope` 주석/README에 명문화한다. 완료정책 규칙(`sot-readiness`·`sot-change-user-gate`)의 완료 결속은 `scope`가 아니라 **D28(i) epoch**가 담당하므로 local이어도 무효화를 잃지 않는다.
- Codex-Sol이 제안한 `kind:` 필드 개편은 보류(현 이분 + 분류 기준 문서화로 충분). 반영: `ADR-0015` · 규칙 10종 frontmatter · `rule-sot-readiness` 예시·`README`.

> 📌 현재 미결 결정: **없음**. 구현 중 새 갈림길이 생기면 여기에 D32~ 로 추가한다.

---

## 📖 용어 정의  *(→ `docs/sot/rule/` 편입 확정 — D13)*

| 구분 | 위치 | 의미 | 작성 주체 | 변경 |
|---|---|---|---|---|
| **SoT** (Source of Truth) | `docs/sot/` | 초기에 세우는 **권위본** (requirements/specification/test-design/rule) | Agent 작성, **변경은 사용자 게이트 PR로만** | 통제됨 |
| **Interim** (중간 산출물) | `docs/interim/` | 작업 중 생성·변경되는 파일 (ADR/plan/report/progress) | **Agent** (Leader·Maintainer 무관, 단 개별 파일에 더 좁은 제약 가능) | 자유 |

핵심 구분: **"권위본이라 변경이 통제되는가(SoT)" vs "작업 중 만들어지고 자유롭게 바뀌는가(interim)"**.
interim은 사람이 아니라 Agent가 쓰는 작업 공간.

### interim 파일별 역할 & 작성자

| 파일 | 역할 | 작성자 | 상태(status) 보유 |
|---|---|---|---|
| **plan** (wave/task) | 작업 **정의·구조** ("무엇을 할지") | **Maintainer** (분해·배정) | ❌ 없음 |
| **report** | task별 상세 + **Leader 자기보고 상태** | Leader | ✅ `report.status` (Leader 소유) |
| **progress** | 오케스트레이션 **색인 + 수용 상태** (report는 canonical 경로로 판정, 컬럼 아님) | **Maintainer만** (단일 작성자) | ✅ `progress.status` (Maintainer 소유, 시스템 권위) |

---

## 📊 상태 모델 (status flow)

상태는 한 곳에만 사는 게 아니라, **계층마다 권위 주체가 하나씩 있고 흐름은 한 방향**이다.

```
Leader ─(report.status 기록: 자기 작업 주장)─┐
                                            │  Maintainer가 읽고 검토/수용 (게이트)
                                            ▼
Maintainer ─(progress.status 기록: 수용된 진실)─> 시스템·웹·의사결정은 이걸 권위로 읽음
```

- `report.status` 는 **"Leader가 어떻게 보고하는가"**, `progress.status` 는 **"오케스트레이터가 무엇을 참으로 수용했는가"** 에 답한다 — 서로 다른 질문.
- 둘이 다르면 모순이 아니라 **"Maintainer 처리/수용 대기"** 라는 정상 상태. **권위는 항상 progress.**
- report→progress 승격이 곧 **Maintainer의 검토/게이트 지점** (집계 + 수용 + 필요시 Reviewer/Tester/사용자 게이트 + wave 롤업).

---

## 🔀 통신 채널 맵

```
사용자 ⇅ Maintainer          : 메신저(양방향, Phase 7) + Web 브리핑(read-only, Phase 7)
Maintainer → Leader          : tmux send-keys (prompt 주입)
Leader → Maintainer          : report 파일 (상향, 자기보고)
Watcher → Maintainer         : context 점검·정리 (Cron, 제어)
Leader ⇄ Dev/Reviewer/Tester : Leader가 호출·결과 수신 (허브). sub-agent는 Leader에게만 응답
Dev/Reviewer/Tester 상호간   : 직접 통신 없음 (sub-agent 간 통신 불가) → Leader가 산출물 중계
Leader ⇆ Leader              : 직접 통신 지양 → Maintainer 경유
메신저 inbound               : 사용자 → webhook 브릿지 → tmux send-keys → Maintainer
```

---

## 🗃️ 디렉터리 구조 & 문서 요건  (D11·D12)

```
docs/
  sot/                  # 권위본 (변경 = 사용자 게이트 PR)
    specification/
    requirements/
    test-design/
    rule/
  interim/              # 중간 산출물 (가변, Agent 작성)
    ADR/
    plan/
      wave/
      task/
    report/             # 🆕 task별 Leader 보고
    progress.md         # 🆕 단일 진행 기록 (Maintainer 단독)
src/                    # 대상 프로젝트 코드 (D12)
test/                   # 대상 프로젝트 테스트 (D12)
WIP/                    # AXDT 자체 구현·기획 임시 위치 (D12)
```

각 디렉터리에 `README.md`(목적·필수내용·네이밍), 문서를 담는 곳엔 추가로 `_TEMPLATE.md`(복제해 채우는 빈 양식).

| 경로 | 목적 | README 필수 내용 | 템플릿 |
|---|---|---|---|
| `docs/` | 문서 루트 | SoT vs interim 구분 안내 | — |
| `docs/sot/` | 권위본 루트 | 권위성·변경은 사용자 게이트 PR로만 | — |
| `docs/sot/specification/` | 시스템이 **무엇을 어떻게** (동작·인터페이스·데이터) | 범위·구성요소·인터페이스·데이터모델·동작·수용기준·참조 | ✅ Spec |
| `docs/sot/requirements/` | **무엇이 왜** 필요 (기능/비기능) | 목표·기능요구·비기능요구·제약·범위외·수용기준 | ✅ Req |
| `docs/sot/test-design/` | 요구·사양을 **어떻게 검증** (조건·커버리지·스위트·추적·절차) | 범위·테스트조건·커버리지목표·스위트·추적성·절차원칙·수용기준·참조 | ✅ TestDesign |
| `docs/sot/rule/` | 프로젝트 규칙 (네이밍·용어·표준) | 규칙문·근거·적용범위·예시 | ✅ Rule |
| `docs/interim/` | 중간 산출물 루트 | 가변·Agent 작성·비권위 안내 | — |
| `docs/interim/ADR/` | 아키텍처 결정 기록 | 번호·제목·상태·맥락·결정·결과·대안 | ✅ ADR |
| `docs/interim/plan/` | 작업 분해 루트 | wave/task 관계, **상태 필드 없음** | — |
| `docs/interim/plan/wave/` | wave (마일스톤=task 묶음) | wave id·목표·포함 task·의존·종료기준 | ✅ Wave |
| `docs/interim/plan/task/` | task (Leader 단위) | task id·상위 wave·목표·범위·의존·DoD·대상 workspace/branch | ✅ Task |
| `docs/interim/report/` | Leader 보고 | task 참조·`report.status`·요약·완료내역·블로커·사양변경요청·다음 | ✅ Report |
| `docs/interim/progress.md` | Maintainer 진행 기록 | 고정 컬럼 MD 테이블 (D7) | ✅ (스키마=양식) |
| `src/` · `test/` | 대상 프로젝트 코드/테스트 | 레이아웃·테스트 규약 | — |

---

## Phase 0 — 기반 정비 (Foundation)

- [x] 파일명 오타 수정: `Initail_Idea.md` → `INITIAL_IDEA.md` (또는 `docs/`로 이동) ✅ 2026-06-30
- [x] 저장소 디렉터리 구조 스캐폴딩 생성 ✅ 2026-06-30
  - [x] `docs/sot/{specification,requirements,rule}`
  - [x] `docs/interim/{ADR,plan/{wave,task},report}` + `docs/interim/progress.md`
  - [x] `src/`, `test/` (대상 프로젝트 자리, D12)
- [x] **각 디렉터리에 `README.md` 작성** (목적·필수내용·네이밍, D11) ✅ 2026-06-30
- [x] `.gitignore` 작성 (Docker, workspace, 런타임 산출물 제외 — **progress는 추적**, D10 마일스톤 커밋) ✅ 2026-06-30
- [x] `LICENSE` 선택 및 추가 ✅ 2026-06-30
- [x] `README.md` 보강 (사용법/빠른 시작 섹션 추가) ✅ 2026-06-30
- [x] 지원 도구/버전 매트릭스 명시 (Docker, tmux, git, **Python**, Claude Code, Codex) ✅ 2026-06-30
- [x] 초기 커밋 + 브랜치 전략 문서화 ✅ 2026-06-30
- [x] **AXDT 베이스 규칙 문서화** (`docs/sot/rule/` — 모든 프로젝트에 전파되는 공통 규칙) ✅ 2026-06-26
  - [x] 용어 정의 (SoT/Interim) → `terminology.md`
  - [x] Branch/Workspace 네이밍 규칙 → `branch-workspace-naming.md` (D14)
  - [x] 통신·상태 규범 (progress 단일 작성자 / sub-agent 직접 통신 금지·Leader 허브 / Leader 간 Maintainer 경유 / SoT 변경=사용자 게이트) → `progress-single-writer`·`subagent-no-direct-communication`·`leader-coordination-via-maintainer`·`sot-change-user-gate`·`report-to-progress-authority`
  - [x] 규칙 "전파" 개념 명시 (베이스 규칙이 신규 프로젝트로 상속) → `propagation.md`
  - [x] 보호 경로 규칙 (role→쓰기허용 경로 명세, 강제 계층) → `protected-paths.md` (D15)
- [x] **AXDT 자체 설계 ADR 작성** (`WIP/adr/` — 비자명 결정의 근거+대안, D13) ✅ 2026-06-26
  - [x] D1: Maintainer = 상시 tmux 세션 (왜 무상태/Cron이 아닌가) → `0001`
  - [x] 별도 DB/큐 없음 (report·plan이 상태를 담음, Web은 read-time 렌더) → `0002`
  - [x] D2: 통신 모델 (tmux 하향 / report 상향 / Leader 허브 / sub-agent 비통신) → `0003`
  - [x] 상태 모델: report→progress 단방향 권위 흐름 → `0004`
  - [ ] D15: 강제는 호스트/허브 층 (물리 격리 + 권고 훅 + 권위 게이트) → `0007`(proposed)
  - [x] D16: 테스트 설계 = SoT 4번째 타입 → `0008`
  - [x] SoT 완료 강제(머지 컨트롤러) 설계 → `0009`
  - [x] Git 호스트 추상화((b) 클라이언트) → `0010`

## Phase 1 — SoT 문서 시스템 (Source of Truth)

- [x] 각 문서 디렉터리에 `_TEMPLATE.md` 작성 (frontmatter + 필수 섹션, D11) ✅ 2026-07-02
  - [x] specification `_TEMPLATE.md`
  - [x] requirements `_TEMPLATE.md`
  - [x] test-design `_TEMPLATE.md` ✅ 2026-07-07 (D16)
  - [x] rule `_TEMPLATE.md`
  - [x] ADR `_TEMPLATE.md`
  - [x] plan/wave · plan/task `_TEMPLATE.md` (**상태 필드 없음**)
  - [x] report `_TEMPLATE.md` (`report.status` 포함)
  - [x] progress.md 빈 양식 (고정 컬럼 테이블, D7 — Phase 4와 정합)
- [x] **요구사항/사양/테스트 설계 작성 Skill** 제작 (Agent와 대화형 작성) — B-1 (D18) ✅ 2026-07-12
  - [x] 설계 초안 + 브레인스토밍 결정 확정(D17~D20) ✅ 2026-07-09
  - [x] 파급(Author 역할·`rule-adr-recording`·`ADR-0011`) 게이트 PR #8 ✅ 2026-07-09
  - [x] 선언 명시 SoT 개정(D21) — 템플릿 3종 `items` + rule ① 정합화, `sot/item-declaration` 게이트 PR #9 ✅ 2026-07-09
  - [x] 스킬 본체(`SKILL.md`) 구현 — `.claude/skills/sot-authoring/SKILL.md`. 초안→스펙 리뷰→Sonnet 위임 구현, 다중모델 리뷰 2R(지시서 R1·구현물 R2, Codex·Fable) 반영. 커밋 55472ab ✅ 2026-07-12
  - [x] `sot-lint` 형식 검사기 스크립트(D20·D22) — 완료 판정 ① 구현. `WIP/axdt/sot_lint/`(6모듈+테스트, pytest 94 — C3 `status: active` 참조 무결성 6건[deprecated·superseded·active통과·누락·기형·대소문자] + 템플릿 `{{...}}` 회귀 4건 + 백틱 펜스 마스킹 우회 회귀 2건 + C6 매핑 회귀 3건 포함), 다중모델 리뷰 반영. 강제(집계 게이트의 증거 산출)는 Phase 6. ✅ 2026-07-10
- [x] SoT 변경 워크플로 정의 (Reviewer=사용자 게이트가 있는 PR 기반) — `sot-change-user-gate`(발의·일시정지·재개·`sot/<slug>` 브랜치)·`protected-paths`(task 경로 차단)·`sot-readiness`(머지 판정 ①②③·main require-PR·감사 이력 보존)에 정의 완료, 강제는 Phase 6 ✅ 2026-07-07
- [ ] **문서 완료 판정 기준 정의** (→ 자동 개발 시작 트리거, D6) — `rule-sot-readiness` · 설계·정의 커밋 완료. 강제: **① 형식 검사와 ②의 두 검토(정합성·완전성)는 모두 비필수 증거 검사**(산출물)이고, 머지 차단 **필수 검사는 집계 게이트 `sot-readiness-gate` 하나**뿐 — Phase 6
  - [x] 형식 기준 (기계 검증: 문서 존재·플레이스홀더 없음·필수 섹션·TBD 없음) — 검사기 `sot-lint` 구현 완료(D20, `WIP/axdt/sot_lint/`), 강제(집계 게이트의 증거 산출)는 Phase 6 ✅ 2026-07-10
  - [x] 정합성·공백 + 선언 완전성 LLM 검토 Skill (requirements·specification·test-design 3원 정합성 + 누락/미고려 지점 + `rules` 선언 완전성) → `.claude/skills/sot-readiness-review/` — 스킬 구현 완료(a770050), 강제(집계 게이트의 증거 산출)는 Phase 6 ✅ 2026-07-06
  - [ ] 검토 감사 로그 `docs/interim/sot-readiness-review.md` (스킬 생성, 게이트 비신뢰 사본 — 스키마는 스킬이 규정) — **정의 완료**(스킬 `SKILL.md` 기록 섹션), 실 기록은 ② 검토 **CI 자동 실행 = Phase 6**
  - [ ] 사용자 게이트 최종 판정 연결 (`rule-sot-change-user-gate`) — **정의 완료**(`rule-sot-readiness` ③·강제 매핑), 배선은 집계 게이트 `sot-readiness-gate` = **Phase 6**

## Phase 2 — 역할(Role) 정의 & 통신 프로토콜

각 역할별로 책임 / 시스템 프롬프트 / 호출 인터페이스 / Skill 정의.

- [x] **역할·프로토콜 설계 스펙 확정** — 10차 개정 3모델 치명0 수렴 (`WIP/specs/2026-07-09-phase2-roles-and-protocol-design.md`, PR #10) ✅ 2026-07-14
- [x] **§8.3a 라이브 측정 하네스** 구현·다중모델 리뷰 수렴 (`live_probe.py`, Codex·Fable 전 심각도 clear — 구현 착수 게이트 *도구*) ✅ 2026-07-14
- [ ] **§8.3a 라이브 측정 실행**(AX-DEV 착수) — 실측 결과 **상태판정 마커·모델이 현재 CLI(claude 2.1.209)에 부적합**함을 확인(캐럿·푸터가 IDLE/BUSY 공유, 스피너 랜덤, statusLine 상태 미탑재). **훅 기반 상태판정**이 대안임을 실증(SessionStart→IDLE·UserPromptSubmit→BUSY·Stop→IDLE, codex도 동일 훅). `detect_state` 재설계는 Phase 5 인계 → `WIP/handoff-state-detection-redesign.md`. **항목별 실측·어댑터 argv·강제 등급 동결은 Phase 5 판정기 이후로 이월**(재-시퀀싱). 측정 하네스에 `--workdir-base`(신뢰된 폴더 하위 측정) 보정 커밋
- [x] **§8.3b(11~13) Phase 3 인계** (`WIP/handoff-83b-container-measurement.md`) ✅ 2026-07-14
- [ ] **SoT PR 2건 (사용자 게이트)** — ① `rule-role-responsibilities`(역할→쓰기경로 단일 명세) 신설 + `rule-protected-paths` 개정(경로축/역할축 분리·상호참조 · **ADR 작성권 Leader→Maintainer 이동**, 사용자 결정): **작성·2모델 리뷰 수렴, ADR 변경 6파일+계약테스트 적용, 최신 main 재조정 완료**(role-responsibilities `scope` global→local(ADR-0015)·protected-paths는 main SoT 프레임워크 위에 얹음, 병합 `33ea79b`, 646 테스트 통과). **PR #10을 사용자 게이트로 확정**(별도 `sot/` 브랜치 안 씀 — 재조정 후 SoT 변경이 #10에 정합) → **#10 병합 완료**(병합 `452dea8`, SoT 변경 main 반영, 2026-07-16). ② `rule-prompt-injection`(주입 규약)은 메시지 계약(§4.1 message)만 골격 확정, 게이트 배선은 Phase 5
- [ ] **Watcher 설계 (별도 브레인스토밍)** — 설계 초안 작성: `WIP/specs/2026-07-15-phase2-watcher-design.md` (확정=하한선·최소 tick / 제안=후보 흐름·설계 결정, 사용자 검토 대상 / 이월=라이브 파싱·게이트 배선 Phase 5). 2모델 리뷰 수렴 (2026-07-15). Codex에 대응 명령 없을 때 Maintainer가 오래 사는 방법 등 미해결 질문은 §4·§5. 본체 구현은 후속.
- [x] **역할 5종 정의 (RoleSpec + 시스템 프롬프트)** — `WIP/axdt/roles/spec.py`(kind·capability·enforcement·writable_paths·rule_refs) + `prompts/{maintainer,leader,developer,reviewer,tester}.md`(각자 rule_refs만 인용) + 계약 검사 `tests/test_spec.py`(role-responsibilities 표 ↔ spec.py 등가·프롬프트 rule 태그 ⊆ rule_refs). Watcher는 RoleSpec 밖(§2.4). 2모델 리뷰 수렴·33 passed ✅ 2026-07-15
- [x] **주입 규약 골격** — `WIP/axdt/protocol/{message,inject,converge}.py`: message(토큰·단일행 불변식 \n·\t·\r·POSIX 경로 렌더)는 실동, inject/converge는 스켈레톤(NotImplementedError — poll_state·observe·report 승격은 Phase 4/5 의존). 2모델 리뷰 수렴 ✅ 2026-07-15

**본체 구현** (설계는 위 스펙에서 수렴, **역할 책임·프롬프트·주입 메시지 계약은 위 [x] 항목에서 초안 확정**, 아래는 런타임 배선 구현 대기):

- [ ] **Maintainer** — 상시 장기 tmux 세션. 전체 진척도 관리, Leader 생성·배치, Tmux 관리, progress 단독 작성 (Skill)
- [ ] **Watcher** — Cron 주기 호출. Maintainer **context 관리(압축/정리)** 전담
- [ ] **Leader** — 기능 단위 개발, workspace 종속, report 작성(자기보고 상태 포함) (Skill)
- [ ] **Developer** — 책임 범위 정의 (Leader가 workspace 내부에서 직접 호출)
- [ ] **Reviewer** — 책임 범위 정의 (코드 리뷰 + 사용자 게이트 연동)
- [ ] **Tester** — 책임 범위 정의 (유닛/통합 테스트 담당)
- [ ] **통신 프로토콜 정의** (D2 반영)
  - [ ] **report 파일** 포맷·위치·라이프사이클 (`report.status` 포함)
  - [ ] Maintainer → Leader **tmux send-keys** 주입 규약 — 메시지 렌더·토큰 계약은 `protocol/message.py` 골격 확정, IDLE 게이트 배선은 Phase 5(`inject.py`)
  - [ ] Leader의 Dev/Reviewer/Tester 호출·산출물 중계 규칙 (sub-agent 간 직접 통신 없음, Leader가 허브)
  - [ ] Leader 간 의존성 → Maintainer 경유 조율 규칙

## Phase 3 — 격리 & 인프라 (Isolation / Infra)

> glue 스크립트 = **Python** (D9)

- [ ] Workspace 생성/삭제 자동화 스크립트
- [ ] **Docker 격리** — **workspace당 컨테이너 1개**, 해당 workspace만 마운트 (D3)
  - [ ] `git worktree`의 `.git` 공유 문제 해결 (독립 `.git` 또는 remote push 방식)
- [ ] Leader를 Docker로 배치하는 자동화
- [ ] **Tmux 오케스트레이션** — Maintainer가 다수 Leader 세션 관리 + send-keys 주입
- [ ] **Cron 설정** — Watcher 주기 호출 (context 관리)
- [ ] **규칙 강제(guardrails)** — 호스트/허브 층 (D15, `ADR-0007`; 명세 `rule-protected-paths`)
  - [ ] 런치 가드 — 격리 러너/entrypoint를 허브 쓰기 자격의 **유일 경로**로 (Maintainer 호스트 예외)
  - [ ] 로컬 pre-commit 훅(권고) — 네이밍·보호 경로 위반 즉시 경고
  - [ ] 허브 서버사이드 게이트(강제) — push 시 보호 경로 diff·네이밍·SoT 위반 거부, 정책·검사코드는 **신뢰 ref**에서 읽음. **경로·ref 기반은 무인증 baseline, 주체 인증(ref 위장 방지)은 하드닝 연기**
    - [ ] 표↔블록↔코드 적합성 테스트 — `protected-paths.md`의 기계용 블록(`axdt-protected-paths`)과 `hubgate` 파서·매처가 일치하는지 결속. 현재 코드는 자체 픽스처로만 검증, 실제 정본 미결속 — 정본이 `main`에 착지한 뒤 결속.

## Phase 4 — 진척 추적 모델 (Progress / Report)

> 별도 DB 없음. interim 파일 기반.

- [ ] **progress 파일** 설계 — **엄격 스키마 MD 테이블** (D7)
  - [ ] 스키마: 고정 5컬럼(`wave`·`task`·`status`·`leader`·`updated`) + 통제된 status 어휘 (report 포인터 컬럼 없음 — canonical 경로로 판정)
  - [ ] **단일 작성자 = Maintainer** 규칙 명문화
- [ ] **report → progress 승격 흐름** 구현 (Maintainer가 report 읽고 수용 후 progress 갱신)
- [ ] 크래시/컨텍스트 압축 후 **progress·report로부터 상태 복원** 절차
- [ ] progress **마일스톤 커밋** 정책 적용 (D10)

## Phase 5 — 멀티 플랫폼 Agent 지원

> D4: 공통 인터페이스 + **두 어댑터 모두 구현**

- [ ] 공통 **agent runner 인터페이스** 정의 (세션 기동/prompt 주입/출력 읽기)
- [ ] `.claude/` 구성 + Claude Code 어댑터 (skills, settings, hooks)
- [ ] `.codex/` 구성 + Codex 어댑터 (동등 기능)
- [ ] 플랫폼별 동작 차이 검증 매트릭스
- [ ] **상태판정 재설계 — 훅 기반** (§8.3a 발견 인계): `detect_state`/`poll_state`를 화면 긁기에서 훅이 쓴 상태파일 읽기로. 화면 마커 폐기·`PLATFORM_MATRIX` 마커 행 재정의. claude·codex 훅(SessionStart/UserPromptSubmit/Stop)→상태. 근거·실측 → `WIP/handoff-state-detection-redesign.md`

## Phase 6 — Git 호스트 연동 & SoT 완료 강제

### 6-A. Git 호스트 연동
- [ ] **GitHub 1차 완성** (D5, `gh` CLI)
- [ ] **사용자 게이트** — 회색지대 결정 시 사용자를 Reviewer로 한 PR 생성 후 일시정지/재개
- [ ] 호스트 추상화 레이어 (PR 생성/리뷰/머지 공통 인터페이스) — `ADR-0010`((b) 클라이언트)
- [ ] **`ADR-0009` 착지 후 참조 정리**(이번 main 병합으로 트리거 충족) — `docs/sot/rule/protected-paths.md`(forward 참조·`related`에 0009 추가)·`sot-readiness.md`(결정 8을 RS-C=`sot/*` 보호 요구로 반영)·phase6 핸드오프·사양서의 "main 미착지/PR #13" 낡은 문구를 확정 참조로. `docs/sot/**`는 사용자 게이트 PR.
- [ ] GitLab 어댑터
- [ ] Forgejo 어댑터

### 6-B. SoT 완료 강제 (머지 컨트롤러)

> SoT 문서가 '완료'로 인정받는 세 조건 — ① 정해진 형식을 갖췄고, ② 검토에서 막는 지적이 없고, ③ 사용자가 승인함 — 을 **모두 만족할 때만 main 브랜치에 병합되도록 실제로 강제**하는 장치. main을 바꿀 수 있는 유일한 주체를 '자동 병합 관리자'로 두고, 병합 직전에 세 조건을 계산해 전부 통과할 때만 병합한다(사람이 미완성 문서를 실수로·우회로 병합하지 못하게). 근거: `ADR-0009` · 사양서 `WIP/specs/2026-07-08-phase6-enforcement-host-branch-protection-design.md` · 규칙 `sot-readiness`.

- [x] **설계 확정** — 설계서 3종(사양서 · `ADR-0009` · 완료 판정 규칙 `sot-readiness`) 작성·동결. 규칙 정본 2키 모델(판정 키 4성분 + 완전성 스윕 키) 정합으로 사양서 §2.2~§3 재개정·재동결(`34cadcf`, Codex+Fable 2R 수렴)
- [x] **판정 로직 구현 (GitHub 접속 없이 계산되는 핵심부)** — "이 PR을 병합해도 되는가"를 입력값만으로 초록/빨강 판정하는 핵심 함수 + 검토 지적을 서로 같은 것으로 대조하는 '지문(해시)' 계산 함수 (`WIP/axdt/sot_gate/`) — 순수 코어 구현·2키 재작업 완료(keys/models/gate + 테스트 124, `34cadcf`) ✅ 2026-07-17
- [ ] **GitHub 연결·실행부 구현** — GitHub에서 PR·코멘트·승인 읽는 연결부 · 초록일 때만 병합하는 자동 병합 관리자 · 문서 자동 검토 CI 작업 · 바뀐 파일 경로를 보호 규칙과 맞추는 경로 패턴 매칭 (실제 GitHub 검증 전 가정 → 실동작 확정)
- [ ] **켜기 전 준비조건** — 게이트 코드 자신도 보호 경로 목록에 등록 · 승인 권한자 명단 확정 · (자기 PR 자기 승인 방지) 검토자 둘 이상 구성 전환 (근거 문서 `ADR-0009` main 착지 완료 — 2026-07-18 PR #13)

## Phase 7 — 사용자 인터페이스 & 알림 (Web / Messenger)

> Web·브릿지 = **Python** (D9)

- [ ] **Local Web Server 브리핑** — interim 파일 **read-only** 렌더링 (Python)
  - [ ] 개요: progress 파일 1개 읽기
  - [ ] 드릴다운: 클릭 시 해당 report 파일만 읽기
- [ ] **메신저 연동** (양방향)
  - [ ] outbound: Maintainer가 결정 지점에서 직접 알림 발송 (큐 없음)
  - [ ] inbound: webhook 브릿지 → tmux send-keys → Maintainer (stateless)
  - [ ] **Discord 1차 완성** (D8)
  - [ ] 메신저 추상화 레이어
  - [ ] Slack 어댑터
  - [ ] Lark 어댑터

## Phase 8 — 오케스트레이션 / 자동화 엔진

- [ ] 핵심 루프: 문서 완료 → 자동 개발 착수 — **세 트리거 지원** (SoT PR merge / 명시 명령 / 마커 파일, D6)
- [ ] Maintainer 주도 진척도 관리 (Phase 4 progress 활용)
- [ ] Wave/Task 분해 → Leader 배정 로직
- [ ] 일시정지/재개 메커니즘 (사용자 결정 지점, 게이트·메신저 연동)
- [ ] 실패/재시도/에스컬레이션 처리

## Phase 9 — 검증 & 문서화

- [ ] 핵심 스크립트/Skill 유닛 테스트
- [ ] 전체 워크플로 통합 테스트 (문서→개발→PR→브리핑→알림 1사이클)
- [ ] **도그푸딩**: 예제 미니 프로젝트로 템플릿 실제 구동
- [ ] 최종 사용자 가이드 (템플릿 사용법, 셋업, 트러블슈팅)
- [ ] 아키텍처 다이어그램 / 역할 상호작용도 + 통신 채널 맵

---

## 의존 관계 요약

```
Phase 0 ─> Phase 1 ─> Phase 2 ─┐
                                ├─> Phase 8 ─> Phase 9
Phase 3 ─> Phase 4 ─> Phase 7 ─┤
Phase 5 ─> Phase 6 ────────────┘
```

- Phase 0(기반)은 모든 작업의 선행.
- Phase 4(진척 모델)는 Phase 7(Web·메신저)의 선행 — 브리핑이 progress·report에 의존.
- Phase 8(엔진)은 2·4·6·7이 어느 정도 갖춰져야 통합 가능.
- Phase 9(검증)는 마지막이지만, 각 Phase 종료 시 부분 검증 권장.

---

## 🗂️ 백로그 (Backlog)

> Phase 계획에 아직 박히지 않은, 진행 중 떠오른 작업. 우선순위를 표기하고 착수 시점에 적절한 Phase로 편입한다.

- [ ] **[높음] 용어집(glossary) 작성** — AXDT 설계 전반의 용어를 한곳에 정의. 지금은 SoT/Interim 정도만 `terminology.md`·본 TODO에 흩어져 있고, Maintainer·Leader·게이트·readiness·finding(`F-n`)·`review_clear`/`accepted`/`rejected`·트리 해시 등 논의에서 쓰는 용어의 단일 사전이 없어 혼동이 잦다. 위치·형식 미정(`docs/sot/rule/` 편입 vs 별도 glossary 파일).
- [ ] **[높음] 문서 워크플로 도식화** — SoT·interim 각 문서의 생애와 문서 간 관계를 사람이 한 눈에 이해할 도식으로. 지금은 통신 채널 맵·상태 모델(report→progress)·디렉터리 구조·강제 계층이 TODO·`protected-paths`·`ADR-0004` 등에 흩어져 있고, "작성 → 검토(②) → 사용자 게이트(①②③) → 완료 → 개발 트리거"로 이어지는 문서 전체 흐름을 한 장으로 보는 통합 자료가 없다.
- [ ] **[조건부] `WIP/**` 보호 재구성** — 대상 프로젝트가 AXDT가 아닌 것으로 전환(도그푸딩 종료)되면, `protected-paths.md` 기계용 블록의 `WIP/**` 제외(각주 ‡)를 재검토(`deny WIP/**` 여부)해 사용자 게이트 PR로 선행한다. 그 전까지 (b) 게이트를 새 대상에 적용하지 않는다.
- [ ] **[중간] WIP 문서 구조 `README.md` 정리** — WIP 상위 디렉터리 분류(`specs/`=확정 설계, `plans/`=빌드 플랜, `drafts/`=초안, `reviews/`=review-report 스킬 세션, `adr/`=결정, `handoff-*.md`=측정·인계 워킹 노트, `axdt/`=코드+매트릭스)와 측정 결과 로그의 지정 위치가 한곳에 문서화돼 있지 않다(README 부재 확인). 이 분류를 `WIP/README.md`로 정리해 배치 혼동을 없앤다. (계기: seed+copy 측정 로그를 review-report 세션 폴더에 잘못 놓았다가 루트로 이동.)
- [x] **[중간] phase1 승격 초안 정리** — `adr-recording-rule-draft.md`(정식 `docs/sot/rule/adr-recording.md`로 승격돼 중복)·`b1-authoring-skill-draft.md`(SKILL.md 구현·동결 완료 `55472ab`, R3 리뷰 major 없음) 삭제. ✅ 2026-07-13
