# 핸드오프 — review-report 스킬

> 새 세션은 이 파일 하나로 이어간다. 여기엔 **다른 곳에 없는 것만** 적는다:
> 스킬 사용법은 `~/.claude/skills/review-report/SKILL.md`, Artifact 도구 거동은 같은 폴더의 `ARTIFACT-CONTRACT.md`,
> 설계·계획은 `WIP/specs/2026-07-13-review-report-skill-design.md`·`WIP/plans/2026-07-13-review-report-skill.md`,
> 도구 사용 규칙(py -3 / codex 호출법 / "테스트 통과" 주장 대신 실행 실증)은 메모리에 있다 — 여기서 되풀이하지 않는다.

## 무엇
검토 문서를 자체완결 HTML로 Artifact 게시 → 사용자가 페이지에서 섹션별 의견 주입 → 회수 → 같은 URL에 라운드를 올려 반영하는 반복 루프.

## 어디에 있나
- **스킬 본체**: `C:/Users/Harriet/.claude/skills/review-report/` — 개인 스킬, **자체 git repo(원격 없음)**, 19커밋, 태그 `v1.0`. AXDT 리포에 스킬 코드는 없다.
- **AXDT 쪽**: worktree `.claude/worktrees/review-report-skill`, 브랜치 `worktree-review-report-skill`, 초안 **PR #12**. 담긴 것은 설계·계획·이 핸드오프·`WIP/reviews/` 데이터 스캐폴딩·`.gitignore`뿐.

## 상태: 구현 완료
134개 테스트 통과. 2라운드 acceptance 통과. **실사용자가 실제 아티팩트에 남긴 의견을 postMessage로 회수 → `ingest` → 처리결과 기입 → 같은 URL 재게시**까지 종단 검증됨. 집 스타일의 진실원이 메모리에서 `shell.html`로 이전됐다(구 메모리는 스킬 repo에 `ARCHIVE-html-deliverable-house-style.md`로 백업 후 삭제).

## 계획에서 벗어난 결정 3건 (근거)
1. **중첩 `<section>` 금지** — 계획은 허용했고 테스트까지 있었다. 그런데 shell의 JS가 후손 선택자라 중첩 section에도 의견함을 만들어 주는 반면 카드 주입은 최상위에서만 일어나, **거기 단 의견이 저장·회수까지 되고도 영영 안 보였다**(데이터 유실). 번호·앵커·카드 어디에도 안 쓰이면서 함정만 만들어 금지로 뒤집었다. 하위 구조는 `<div>`.
2. **계획의 낡은 테스트를 뒤집음** — R2에서 `render_shell`의 미치환 토큰 검사를 의도적으로 제거했는데(안 그러면 이 스킬로 이 스킬의 템플릿 문서를 리뷰할 때 본문의 `{{TOKEN}}` 예시를 미치환으로 오판해 빌드가 실패한다), 그 검사가 raise하는지 보는 옛 테스트가 남아 모순이었다. 구현이 옳고 테스트가 낡은 것으로 판단.
3. **의견 회수를 postMessage로 교체** — SKILL.md 초안은 "claude-in-chrome으로 아티팩트의 localStorage를 JS로 직접 읽어 회수"라고 적었으나 **불가능하다**(cross-origin이라 밖에서 안을 못 읽는다). 대신 안→밖 `parent.postMessage()`는 CSP에 막히지 않아 그걸 쓴다. 클립보드는 폴백(폰·확장 미연결). 상세는 `ARTIFACT-CONTRACT.md`.

## 정적 리뷰가 전부 놓치고 실행에서만 잡힌 결함들 (손볼 때 재발 주의)
- `ingest` 성공 메시지의 em-dash가 cp949 콘솔에서 `UnicodeEncodeError` — 데이터는 기록됐는데 명령이 traceback으로 끝나 실패로 오인됐다. 이후 stdout/stderr를 `backslashreplace`로 재설정해 데이터 출력(용어·앵커 이름)까지 안전하게 만들었다.
- 용어 감싸기 단어 경계에 `str.isalnum()`(유니코드 전체 True)을 써서 한글 조사 붙은 ASCII 용어(`SoT는`)가 전멸 → `_is_ascii_word`(= `c.isascii() and c.isalnum()`).
- 중첩 section 의견 유실(위 1).
- `ingest`가 빈 클립보드로 그 라운드 의견을 통째로 삭제 — localStorage는 브라우저별이라 다른 기기·시크릿창에서 복사하면 빈 목록이 온다. 이제 거부하고 `--force`로만 비운다.
- 자체완결 검사가 평범한 외부 링크(`<a href>`)까지 차단 — CSP가 막는 건 리소스 로드지 링크 이동이 아니다. `src`·`<link href>`·CSS `url()`만 위반으로 본다.

## 알려진 한계 (지금은 실사용 영향 없음)
`parse_glossary`가 이 프로젝트의 실제 문서를 잘 못 읽는다: `docs/sot/rule/terminology.md`는 규칙 템플릿의 필드명(`- **대상**: …`)을 용어로 오파싱하고, `docs/glossary.md`는 용어명이 `SoT (Source of Truth, 권위본)` 꼴이라 `SoT`가 자동 감싸기에 안 걸린다. 지금은 `WIP/reviews/config.json`의 `glossary_sources`가 **빈 배열**이라 자동 감싸기가 없고 수동 `<b-term>`이 실효 경로다. 진짜 용어집을 붙이려면 그 형식(`- **용어** — 풀이` 또는 2열 표)을 맞추거나 파서를 손봐야 한다.

## 다음 단계: 다중 모델 리뷰 (사용자 요청)
브랜치 작업 **전체**를 Codex-Sol + Fable에게 리뷰받는다. 대상은 **두 곳**이다 — 스킬 repo(코드·문서)와 AXDT 브랜치(설계·계획·스캐폴딩).

두 리뷰어에게 명시 질문으로 물을 것:
- 실사용에서 깨질 정확성 결함이 남아 있나 — 파서 스택, 용어 경계, JSON 왕복, 원자적 쓰기, 인코딩.
- **postMessage 회수 경로가 옳은 수단인가**, 더 나은 길이 있나.
- 위 "계획에서 벗어난 결정 3건"이 타당한가.
- 사용자 의견 텍스트가 페이지에 렌더되는데 escape 구멍이 있나.
- 이 스킬을 처음 쓰는 에이전트가 `SKILL.md`만 읽고 라운드를 돌릴 수 있나(문서 공백).

리뷰어에게 요구할 것: 추측성 지적 금지 — 재현 코드와 실제 출력으로 증명하거나, 확인 못 했으면 그렇게 명시. 심각도(Blocking/Important/Minor)로 구분.
다시 볼 필요 없는 것(이미 실증됨): 134개 테스트 통과, 2라운드 acceptance, 실사용자 입력 postMessage 종단 검증.

## 제약
표준 라이브러리만 · 콘솔 출력은 cp949 인코딩 가능해야 함(한글 OK, em-dash·`⚠` 금지) · `shell.html`은 자체완결(외부 **리소스 로드** 금지, 외부 **링크**는 허용) · 마크업 처리는 정규식이 아니라 `HTMLParser` 깊이 스택 · 의견 카드는 이전 라운드만(`round < meta.round`).
