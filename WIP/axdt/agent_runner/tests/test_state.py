from axdt.agent_runner.state import AgentState


def test_vocabulary_is_exactly_the_controlled_set():
    assert {s.name for s in AgentState} == {
        "STARTING", "IDLE", "BUSY", "WAITING_INPUT", "STOPPED", "ERROR",
    }


def test_values_are_lowercase_names():
    for s in AgentState:
        assert s.value == s.name.lower()
