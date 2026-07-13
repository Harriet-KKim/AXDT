# 핸드오프 — review-report 스킬 (compact 경계)

> compact 이후(또는 새 세션에서) 이 파일 하나로 이어간다. 디스크의 설계·계획 파일과 git 이력이 진실원이고, 이 문서는 그 지도다.

## 무엇
AXDT 프로젝트에서 **"검토/보고용 HTML 스킬 review-report"** 를 설계·구현 중.
검토 문서를 자체완결 HTML로 Artifact 게시 → 사용자가 페이지에서 의견 주입 → 회수 → 같은 URL에 라운드를 올려 반영하는 반복 루프. 스킬 본체는 개인 스킬(`~/.claude/skills/review-report/`, 자체 git repo), 데이터는 `<프로젝트>/WIP/reviews/`.

## 작업 위치 (절대경로)
- worktree: `C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill`
- 브랜치: `worktree-review-report-skill`. 모든 명령은 이 worktree에서.

## 산출 파일
- 설계(R2, 확정 대기): `WIP/specs/2026-07-13-review-report-skill-design.md` (최신 커밋 `94b92d4`)
- 계획(R1, 낡음 — 재작성 필요): `WIP/plans/2026-07-13-review-report-skill.md`

## 진행 상태
브레인스토밍 → 설계 → 계획(R1) 작성 완료 → Codex(gpt-5.6-sol)+Fable 다중 리뷰에서 **둘 다 "착수 불가"**(blocking 다수) → 설계를 **R2로 개정·커밋 완료**. 계획은 아직 R1이라 R2와 불일치.

## R2에서 바뀐 핵심 설계 결정
1. 의견 왕복 **JSON 단일화**(텍스트 형식 폐기)
2. **앵커당 다중 의견**(localStorage·클립보드·comments.json 동형 items 배열)
3. **용어 풀이 실노출**(hover/focus 툴팁+title, 수동용어도 용어표) + 단어경계 + 수동 b-term 소진
4. **마크업 안전**(body를 엄격 fragment로 제한, 앵커수집·카드주입은 파서 스택, placeholder는 알려진 토큰 1회 치환)
5. **context.html 신뢰입력** + 최종산출물 외부리소스 차단
6. 메타/comments 타입·스키마 검증, **utf-8-sig**, ASCII 안전 로그
7. 메모리 `html-deliverable-house-style` 삭제는 **2라운드 검증+백업 후로 지연**
8. Artifact 계약(favicon 필수·title·같은경로=같은URL·버전)은 **구현 전 Task 0로 실측**

## 실증된 blocking (코드로 확인)
수동 b-term 뒤 동일 용어 재감쌈 / SoTware 안 SoT 부분어 오탐 / 텍스트 클립보드 왕복에서 `###` 줄 소실 / Windows 콘솔 cp949에서 유니코드 로그 크래시.

## 리뷰 원문
- Codex: `$CLAUDE_JOB_DIR/tmp/codex-review2.txt` 끝부분 (job 삭제되면 사라짐 — 요지는 위 R2 결정에 이미 흡수됨).
- Fable: 대화 내 task 결과(요지도 위에 흡수됨).

## 다음 단계 (이 순서로)
1. **(선택) 사용자 설계 R2 확인.** 이미 대기 걸어둔 상태 — 사용자가 넘어가라면 바로 2로.
2. **R2 설계에 맞춰 계획 전면 재작성(직접 수행 권장 — 판단 밀도 높음).** R1 대비 반드시 반영:
   - 의견 왕복을 JSON 단일 계약(serialize/parse 텍스트 → `json.loads`/`JSON.stringify`).
   - 의견 데이터 모델 앵커당 다중(items 배열), UI 추가/삭제.
   - 용어 감싸기 단어 경계(ASCII는 영숫자·`_` 경계, CJK는 경계없음) + 수동 b-term 소진 등록. b-term hover/focus 툴팁+title, 자동·수동 모두 용어표.
   - body 엄격 fragment 검증(앵커 정규식 `[A-Za-z0-9_-]+`·유일·data-title 필수·id금지·중첩/DOCTYPE 거부). 앵커수집·카드주입 HTMLParser 스택. placeholder 알려진 토큰 1회 치환.
   - context.html 신뢰입력 렌더 + 최종 out.html 외부리소스 검사.
   - 메타/comments 타입·스키마 검증, utf-8-sig 입력, ASCII 안전 로그.
   - `ingest` 하위명령(붙여넣은 JSON→comments.json 병합, slug/round 대조).
   - 클립보드 writeText `.catch()`+readonly textarea 폴백.
   - **Task 0: 구현 전 Artifact 실측**(favicon·title·같은URL 재게시·버전).
   - 스킬 빌드 명령은 스킬 절대경로, 데이터 경로는 인자.
   - 스모크 Step 순서 수정, 2라운드 수동 acceptance test 추가.
   - 메모리 삭제 / v1.0 태깅은 2라운드 검증+백업 커밋 후로.
   - TDD(unittest), 각 태스크 스킬 repo 커밋.
3. **재작성 계획을 Codex+Fable 재리뷰.** codex는 문서를 **stdin 인라인 + `--sandbox read-only`** 로 호출(파일 도구 handshake 실패 회피 — 메모리 `codex-exec-inline-files-on-handshake-fail`).
4. 재리뷰 통과 수준이면 사용자 보고 후 **subagent-driven**으로 착수.

## 제약 (항상)
py -3만(python stub 깨짐) · 표준 라이브러리만 · 개인 스킬은 자체 git repo · worktree에서 작업 · AXDT엔 데이터 스캐폴딩만 커밋 · 계획 커밋 전 재리뷰(re-review after fix) 준수.
