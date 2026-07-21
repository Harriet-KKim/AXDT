import json
from pathlib import Path

import pytest

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter
from axdt.agent_runner.adapters.claude_code import ClaudeCodeAdapter
from axdt.agent_runner.adapters.codex import CodexAdapter
from axdt.roles.spec import ROLES, SUBAGENT_ROLES, Capability


def test_platform_adapter_is_abstract():
    with pytest.raises(TypeError):
        PlatformAdapter()  # cannot instantiate abstract base


def test_claude_identity_and_config_dir():
    a = ClaudeCodeAdapter()
    assert a.name == "claude-code"
    assert a.config_dir_name == ".claude"
    assert a.config_dir(Path("/work/wt")) == Path("/work/wt/.claude")


def test_claude_session_command_and_prompt():
    a = ClaudeCodeAdapter()
    cmd = a.build_session_command(ROLES["leader"], Path("/work/wt"))
    assert cmd[0] == "claude"
    assert "--append-system-prompt" in cmd
    assert ROLES["leader"].system_prompt in cmd
    assert a.format_prompt("hi") == "hi"
    assert a.submit_key() == "Enter"
    assert a.clear_key() == "C-u"


def test_claude_detect_state_hook_mapping():
    a = ClaudeCodeAdapter()
    assert a.detect_state("idle") is AgentState.IDLE
    assert a.detect_state("start") is AgentState.IDLE
    assert a.detect_state("busy") is AgentState.BUSY
    assert a.detect_state("waiting") is AgentState.WAITING_INPUT
    assert a.detect_state("bogus") is None
    assert a.detect_state(None) is None


def test_claude_capability_args_shape():
    a = ClaudeCodeAdapter()
    read_only = a.capability_args(Capability.READ_ONLY)
    assert "--tools" in read_only
    assert "--permission-mode" in read_only
    assert "plan" in read_only

    write_workspace = a.capability_args(Capability.WRITE_WORKSPACE)
    assert "--permission-mode" in write_workspace
    assert "dontAsk" in write_workspace

    host_control = a.capability_args(Capability.HOST_CONTROL)
    assert "--permission-mode" in host_control
    assert "dontAsk" in host_control


def test_claude_prepare_subagents_returns_agents_json():
    a = ClaudeCodeAdapter()
    args = a.prepare_subagents(Path("/work/wt"), SUBAGENT_ROLES)
    assert args[0] == "--agents"
    obj = json.loads(args[1])
    for role in SUBAGENT_ROLES:
        assert role.name in obj


def test_bare_adapter_uses_base_defaults():
    # The base hook-state mapping works without any overrides; the concrete
    # base config_dir / format_prompt still work without any overrides.
    class BareAdapter(PlatformAdapter):
        name = "bare"
        config_dir_name = ".bare"

        def capability_args(self, cap):
            return []

        def prepare_subagents(self, workdir, roles):
            return []

        def build_session_command(self, role, workdir, subagent_args=()):
            return ["bare"]

    a = BareAdapter()
    assert a.detect_state("busy") is AgentState.BUSY
    assert a.format_prompt("x") == "x"
    assert a.config_dir(Path("/w")) == Path("/w/.bare")


def test_codex_identity_and_config_dir():
    a = CodexAdapter()
    assert a.name == "codex"
    assert a.config_dir_name == ".codex"
    assert a.config_dir(Path("/work/wt")) == Path("/work/wt/.codex")


def test_codex_session_command_and_prompt():
    a = CodexAdapter()
    cmd = a.build_session_command(ROLES["leader"], Path("/work/wt"))
    assert cmd[0] == "codex"
    assert cmd[1:3] == ["-p", "leader"]   # 역할↔프로파일 바인딩(결정적; fail-closed 강제는 Phase 3)
    assert "-s" in cmd
    assert "workspace-write" in cmd
    # 역할 시스템 프롬프트는 argv에 실리지 않는다 — -p 프로파일이 얹는다(외부 아티팩트).
    assert ROLES["leader"].system_prompt not in cmd
    assert a.format_prompt("hi") == "hi"
    assert a.submit_key() == "Enter"
    assert a.clear_key() == "C-u"


def test_codex_session_command_binds_role_to_profile():
    # 서로 다른 SESSION 역할은 서로 다른 -p 프로파일을 고른다(역할↔아티팩트 계약).
    a = CodexAdapter()
    leader = a.build_session_command(ROLES["leader"], Path("/w"))
    maint = a.build_session_command(ROLES["maintainer"], Path("/w"))
    assert leader[leader.index("-p") + 1] == "leader"
    assert maint[maint.index("-p") + 1] == "maintainer"
    assert leader[leader.index("-p") + 1] != maint[maint.index("-p") + 1]


def test_codex_detect_state_hook_mapping():
    a = CodexAdapter()
    assert a.detect_state("idle") is AgentState.IDLE
    assert a.detect_state("start") is AgentState.IDLE
    assert a.detect_state("busy") is AgentState.BUSY
    assert a.detect_state("waiting") is AgentState.WAITING_INPUT
    assert a.detect_state("bogus") is None
    assert a.detect_state(None) is None


def test_codex_capability_args_exact():
    a = CodexAdapter()
    assert a.capability_args(Capability.READ_ONLY) == ["-s", "read-only"]
    assert a.capability_args(Capability.WRITE_WORKSPACE) == ["-s", "workspace-write"]
    assert a.capability_args(Capability.HOST_CONTROL) == ["-s", "danger-full-access"]


def test_codex_prepare_subagents_raises_not_implemented():
    a = CodexAdapter()
    with pytest.raises(NotImplementedError):
        a.prepare_subagents(Path("/work/wt"), SUBAGENT_ROLES)
