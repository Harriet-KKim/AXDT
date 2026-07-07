from abc import ABC, abstractmethod
from collections.abc import Mapping

from axdt.git_host.state import PullRequestState, ReviewDecision, MergeMethod
from axdt.git_host.models import (
    PullRequest,
    CommandResult,
    ReviewEvent,
    ReviewSnapshot,
    GitHostError,
)


class GitHostAdapter(ABC):
    """Git-host-specific knowledge. parse_* are concrete base methods; subclasses provide
    data (cli, field names, value maps) and the argv builders. The only abstract methods
    are the 4 build_* commands."""

    name: str                         # "github" | "gitlab" | "forgejo"
    cli: str                          # "gh" | "glab" | "tea"

    # view(get-pr) JSON fields/maps (subclasses declare; provisional — HOST_MATRIX)
    _NUMBER_FIELD: str = "number"
    _URL_FIELD: str = "url"
    _STATE_FIELD: str = "state"
    _STATE_MAP: Mapping[str, PullRequestState] = {}
    _REVIEWS_FIELD: str = "reviews"                    # full review history (order preserved; consensus B)
    _REVIEW_AUTHOR_PATH: tuple = ("author", "login")  # locate a review item's reviewer login
    _REVIEW_STATE_FIELD: str = "state"
    _REVIEW_ID_FIELD: str = "id"                       # opaque review id (not a timestamp — consensus C)
    _REVIEW_STATE_MAP: Mapping[str, ReviewDecision] = {}
    _REVIEW_REQUESTS_FIELD: str = "reviewRequests"
    _REQUEST_LOGIN_FIELD: str = "login"                # User/Bot only; Team has no login (consensus E)

    @abstractmethod
    def build_create_pr_command(self, head: str, base: str,
                                title: str, body: str) -> list[str]:
        """PR-create argv. body is passed as an arg into the argv (list argv → shell-escape safe;
        very long bodies via --body-file is provisional). Reviewers are NOT included (§2.6)."""

    @abstractmethod
    def build_get_pr_command(self, ref: "int | str") -> list[str]:
        """PR view argv. JSON request must include number,url,state,reviews,reviewRequests (consensus B)."""

    @abstractmethod
    def build_request_review_command(self, number: int, reviewer: str) -> list[str]:
        """Add-reviewer (re-request) argv. Re-call = re-request (not a decision reset, §2.8). Single reviewer."""

    @abstractmethod
    def build_merge_command(self, number: int, method: MergeMethod) -> list[str]: ...

    def parse_create_ref(self, result: CommandResult) -> str:
        """create stdout → ref for the view call. Default: last non-empty line (gh emits the URL).
        Empty stdout → GitHostError."""
        for line in reversed(result.stdout.splitlines()):
            if line.strip():
                return line.strip()
        raise GitHostError.from_result(result)

    def parse_pr(self, result: CommandResult, head: str, base: str) -> PullRequest:
        """view JSON → PullRequest(number/url). Missing field / type error / non-dict JSON → GitHostError."""
        data = self._loads(result)
        try:
            return PullRequest(number=int(data[self._NUMBER_FIELD]),
                               url=str(data[self._URL_FIELD]), head=head, base=base)
        except (KeyError, TypeError, ValueError) as e:
            raise GitHostError(result.argv, result.exit_code, result.stdout, str(e)) from e

    def parse_pr_state(self, result: CommandResult) -> PullRequestState:
        """view JSON → PR lifecycle state (monitoring). Unknown value → UNKNOWN."""
        data = self._loads(result)
        return self._STATE_MAP.get(str(data.get(self._STATE_FIELD)), PullRequestState.UNKNOWN)

    def parse_review(self, result: CommandResult, reviewer: str) -> ReviewSnapshot:
        """view JSON reviews/reviewRequests → the target reviewer's ReviewSnapshot (§2.8, consensus A–E).
        Build an ordered (oldest→newest) ReviewEvent list from the reviews history for the target reviewer;
        unmapped review state → COMMENTED (conservative, non-terminal). Compute awaiting from reviewRequests
        membership, skipping login-less heterogeneous items (Team). JSON/structural errors → GitHostError."""
        data = self._loads(result)
        reviews = data.get(self._REVIEWS_FIELD) or []
        if not isinstance(reviews, list):
            raise GitHostError(result.argv, result.exit_code, result.stdout,
                               f"{self._REVIEWS_FIELD} is not a list")
        events = []
        for item in reviews:
            if not isinstance(item, dict):
                raise GitHostError(result.argv, result.exit_code, result.stdout,
                                   "review item is not an object")
            if self._dig(item, self._REVIEW_AUTHOR_PATH) != reviewer:
                continue
            try:
                review_id = str(item[self._REVIEW_ID_FIELD])
            except (KeyError, TypeError) as e:
                raise GitHostError(result.argv, result.exit_code, result.stdout, str(e)) from e
            decision = self._REVIEW_STATE_MAP.get(
                str(item.get(self._REVIEW_STATE_FIELD)), ReviewDecision.COMMENTED)
            events.append(ReviewEvent(review_id, decision))
        requests = data.get(self._REVIEW_REQUESTS_FIELD) or []
        if not isinstance(requests, list):
            raise GitHostError(result.argv, result.exit_code, result.stdout,
                               f"{self._REVIEW_REQUESTS_FIELD} is not a list")
        awaiting = any(
            isinstance(req, dict) and req.get(self._REQUEST_LOGIN_FIELD) == reviewer
            for req in requests
        )
        return ReviewSnapshot(events=tuple(events), awaiting=awaiting)

    @staticmethod
    def _dig(obj, path):
        """Walk a key path through nested dicts; return None if any level is missing/not a dict."""
        for key in path:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        return obj

    def _loads(self, result: CommandResult) -> dict:
        import json
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError) as e:
            raise GitHostError(result.argv, result.exit_code, result.stdout, str(e)) from e
        if not isinstance(data, dict):
            raise GitHostError(result.argv, result.exit_code, result.stdout, "not a JSON object")
        return data
