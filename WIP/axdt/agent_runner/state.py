from enum import Enum


class AgentState(Enum):
    """Controlled state vocabulary. adapter.detect_state maps a hook-emitted state value -> one of these."""

    STARTING = "starting"
    IDLE = "idle"                   # ready to receive a prompt
    BUSY = "busy"                   # processing
    WAITING_INPUT = "waiting_input"  # awaiting user/upstream input
    STOPPED = "stopped"
    ERROR = "error"
