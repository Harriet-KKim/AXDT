# 호스트별 provisional 검증 매트릭스 (Phase 6)

> 범위: `git_host` 어댑터의 호스트 간 차이. GitHub는 설치된 `gh` 공식 문서 대조로 **확정**(Phase 6 (b)).
> GitLab(`glab`)·Forgejo(`tea`)는 구조만 선언한 **provisional** — 라이브 호스트 E2E는 Phase 9.

| 항목 | GitHub | GitLab | Forgejo | 비고 |
|---|---|---|---|---|
| create 서브커맨드/플래그 | 확정 — `gh pr create --head H --base B --title T --body BODY`, stdout은 PR URL 한 줄(JSON 없음) | provisional — `glab mr create --source-branch H --target-branch B --title T --description BODY` | provisional — `tea pulls create --head H --base B --title T --description BODY` | 세 호스트 모두 create는 JSON을 내지 않는다(§2.7, create→view 합성). |
| view/get 서브커맨드 + JSON 필드명 | 확정 — `gh pr view REF --json number,url,state,reviews,reviewRequests` | provisional — `glab mr view N -F json`; 필드명 `number`→`iid`, `url`→`web_url` | provisional — `tea pulls N --output json` | `number/iid`, `url/web_url`, `state`, `reviews`, `reviewRequests` 대응 필드명은 라이브 검증 전까지 미확정. |
| view ref 수용 형태 | 확정 — 번호·URL·branch 모두 수용 | provisional — 번호만 수용(URL 미수용 → 호출 전 URL에서 번호를 파싱해야 함) | provisional — 번호 | GitHub 외에는 ref 형태가 좁을 수 있다. |
| request-review 플래그 의미 | 확정 — `gh pr edit N --add-reviewer R`(추가). 팀 리뷰어 조회는 `read:org` 스코프가 필요할 수 있음 | provisional — `glab mr update N --reviewer +R`. **주의: `+R`은 추가, bare `R`은 교체** | provisional — `tea pulls edit N --add-reviewers R` | GitLab은 `+` 접두를 빠뜨리면 재요청이 아니라 리뷰어 교체가 된다. |
| merge 방식 플래그 | 확정 — `gh pr merge N --squash\|--merge\|--rebase` | provisional — `glab mr merge N --merge\|--squash\|--rebase`(정확한 플래그명 미검증) | provisional — `tea pulls merge N --style=merge\|squash\|rebase` | 세 값 모두 `MergeMethod` 통제 어휘로 고정되어 있고, 호스트별 플래그 문자열만 다르다. SoT 관문 PR은 감사 이력 보존을 위해 `SQUASH`가 아니라 `MergeMethod.MERGE`로 머지한다(§9). |
| 리뷰 모델 + 상태 맵 | 확정 — `reviews[].state` = APPROVED/CHANGES_REQUESTED/COMMENTED(전체 이력; 순서·페이지네이션은 라이브 미검증) | provisional — GitLab은 승인(approvals) 모델이라 GitHub식 리뷰 스트림과 형태가 다르다. 현재 `_REVIEW_STATE_MAP`은 비어 있어 base가 모든 값을 COMMENTED(비종결)로 처리 | provisional — 리뷰 상태 값 미검증, 현재 `_REVIEW_STATE_MAP`도 비어 있음 | `reviews` 페이지네이션·정렬 순서, 커서 `id`가 리뷰 dismiss로 스트림에서 사라졌을 때의 동작(base `terminal_after`는 커서를 못 찾으면 `None`을 반환해 대기를 유지)도 세 호스트 공통으로 provisional. |
| 게이트 배포 전제 (합의 F/G) | 호스트 검증 필요 | 호스트 검증 필요 | 호스트 검증 필요 | **게이트 리뷰어 ≠ PR 작성자**가 전제다(봇/머신 계정이 PR을 열고, 사람이 게이트 리뷰어). self-request/self-review 시 호스트가 어떻게 반응하는지(거부/무시/허용)는 호스트별로 라이브 검증한다. |

## 검증 방식
- 확정 항목: `axdt/git_host/tests/test_adapters.py`가 `gh` 공식 문서 대조로 argv/파싱을 고정한다.
- provisional 항목: Phase 9에서 실제 GitLab/Forgejo 호스트로 argv·JSON 스키마·값 맵을 검증하고 이 표를 갱신한다.

## 범위 밖
호스트 브랜치 보호(required check, 승인+dismiss-stale, `main` require-PR 등) 같은 **강제(guardrail)** 는 이 클라이언트 증분의 범위 밖이며 별도 증분으로 `ADR-0009`가 추적한다.
