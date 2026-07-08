import time
from pathlib import Path

from axdt.git_host.state import PullRequestState, ReviewDecision, MergeMethod
from axdt.git_host.models import PullRequest, ReviewSnapshot, GateResult, GitHostError
from axdt.git_host.adapters.base import GitHostAdapter
from axdt.git_host.backend import CommandBackend


class GitHostClient:
    """Common Git-host interface = adapter + backend composition. Result authority is progress (ADR-0004)."""

    CLOSED_STATES = frozenset({PullRequestState.MERGED, PullRequestState.CLOSED})

    def __init__(self, adapter: GitHostAdapter, backend: CommandBackend,
                 cwd: "Path | None" = None):
        self._adapter = adapter
        self._backend = backend
        self._cwd = cwd

    def _run(self, argv: list):
        """Run one command; a non-zero exit becomes GitHostError (the backend itself never raises on exit)."""
        result = self._backend.run(argv, cwd=self._cwd)
        if result.exit_code != 0:
            raise GitHostError.from_result(result)
        return result

    def open_pull_request(self, head: str, base: str,
                          title: str, body: str) -> PullRequest:
        """create→view composition (§2.7). Any non-zero exit → GitHostError. Reviewers are NOT attached."""
        create = self._run(self._adapter.build_create_pr_command(head, base, title, body))
        ref = self._adapter.parse_create_ref(create)
        view = self._run(self._adapter.build_get_pr_command(ref))
        return self._adapter.parse_pr(view, head, base)

    def request_review(self, pr: PullRequest, reviewer: str) -> None:
        """Assign/re-request reviewer (idempotent re-call = re-request, NOT a decision reset). Failure → GitHostError."""
        self._run(self._adapter.build_request_review_command(pr.number, reviewer))

    def poll_state(self, pr: PullRequest) -> PullRequestState:
        """One-shot PR lifecycle state (monitoring, non-authoritative). Failure → GitHostError."""
        view = self._run(self._adapter.build_get_pr_command(pr.number))
        return self._adapter.parse_pr_state(view)

    def poll_review(self, pr: PullRequest, reviewer: str) -> ReviewSnapshot:
        """One-shot review sample for the target reviewer (gate cursor). Failure → GitHostError."""
        view = self._run(self._adapter.build_get_pr_command(pr.number))
        return self._adapter.parse_review(view, reviewer)

    def wait_for_decision(self, pr: PullRequest, reviewer: str, timeout: float,
                          poll_interval: float = 30.0, *,
                          max_consecutive_errors: int = 3) -> GateResult:
        """Gate resume wait (§2.8). Capture the target reviewer's latest review id as the cursor at start,
        then return when a terminal review LATER in stream position than the cursor arrives (terminal_after),
        or the PR reaches CLOSED_STATES → GateResult(timed_out=False); on timeout → GateResult(timed_out=True).
        COMMENTED is non-terminal. Transient failures are tolerated up to max_consecutive_errors missed polls,
        then propagated."""
        deadline = time.monotonic() + timeout
        last_state = PullRequestState.UNKNOWN
        consecutive_errors = 0
        # Capture the entry cursor with the same tolerance as the poll loop: a transient
        # failure on the very first read must not kill the gate (I-B).
        while True:
            try:
                cursor = self.poll_review(pr, reviewer).latest_review_id
            except GitHostError:
                consecutive_errors += 1
                if consecutive_errors > max_consecutive_errors:
                    raise
                if time.monotonic() >= deadline:
                    return GateResult(True, last_state, ReviewDecision.PENDING)
                time.sleep(poll_interval)
            else:
                break
        consecutive_errors = 0
        while True:
            try:
                state = self.poll_state(pr)
                snap = self.poll_review(pr, reviewer)
            except GitHostError:
                consecutive_errors += 1
                if consecutive_errors > max_consecutive_errors:
                    raise
            else:
                consecutive_errors = 0
                last_state = state
                decision = snap.terminal_after(cursor)
                if state in self.CLOSED_STATES:
                    return GateResult(False, state, decision or ReviewDecision.PENDING)
                if decision is not None:
                    return GateResult(False, state, decision)
            if time.monotonic() >= deadline:
                # Timed out: no terminal decision was reached (else we'd have returned), so decision is PENDING.
                return GateResult(True, last_state, ReviewDecision.PENDING)
            time.sleep(poll_interval)

    def merge(self, pr: PullRequest, method: MergeMethod = MergeMethod.SQUASH) -> None:
        """Merge primitive (policy gating is the orchestrator's job). Failure → GitHostError.
        Note: a SoT gate PR needs MergeMethod.MERGE for audit-history preservation (§9)."""
        self._run(self._adapter.build_merge_command(pr.number, method))
