from pathlib import Path

import pytest

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter
from axdt.agent_runner.adapters.claude_code import ClaudeCodeAdapter
from axdt.agent_runner.adapters.codex import CodexAdapter


def test_platform_adapter_is_abstract():
    with pytest.raises(TypeError):
        PlatformAdapter()  # cannot instantiate abstract base


def test_claude_identity_and_config_dir():
    a = ClaudeCodeAdapter()
    assert a.name == "claude-code"
    assert a.config_dir_name == ".claude"
    assert a.config_dir(Path("/work/wt")) == Path("/work/wt/.claude")


def test_claude_launch_and_prompt():
    a = ClaudeCodeAdapter()
    assert a.build_launch_command(Path("/work/wt")) == ["claude"]
    assert a.format_prompt("hi") == "hi\n"


def test_claude_detect_state_markers():
    a = ClaudeCodeAdapter()
    assert a.detect_state("fatal: boom") is AgentState.ERROR
    assert a.detect_state("Do you want to proceed?") is AgentState.WAITING_INPUT
    assert a.detect_state("... Esc to interrupt") is AgentState.BUSY
    assert a.detect_state("\n> ") is AgentState.IDLE
    assert a.detect_state("random noise") is None  # inconclusive


def test_detect_state_latest_marker_wins():
    # Most-recent signal wins: a fresh IDLE prompt after a BUSY spinner recovers.
    a = ClaudeCodeAdapter()
    assert a.detect_state("... Esc to interrupt ...\n> ") is AgentState.IDLE
    # And the reverse — a BUSY spinner after an IDLE prompt reads BUSY.
    assert a.detect_state("\n> \n... Esc to interrupt") is AgentState.BUSY


def test_bare_adapter_uses_base_defaults():
    # Empty base marker tuples -> detect_state always inconclusive; the concrete
    # base config_dir / format_prompt still work without any overrides.
    class BareAdapter(PlatformAdapter):
        name = "bare"
        config_dir_name = ".bare"

        def build_launch_command(self, workdir):
            return ["bare"]

    a = BareAdapter()
    assert a.detect_state("Esc to interrupt\n> fatal:") is None
    assert a.format_prompt("x") == "x\n"
    assert a.config_dir(Path("/w")) == Path("/w/.bare")


def test_codex_identity_and_config_dir():
    a = CodexAdapter()
    assert a.name == "codex"
    assert a.config_dir_name == ".codex"
    assert a.config_dir(Path("/work/wt")) == Path("/work/wt/.codex")


def test_codex_launch_and_prompt():
    a = CodexAdapter()
    assert a.build_launch_command(Path("/work/wt")) == ["codex"]
    assert a.format_prompt("hi") == "hi\n"


def test_codex_detect_state_markers():
    a = CodexAdapter()
    assert a.detect_state("stream error: boom") is AgentState.ERROR
    assert a.detect_state("Allow command? [y/N]") is AgentState.WAITING_INPUT
    assert a.detect_state("working (ctrl-c to interrupt)") is AgentState.BUSY
    assert a.detect_state("\n› ") is AgentState.IDLE
    assert a.detect_state("random noise") is None
