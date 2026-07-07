from enum import Enum


class PullRequestState(Enum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
    UNKNOWN = "unknown"               # host value not in map (NOT a parse failure)


class ReviewDecision(Enum):
    PENDING = "pending"               # no decision
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"           # comment-only (non-terminal)


class MergeMethod(Enum):
    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"


# Terminal (wait-ending) decisions. COMMENTED is non-terminal.
TERMINAL_DECISIONS = frozenset({ReviewDecision.APPROVED, ReviewDecision.CHANGES_REQUESTED})
