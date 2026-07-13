# 핸드오프 — review-report 스킬 (compact 경계)

> compact 이후(또는 새 세션에서) 이 파일 하나로 이어간다. 디스크의 설계·계획 파일과 git 이력이 진실원이고, 이 문서는 그 지도다.

## 무엇
AXDT 프로젝트에서 **"검토/보고용 HTML 스킬 review-report"** 를 설계·구현 중.
검토 문서를 자체완결 HTML로 Artifact 게시 → 사용자가 페이지에서 의견 주입 → 회수 → 같은 URL에 라운드를 올려 반영하는 반복 루프. 스킬 본체는 개인 스킬(`~/.claude/skills/review-report/`, 자체 git repo), 데이터는 `<프로젝트>/WIP/reviews/`.

## 작업 위치 (절대경로)
- worktree: `C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill`
- 브랜치: `worktree-review-report-skill`. 모든 명령은 이 worktree에서.
- 스킬 생성 위치: `C:/Users/Harriet/.claude/skills/review-report/` (자체 git repo, AXDT 리포 밖)

## 산출 파일
- 설계 R2: `WIP/specs/2026-07-13-review-report-skill-design.md` (확정 대기)
- 계획 R2(재리뷰 반영본): `WIP/plans/2026-07-13-review-report-skill.md` — 12태스크 TDD. 최신 커밋 `4ecfe1a`.

## 진행 상태 (현재: 착수 단계)
브레인스토밍 → 설계 → 계획 R1 → **1차 리뷰(Codex+Fable) 착수불가** → 설계 R2 개정 → 계획 R2 재작성(Sonnet 위임) → 내 검수로 Task3 실행버그(isascii) 발견·수정 → **2차 재리뷰(Codex+Fable)**: R1 blocking 10개 전부 해소 확인, 코드·101테스트 trace상 실제 통과 확인. Fable "조건부 가능", Codex "착수 불가". → **합의 blocking 2건 + 실결함 3건을 반영 완료·커밋(`4ecfe1a`)**. 사용자가 "핵심 결함 반영 후 착수"(선택 A) 승인. **이제 착수 단계.**

## 재리뷰에서 반영 완료한 것
- (코드 반영·실증) glossary 표 파싱 2열만 채택(terminology.md 4열 오파싱 차단) / ingest merge_comments replace(재회수 중복 제거) / render_shell leftover 검사 제거(삽입 본문 리터럴 `{{TOKEN}}` 오탐)
- (설계·config) `glossary_sources` 빈 배열(terminology.md는 규칙문서라 부적합; 373 진짜 용어집 생기면 추가; 그 전까지 수동 `<b-term>`만 실효)

## 착수 시 반영할 것 (계획에 지시 노트로 박아둠 — TDD로 구현)
- **Task 6**: `render_comment_cards`/`inject_comment_cards`/`_CardInjector`에 `max_round` 추가, `round < meta.round`만 렌더(이전 라운드만). 통합/카드 테스트 `meta.round=2`·comment `round=1`로 조정.
- **Task 8**: shell.html `<script>`가 세션·슬러그·라운드를 JS 리터럴로 직접 주입 금지. 루트 요소 `data-*` 속성 + `dataset` 읽기(HTML escape로 안전, 개행/`&` 안전).
- **Codex 엣지 지적(YAGNI/해당 태스크에서 판단)**: self-closing `<section/>` 거부, escaped pipe `\|`, Python 3.10+ 명시(`write_text(newline=)`), 중첩 `<b-term>` 금지, 인라인 script 검사 문구를 "원격 리소스"로 좁힘, Artifact `url=` 교차대화는 Task 0 실측 때 확인, favicon 값 고정(🔎).

## 다음 단계 (착수)
**superpowers:subagent-driven-development로 태스크별 구현.** Task 0(Artifact 계약 실측)은 내가 직접 도구로(최소 페이지 게시→같은 file_path 재게시→URL 동일·버전·favicon 필수·title 확인). Task 1~11은 Sonnet 서브에이전트 + 태스크 사이 내 검수.

**철칙(재리뷰 교훈)**: 계획의 "Expected: PASS (N tests)"를 믿지 말고 **각 태스크에서 실제로 `py -3 -m unittest test_build -v`를 돌려** 통과를 눈으로 확인한다(서브에이전트가 R1·R2에서 안 돌리고 "통과"라 적어 실버그가 숨었다 — Task3 isascii). 각 태스크 끝 스킬 repo 커밋. 계획 커밋 전 재리뷰(re-review after fix) 준수.

## 제약 (항상)
py -3만(python stub 깨짐) · 표준 라이브러리만 · 개인 스킬 자체 git repo · worktree에서 작업 · AXDT엔 데이터 스캐폴딩만 커밋 · 메모리 `html-deliverable-house-style` 삭제/v1.0 태깅은 2라운드 acceptance+백업+승인 후로 지연.
