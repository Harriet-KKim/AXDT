"""GitHubGatePorts — GateHostPorts의 GitHub 구현(§3, §8). 5포트(읽기 4 + 머지 + 룰셋 점검
중 아래 5개)를 `gh api`(CommandBackend 경유)로 구현한다. `compute_landing_keys`·
`read_ci_artifacts`는 이 증분 범위 밖이라 손대지 않았다(NotImplementedError 유지).

라이브 `gh api` 스키마는 Phase 9 도그푸딩 전까지 실증되지 않는다(§8) — 아래 구현은 GitHub REST
API 공개 문서 기준으로 작성했고, 결정적 단위 테스트(FakeCommandBackend)로 계약을 고정한다.
스키마가 실측과 어긋나면 Phase 9에서 이 파일만 고친다(포트 경계 밖으로 새지 않는다).

# gh api 호출 지점 (모두 CommandBackend.run 경유 — subprocess 직접 호출 없음)
- `read_pr_metadata`:
    GET repos/{o}/{r}/pulls/{number}                              — author·head·state
    GET repos/{o}/{r}/pulls/{number}/files (--paginate)            — 변경 경로(rename 포함)
    GET repos/{o}/{r}/contents/docs/sot/rule/protected-paths.md?ref=main
                                                                    — axdt-critical-paths 블록(신뢰 base)
- `read_channel_decisions`:
    GET repos/{o}/{r}/issues/{number}/comments (--paginate)        — PR 대화 코멘트(append-only)
    GET repos/{o}/{r}/collaborators/{login}/permission             — author_role(role_name)
    GET users/{login}                                              — author_is_human(type != "Bot")
- `read_approvals`:
    GET repos/{o}/{r}/pulls/{number}/reviews (--paginate)          — 리뷰 스트림
    GET repos/{o}/{r}/collaborators/{login}/permission             — approver_role
    GET users/{login}                                              — approver_is_human
- `merge_pull_request`:
    PUT repos/{o}/{r}/pulls/{number}/merge  (-f sha=... -f merge_method=merge)
- `verify_ruleset_config`:
    GET repos/{o}/{r}/rulesets (--paginate)                        — 룰셋 목록(id만)
    GET repos/{o}/{r}/rulesets/{id}                                — 룰셋 상세(rules·bypass_actors·conditions)

REST `pulls/{number}`의 `state`는 `gh pr view --json state`(GraphQL 백엔드, "OPEN"/"MERGED"/"CLOSED")
와 값 도메인이 다르다 — REST는 소문자 `"open"`/`"closed"` + 별도 `merged` 불리언이다. 이 파일은
REST를 직접 호출하므로 `git_host.adapters.github._STATE_MAP`(GraphQL 값)을 재사용하지 않고
`_map_pr_state`로 REST 값을 자체 매핑한다.

`gh api --paginate`는 배열 응답 엔드포인트에서 페이지마다 별개의 JSON 배열을 이어붙여 낸다(단일
배열로 병합하지 않는다 — gh CLI 공개 동작). `_json_list`는 stdout을 `raw_decode` 루프로 반복
파싱해 각 페이지 배열을 하나의 파이썬 리스트로 이어붙인다(페이지가 하나뿐이어도 그대로 동작).

# 결정 스탬프 형식 (axdt-decision) — read_channel_decisions가 파싱
PR 대화 코멘트 본문에 아래 펜스 블록이 있으면 그 코멘트를 결정으로 파싱한다. 블록이 없거나
아래 스키마를 어기면(빠진 필드·모르는 `key`·잘못된 `decision`·중복 블록) 그 코멘트는 결정이
아니다(조용히 skip — fail-closed 방향: 결정이 씹히면 open blocking이 미대조로 남아 RED가
되므로 안전하다). 블록 안은 `key: value` 줄만 허용하고(한 줄에 하나, 값은 공백 없는 단일
토큰), `#` 주석·중복 키는 지원하지 않는다(모호성 배제).

정합성(판정 키) 결정:
    ```axdt-decision
    key: judgment
    tree_hash: <값>
    rule_fingerprint: <값>
    review_policy_epoch: <값>
    rule_catalog_manifest_digest: <값>
    finding: F-<n>
    digest: <finding 내용 digest(hex, sha256 — normalize_finding_digest 산출)>
    decision: accepted|rejected
    ```

완전성(완전성 스윕 키) 결정:
    ```axdt-decision
    key: completeness
    projection_tree_hash: <값>
    active_catalog_input_digest: <값>
    review_policy_epoch: <값>
    finding: F-<n>
    digest: <finding 내용 digest>
    decision: accepted|rejected
    ```

`author`(comment.user.login)·`comment_id`(comment.id)·`created_at`/`updated_at`(comment 그대로 —
다르면 편집됨, §2.7 변조 원시 사실)·`deleted=False`(삭제된 코멘트는 스트림에 아예 나타나지
않는다)를 함께 채운다. `author_role`·`author_is_human`은 §2.7이 요구하는 원시 사실이며, 이
포트는 admin∧명단∧사람 판정을 접지 않는다(코어 `_authorized`가 계산).

# 승인 스탬프 형식 (axdt-approval) — read_approvals가 파싱 (§2.3 (ㄴ) 구조화 스탬프)
승인 리뷰(`state in {APPROVED, DISMISSED}`) 본문에 아래 펜스 블록으로 **두 키 모두**를 명시해야
그 승인이 유효하다 — 스탬프가 없거나 필드가 빠지면 그 승인은 배제한다(반환 튜플에 담지 않음,
재계산 금지 원칙 §2.3).

    ```axdt-approval
    judgment_tree_hash: <값>
    judgment_rule_fingerprint: <값>
    judgment_review_policy_epoch: <값>
    judgment_rule_catalog_manifest_digest: <값>
    completeness_projection_tree_hash: <값>
    completeness_active_catalog_input_digest: <값>
    completeness_review_policy_epoch: <값>
    ```

GitHub REST 리뷰 목록 엔드포인트(`pulls/{number}/reviews`)는 코멘트와 달리 `updated_at`(편집
시각)을 노출하지 않는다 — 리뷰 본문은 API로 편집 가능하지만 편집 흔적을 이 엔드포인트에서 볼
방법이 없다(확인 필요 — Phase 9 라이브 실증 전까지 provisional). 그래서 "제출 후 편집된 스탬프를
불신 처리"는 이 구현에서 **탐지하지 못한다**.
# TODO(Phase 9): 리뷰 본문 편집 탐지 방법(다른 엔드포인트·webhook 이벤트 등)을 실증해
#   승인 스탬프의 편집 후 불신 처리를 실제로 구현한다. 그때까지 스탬프는 항상 신뢰한다.

`dismissed`는 리뷰 `state`에서 직접 얻는다 — GitHub의 dismiss-stale이 리뷰를 철회하면 그 리뷰
객체의 `state`가 `"APPROVED"`에서 `"DISMISSED"`로 바뀐다(같은 리뷰 id, 값만 전이). 그래서 이
포트는 `state in {"APPROVED", "DISMISSED"}`인 리뷰를 모두 후보로 보고(둘 다 "한때 승인"의
흔적이므로) `dismissed = (state == "DISMISSED")`로 채운다 — `state == "APPROVED"`인 것만 걸러
버리면 철회된 승인은 그냥 사라져 `dismissed` 필드가 항상 False가 되어 버린다.

# touches_enforcement_surface glob 매칭 — 단일 소스 통합 TODO
`_glob_matches`/`_glob_to_regex`는 `docs/sot/rule/protected-paths.md`의 `axdt-critical-paths`
블록 헤더가 정의하는 glob 계약(`**` = 구분자 포함 0개 이상 세그먼트, `*` = 한 세그먼트 내 0개
이상 문자, trailing `**`는 디렉터리 자체+하위 전체)을 로컬로 구현한 것이다. Phase 3의
`hubgate.py::match_glob`(현재 미병합 브랜치 `phase3-followup`)가 **같은 계약**을 이미 구현하고
있으므로, 그 브랜치가 병합되면 두 구현을 하나의 공유 모듈로 단일화해야 한다(지금은 임시로
로컬 구현).
"""
import base64
import json
import re
from functools import lru_cache
from pathlib import Path

from axdt.git_host.backend import CommandBackend
from axdt.git_host.models import PullRequest, GitHostError
from axdt.git_host.state import PullRequestState

from axdt.sot_gate.keys import JudgmentKey, CompletenessSweepKey, FullBindingKey
from axdt.sot_gate.models import (
    ConsistencyArtifact,
    CompletenessArtifact,
    ChannelDecision,
    ApprovalEvent,
    FindingDecision,
    PRMetadata,
)
from axdt.sot_gate.ports import GateHostPorts, HeadMovedError


class CriticalPathsBlockError(RuntimeError):
    """`docs/sot/rule/protected-paths.md`(신뢰 base `main`)의 `axdt-critical-paths` 블록이
    없거나·중복이거나·미종결 펜스이거나·형식 위반 줄이 있거나·유효 `critical` 줄이 0개다.

    `touches_enforcement_surface`의 유일 입력(스펙 §2.6)이 비어 판정할 수 없는 상태이며,
    스펙 §7 (ㅁ)은 이를 pass-through(무관문 통과)로 흘리지 말고 fail-closed로 다루라고
    요구한다. 이 예외는 그 신호다 — 조용히 `False`를 반환하지 않는다. `evaluate_gate` 이전의
    사전 관문에서 이 예외를 잡아 RED로 접는 것은 컨트롤러 호스팅 증분(§8)의 몫이라 여기서는
    하지 않는다."""


# --- SoT 트리(target-content projection) 판정 ---------------------------------

_SOT_PROJECTION_DIRS = (
    "docs/sot/requirements/",
    "docs/sot/specification/",
    "docs/sot/test-design/",
)
_SOT_PROJECTION_EXCLUDED_BASENAMES = frozenset({"README.md", "_TEMPLATE.md"})


def _is_sot_projection_path(path: str) -> bool:
    if not any(path.startswith(d) for d in _SOT_PROJECTION_DIRS):
        return False
    basename = path.rsplit("/", 1)[-1]
    return basename not in _SOT_PROJECTION_EXCLUDED_BASENAMES


# --- glob 매칭 (axdt-critical-paths 블록 계약, Phase 3 hubgate.py::match_glob과 단일화 대상) ---

def _translate_glob_segment(segment: str) -> str:
    """세그먼트 하나(내부에 '/' 없음)를 정규식으로 번역한다. `*` = 그 세그먼트 안에서 0개
    이상의 문자('/' 불포함)."""
    return "".join("[^/]*" if ch == "*" else re.escape(ch) for ch in segment)


@lru_cache(maxsize=None)
def _glob_to_regex(glob_pattern: str) -> "re.Pattern":
    """critical glob(`**`=구분자 포함 0개 이상 세그먼트, `*`=한 세그먼트 내 0개 이상 문자)을
    정규식으로 컴파일한다. trailing `**`(예: `a/**`)는 그 디렉터리 자체(`a`)와 모든 하위 경로를
    매칭한다(디렉터리→파일 교체로 분류를 피하지 못하게)."""
    segments = glob_pattern.split("/")
    parts: "list[str]" = []
    n = len(segments)
    for idx, seg in enumerate(segments):
        is_last = idx == n - 1
        if seg == "**":
            if parts and parts[-1] == "/":
                parts.pop()
            if is_last:
                if parts:
                    parts.append("(?:/.*)?")
                else:
                    parts.append(".*")
            else:
                if parts:
                    parts.append("(?:/[^/]+)*")
                    parts.append("/")
                else:
                    parts.append("(?:[^/]+/)*")
        else:
            parts.append(_translate_glob_segment(seg))
            if not is_last:
                parts.append("/")
    return re.compile("^" + "".join(parts) + "$")


def _glob_matches(glob_pattern: str, path: str) -> bool:
    return _glob_to_regex(glob_pattern).match(path) is not None


# --- axdt-critical-paths 블록 파싱 ---------------------------------------------

_CRITICAL_BLOCK_RE = re.compile(r"```axdt-critical-paths\r?\n(.*?)\r?\n```", re.DOTALL)
_CRITICAL_LINE_RE = re.compile(r"^critical\s+(\S+)\s*$")


def _parse_critical_globs(markdown_text: str) -> "list[str]":
    matches = _CRITICAL_BLOCK_RE.findall(markdown_text)
    if len(matches) != 1:
        raise CriticalPathsBlockError(
            f"axdt-critical-paths block: expected exactly 1 fenced block, found {len(matches)}"
        )
    globs = []
    for line in matches[0].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _CRITICAL_LINE_RE.match(stripped)
        if not m:
            raise CriticalPathsBlockError(f"malformed axdt-critical-paths line: {line!r}")
        globs.append(m.group(1))
    if not globs:
        raise CriticalPathsBlockError("axdt-critical-paths block has zero valid 'critical <glob>' lines")
    return globs


# --- 결정/승인 스탬프 파싱 (모듈 docstring의 axdt-decision/axdt-approval 형식) -----

_DECISION_BLOCK_RE = re.compile(r"```axdt-decision\r?\n(.*?)\r?\n```", re.DOTALL)
_APPROVAL_BLOCK_RE = re.compile(r"```axdt-approval\r?\n(.*?)\r?\n```", re.DOTALL)
_KV_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(\S+)\s*$")
_FINDING_ID_RE = re.compile(r"^F-\d+$")
_HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{16,}$")

_JUDGMENT_STAMP_FIELDS = ("tree_hash", "rule_fingerprint", "review_policy_epoch", "rule_catalog_manifest_digest")
_COMPLETENESS_STAMP_FIELDS = ("projection_tree_hash", "active_catalog_input_digest", "review_policy_epoch")
_APPROVAL_STAMP_FIELDS = (
    "judgment_tree_hash", "judgment_rule_fingerprint",
    "judgment_review_policy_epoch", "judgment_rule_catalog_manifest_digest",
    "completeness_projection_tree_hash", "completeness_active_catalog_input_digest",
    "completeness_review_policy_epoch",
)


def _parse_kv_lines(block_text: str) -> "dict[str, str] | None":
    """`key: value` 줄만(한 줄에 하나, 값은 공백 없는 단일 토큰). `#` 주석·중복 키는 미지원 —
    있으면 기형(모호성 배제, None 반환)."""
    fields: "dict[str, str]" = {}
    for line in block_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = _KV_LINE_RE.match(stripped)
        if not m:
            return None
        key, value = m.group(1), m.group(2)
        if key in fields:
            return None
        fields[key] = value
    return fields


def _parse_decision_stamp(body: str):
    """axdt-decision 스탬프 파싱. 반환: (review_key, finding_id, digest, FindingDecision) 또는
    스탬프가 없거나 기형이면 None(그 코멘트는 결정이 아니다 — skip)."""
    matches = _DECISION_BLOCK_RE.findall(body)
    if len(matches) != 1:
        return None
    fields = _parse_kv_lines(matches[0])
    if fields is None:
        return None

    finding = fields.get("finding")
    digest = fields.get("digest")
    decision_str = fields.get("decision")
    if finding is None or not _FINDING_ID_RE.match(finding):
        return None
    if digest is None or not _HEX_DIGEST_RE.match(digest):
        return None
    if decision_str not in ("accepted", "rejected"):
        return None

    key_kind = fields.get("key")
    if key_kind == "judgment":
        if any(fields.get(f) is None for f in _JUDGMENT_STAMP_FIELDS):
            return None
        review_key = JudgmentKey(**{f: fields[f] for f in _JUDGMENT_STAMP_FIELDS})
    elif key_kind == "completeness":
        if any(fields.get(f) is None for f in _COMPLETENESS_STAMP_FIELDS):
            return None
        review_key = CompletenessSweepKey(**{f: fields[f] for f in _COMPLETENESS_STAMP_FIELDS})
    else:
        return None

    decision = FindingDecision.ACCEPTED if decision_str == "accepted" else FindingDecision.REJECTED
    return review_key, finding, digest, decision


def _parse_approval_stamp(body: str):
    """axdt-approval 스탬프 파싱(§2.3 (ㄴ)). 반환: (JudgmentKey, CompletenessSweepKey) 또는
    스탬프가 없거나 두 키 중 어느 필드라도 빠지면 None(그 승인은 무효 — 배제)."""
    matches = _APPROVAL_BLOCK_RE.findall(body)
    if len(matches) != 1:
        return None
    fields = _parse_kv_lines(matches[0])
    if fields is None:
        return None
    if any(fields.get(f) is None for f in _APPROVAL_STAMP_FIELDS):
        return None
    judgment = JudgmentKey(
        tree_hash=fields["judgment_tree_hash"],
        rule_fingerprint=fields["judgment_rule_fingerprint"],
        review_policy_epoch=fields["judgment_review_policy_epoch"],
        rule_catalog_manifest_digest=fields["judgment_rule_catalog_manifest_digest"],
    )
    completeness = CompletenessSweepKey(
        projection_tree_hash=fields["completeness_projection_tree_hash"],
        active_catalog_input_digest=fields["completeness_active_catalog_input_digest"],
        review_policy_epoch=fields["completeness_review_policy_epoch"],
    )
    return judgment, completeness


# --- 룰셋 선언 상태 (ENFORCEMENT_MATRIX.md가 아직 없어 그 임시 대체물 — §5·§8) -----
# 스펙 §4.1이 정의하는 RS-A/RS-B/RS-C 선언 상태를 코드 상수로 인코딩했다. `WIP/axdt/sot_gate/
# ENFORCEMENT_MATRIX.md`가 작성되면 이 상수는 그 문서를 단일 출처로 다시 도출해야 한다.

_RS_B_REQUIRED_PARAMS = {
    "dismiss_stale_reviews_on_push": True,
    "require_last_push_approval": True,
    "allowed_merge_methods": ["merge"],
}
_RS_B_MIN_APPROVING_REVIEWS = 1
_RS_C_TARGET_HINT = "sot/"   # RS-C의 conditions.ref_name.include 중 하나가 이 문자열을 포함해야 함


class GitHubGatePorts(GateHostPorts):
    """GateHostPorts의 GitHub 구현. 아래 5포트는 `gh api`(CommandBackend 경유)로 구현했다:
    `read_pr_metadata`·`read_channel_decisions`·`read_approvals`·`merge_pull_request`·
    `verify_ruleset_config`. `compute_landing_keys`·`read_ci_artifacts`는 이 증분 범위 밖이라
    NotImplementedError로 남겨 뒀다(스켈레톤 그대로)."""

    def __init__(self, backend: "CommandBackend", target_repo: str, cwd: "Path | None" = None):
        owner, sep, repo = target_repo.partition("/")
        if not sep or not owner or not repo:
            raise ValueError(f"target_repo must be 'owner/name': {target_repo!r}")
        self._backend = backend
        self._target_repo = target_repo
        self._owner = owner
        self._repo = repo
        self._cwd = cwd

    # --- 스켈레톤 그대로(범위 밖) --------------------------------------------

    def compute_landing_keys(self, pr: "PullRequest") -> "tuple[JudgmentKey, CompletenessSweepKey]":
        """제안된 머지 결과 상태에서 착지 두 키(판정 키 4성분·완전성 스윕 키 3성분)를 계산(§2.3).
        gh api로 "제안된 머지 결과"를 얻는 방법과 두 키 성분 계산은 provisional(§8) — 이 증분
        범위 밖."""
        raise NotImplementedError("GitHubGatePorts.compute_landing_keys — Phase 9 라이브 확정 전(provisional)")

    def read_ci_artifacts(self, pr: "PullRequest") -> "tuple[ConsistencyArtifact | None, CompletenessArtifact | None]":
        """② 검토 CI가 쓴 두 신뢰 산출물(정합성·완전성)을 산출물 저장소에서 읽는다. 산출물
        저장 위치와 쓰기 통제는 provisional(§4.2, §8) — 이 증분 범위 밖."""
        raise NotImplementedError("GitHubGatePorts.read_ci_artifacts — Phase 9 라이브 확정 전(provisional)")

    # --- 내부 helper: CommandBackend 실행 + JSON 파싱 ------------------------

    def _run(self, argv: "list[str]"):
        result = self._backend.run(argv, cwd=self._cwd)
        if result.exit_code != 0:
            raise GitHostError.from_result(result)
        return result

    def _api_get(self, path: str, *, paginate: bool = False):
        argv = ["gh", "api", path]
        if paginate:
            argv.append("--paginate")
        return self._run(argv)

    @staticmethod
    def _json_object(result) -> dict:
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError) as e:
            raise GitHostError(result.argv, result.exit_code, result.stdout, str(e)) from e
        if not isinstance(data, dict):
            raise GitHostError(result.argv, result.exit_code, result.stdout, "not a JSON object")
        return data

    @staticmethod
    def _json_list(result) -> list:
        """`gh api --paginate`는 배열 응답을 페이지별 별개 JSON 배열로 이어붙여 낸다(단일
        배열로 병합하지 않음 — 모듈 docstring 참조). stdout을 반복 `raw_decode`해 각 페이지
        배열을 하나의 파이썬 리스트로 평탄화한다. 페이지가 하나뿐이어도(비페이지 소량 응답)
        그대로 파싱된다."""
        decoder = json.JSONDecoder()
        text = result.stdout
        idx, n = 0, len(text)
        items: list = []
        while idx < n:
            while idx < n and text[idx].isspace():
                idx += 1
            if idx >= n:
                break
            try:
                value, end = decoder.raw_decode(text, idx)
            except ValueError as e:
                raise GitHostError(result.argv, result.exit_code, result.stdout, str(e)) from e
            if not isinstance(value, list):
                raise GitHostError(result.argv, result.exit_code, result.stdout, "page is not a JSON array")
            items.extend(value)
            idx = end
        return items

    # --- read_pr_metadata -----------------------------------------------------

    def read_pr_metadata(self, pr: "PullRequest") -> "PRMetadata":
        result = self._api_get(f"repos/{self._owner}/{self._repo}/pulls/{pr.number}")
        data = self._json_object(result)
        try:
            author = data["user"]["login"]
            head = data["head"]
            head_ref = head["ref"]
            head_sha = head["sha"]
            raw_state = data["state"]
            merged = bool(data.get("merged", False))
        except (KeyError, TypeError) as e:
            raise GitHostError(result.argv, result.exit_code, result.stdout, str(e)) from e

        head_repo_obj = head.get("repo") if isinstance(head, dict) else None
        if not isinstance(head_repo_obj, dict) or "full_name" not in head_repo_obj:
            # head.repo가 null인 경우(소스 저장소가 삭제된 포크 등) 포크 판별이 불가하므로
            # fail-closed(예외) — 이 케이스를 head_repo=target_repo로 얼버무리지 않는다.
            raise GitHostError(result.argv, result.exit_code, result.stdout,
                               "pull request head.repo missing (deleted fork?)")
        head_repo = head_repo_obj["full_name"]

        state = self._map_pr_state(raw_state, merged)

        files = self._read_changed_files(pr)
        paths = self._changed_paths(files)
        touches_sot = any(_is_sot_projection_path(p) for p in paths)
        touches_enforcement_surface = self._touches_enforcement_surface(paths)

        return PRMetadata(
            author=author, head_ref=head_ref, head_repo=head_repo, head_sha=head_sha,
            state=state, touches_sot=touches_sot,
            touches_enforcement_surface=touches_enforcement_surface,
        )

    @staticmethod
    def _map_pr_state(raw_state: str, merged: bool) -> "PullRequestState":
        # REST pulls/{number}의 state는 "open"/"closed"(소문자) + 별도 merged 불리언이다
        # (git_host.adapters.github._STATE_MAP의 "OPEN"/"MERGED"/"CLOSED"는 `gh pr view --json`
        # GraphQL 값이라 다른 도메인 — 재사용하지 않는다, 모듈 docstring 참조).
        if raw_state == "open":
            return PullRequestState.OPEN
        if raw_state == "closed":
            return PullRequestState.MERGED if merged else PullRequestState.CLOSED
        return PullRequestState.UNKNOWN

    def _read_changed_files(self, pr: "PullRequest") -> "list[dict]":
        result = self._api_get(
            f"repos/{self._owner}/{self._repo}/pulls/{pr.number}/files", paginate=True
        )
        items = self._json_list(result)
        for item in items:
            if not isinstance(item, dict) or "filename" not in item:
                raise GitHostError(result.argv, result.exit_code, result.stdout,
                                   "files item missing 'filename'")
        return items

    @staticmethod
    def _changed_paths(files: "list[dict]") -> "set[str]":
        # rename 방어: 변경 전·후 경로 합집합 모두에 판정을 적용한다(critical 경로를 비critical
        # 경로로 옮겨 분류를 피하지 못하게, §2.6).
        paths: "set[str]" = set()
        for f in files:
            paths.add(f["filename"])
            prev = f.get("previous_filename")
            if prev:
                paths.add(prev)
        return paths

    def _touches_enforcement_surface(self, paths: "set[str]") -> bool:
        globs = self._read_critical_globs()
        return any(_glob_matches(g, p) for g in globs for p in paths)

    def _read_critical_globs(self) -> "list[str]":
        result = self._api_get(
            f"repos/{self._owner}/{self._repo}/contents/docs/sot/rule/protected-paths.md?ref=main"
        )
        data = self._json_object(result)
        encoded = data.get("content")
        if not isinstance(encoded, str):
            raise CriticalPathsBlockError(
                "contents API response for protected-paths.md missing 'content' field"
            )
        try:
            text = base64.b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as e:
            raise CriticalPathsBlockError(f"failed to decode protected-paths.md content: {e}") from e
        return _parse_critical_globs(text)

    # --- read_channel_decisions -------------------------------------------

    def read_channel_decisions(self, pr: "PullRequest") -> "tuple[ChannelDecision, ...]":
        result = self._api_get(
            f"repos/{self._owner}/{self._repo}/issues/{pr.number}/comments", paginate=True
        )
        comments = self._json_list(result)
        decisions = []
        for c in comments:
            if not isinstance(c, dict):
                continue
            parsed = _parse_decision_stamp(c.get("body") or "")
            if parsed is None:
                continue    # 스탬프 없음/기형 -> 결정 아님(skip)
            review_key, finding_id, digest, decision = parsed
            try:
                author = c["user"]["login"]
                comment_id = int(c["id"])
                created_at = c["created_at"]
                updated_at = c["updated_at"]
            except (KeyError, TypeError, ValueError):
                continue    # 코멘트 봉투 자체가 기형이면 결정 아님(skip)

            decisions.append(ChannelDecision(
                key=FullBindingKey(review_key=review_key, finding_id=finding_id, content_digest=digest),
                decision=decision,
                author=author,
                comment_id=comment_id,
                created_at=created_at,
                updated_at=updated_at,
                deleted=False,   # 삭제된 코멘트는 이 스트림에 애초에 나타나지 않는다.
                author_role=self._role_name(author),
                author_is_human=self._is_human(author),
            ))
        return tuple(decisions)

    # --- read_approvals -----------------------------------------------------

    _APPROVAL_LIKE_STATES = frozenset({"APPROVED", "DISMISSED"})

    def read_approvals(self, pr: "PullRequest") -> "tuple[ApprovalEvent, ...]":
        result = self._api_get(
            f"repos/{self._owner}/{self._repo}/pulls/{pr.number}/reviews", paginate=True
        )
        reviews = self._json_list(result)
        approvals = []
        for r in reviews:
            if not isinstance(r, dict):
                continue
            state = r.get("state")
            if state not in self._APPROVAL_LIKE_STATES:
                continue
            stamp = _parse_approval_stamp(r.get("body") or "")
            if stamp is None:
                continue    # 두 키 스탬프 없음/기형 -> 무효 승인(배제, 재계산 금지 §2.3)
            judgment, completeness = stamp
            try:
                approver = r["user"]["login"]
                seq = int(r["id"])
            except (KeyError, TypeError, ValueError):
                continue

            approvals.append(ApprovalEvent(
                approver=approver,
                approved_judgment=judgment,
                approved_completeness=completeness,
                seq=seq,
                approver_role=self._role_name(approver),
                approver_is_human=self._is_human(approver),
                dismissed=(state == "DISMISSED"),
            ))
        return tuple(approvals)

    # --- role_name / 사람 계정 판별 (§2.7 원시 사실) --------------------------

    def _role_name(self, login: str) -> str:
        try:
            result = self._api_get(f"repos/{self._owner}/{self._repo}/collaborators/{login}/permission")
        except GitHostError:
            # 저장소 협업자가 아닌 계정(예: 포크 PR의 외부 코멘터)은 404 — role_name 미상을
            # 원시 사실 공백("")으로 채운다. 코어 _authorized()가 role=="admin"이 아니면
            # 자연히 배제하므로 여기서 크래시 대신 공백으로 접는 것이 안전하다(provisional).
            return ""
        data = self._json_object(result)
        role = data.get("role_name")
        return role if isinstance(role, str) else ""

    def _is_human(self, login: str) -> bool:
        try:
            result = self._api_get(f"users/{login}")
        except GitHostError:
            return False
        data = self._json_object(result)
        return data.get("type") != "Bot"

    # --- merge_pull_request ---------------------------------------------------

    _HTTP_STATUS_RE = re.compile(r"\(HTTP (\d+)\)", re.IGNORECASE)

    def merge_pull_request(self, pr: "PullRequest", judgment: "JudgmentKey",
                           completeness: "CompletenessSweepKey", head_sha: str) -> None:
        # judgment/completeness는 감사 기록용 인자(§2.9의 착지 두 키) — 머지 API 호출 자체에는
        # 실리지 않는다(컨트롤러가 audit_log에 별도로 남긴다, controller.py._record_audit).
        argv = [
            "gh", "api", "--method", "PUT",
            f"repos/{self._owner}/{self._repo}/pulls/{pr.number}/merge",
            "-f", f"sha={head_sha}",
            "-f", "merge_method=merge",
        ]
        result = self._backend.run(argv, cwd=self._cwd)
        if result.exit_code != 0:
            status = self._extract_http_status(result)
            if status == 409:
                # 409 = "Head branch was modified. Review and try the merge again." — sha 불일치
                # (head 이동, §2.5). 405("New changes require approval from someone other than
                # the last pusher" 등 — 실증 §4.1)는 승인 부족/머지 불가 일반 사유이지 head 이동이
                # 아니므로 여기서 HeadMovedError로 번역하지 않는다.
                raise HeadMovedError(
                    f"host rejected merge: head moved (head_sha={head_sha!r} no longer current); "
                    f"{result.stderr or result.stdout}"
                )
            raise GitHostError.from_result(result)
        return None

    def _extract_http_status(self, result) -> "int | None":
        for text in (result.stderr, result.stdout):
            m = self._HTTP_STATUS_RE.search(text or "")
            if m:
                return int(m.group(1))
        return None

    # --- verify_ruleset_config -------------------------------------------------

    def verify_ruleset_config(self) -> bool:
        try:
            listing_result = self._api_get(
                f"repos/{self._owner}/{self._repo}/rulesets", paginate=True
            )
            listing = self._json_list(listing_result)
        except GitHostError:
            return False

        details = []
        for item in listing:
            if not isinstance(item, dict) or "id" not in item:
                return False
            try:
                detail_result = self._api_get(f"repos/{self._owner}/{self._repo}/rulesets/{item['id']}")
                details.append(self._json_object(detail_result))
            except GitHostError:
                return False

        rs_a_found = rs_b_found = rs_c_found = False
        for detail in details:
            rule_types = self._ruleset_rule_types(detail)
            bypass_actors = detail.get("bypass_actors", [])
            if not isinstance(bypass_actors, list):
                return False

            has_update = "update" in rule_types
            has_pull_request = "pull_request" in rule_types
            has_nff = "non_fast_forward" in rule_types
            has_deletion = "deletion" in rule_types

            if has_update and has_pull_request:
                # RS-A/RS-B가 한 룰셋으로 합쳐짐 — 불변식 위반(§4.1: bypass가 승인까지 함께
                # 우회하는 실증된 위험).
                return False

            if has_update:
                # RS-A — 갱신 제한. bypass_actors는 "컨트롤러만"이어야 하므로 정확히 1개.
                if len(bypass_actors) != 1:
                    return False
                rs_a_found = True
                continue

            if has_pull_request and has_nff and has_deletion:
                # RS-B — 승인·감사. bypass_actors 공백 + 필수 파라미터.
                if bypass_actors:
                    return False
                if not self._pull_request_params_ok(rule_types.get("pull_request") or {}):
                    return False
                rs_b_found = True
                continue

            if has_nff and has_deletion and not has_pull_request:
                # RS-C 후보 — sot/* 단조 전진. bypass_actors 공백 + 대상이 sot/*.
                if bypass_actors:
                    return False
                if self._targets_sot(detail):
                    rs_c_found = True
                continue

        return rs_a_found and rs_b_found and rs_c_found

    @staticmethod
    def _ruleset_rule_types(detail: dict) -> "dict[str, dict]":
        rules = detail.get("rules", [])
        if not isinstance(rules, list):
            return {}
        types: "dict[str, dict]" = {}
        for rule in rules:
            if isinstance(rule, dict) and "type" in rule:
                types[rule["type"]] = rule.get("parameters") or {}
        return types

    @staticmethod
    def _pull_request_params_ok(params: dict) -> bool:
        if not isinstance(params, dict):
            return False
        count = params.get("required_approving_review_count")
        if not isinstance(count, int) or count < _RS_B_MIN_APPROVING_REVIEWS:
            return False
        return all(params.get(k) == v for k, v in _RS_B_REQUIRED_PARAMS.items())

    @staticmethod
    def _targets_sot(detail: dict) -> bool:
        conditions = detail.get("conditions")
        ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
        include = ref_name.get("include") if isinstance(ref_name, dict) else None
        if not isinstance(include, list):
            return False
        return any(isinstance(p, str) and _RS_C_TARGET_HINT in p for p in include)
