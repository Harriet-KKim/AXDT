import dataclasses
import json
import tomllib
from pathlib import Path, PureWindowsPath

import pytest

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter, RoleArtifact, RoleNotProvisioned
from axdt.agent_runner.adapters.claude_code import ClaudeCodeAdapter
from axdt.agent_runner.adapters.codex import CodexAdapter, _toml_basic_string
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
    assert a.detect_state("starting") is AgentState.STARTING
    assert a.detect_state("idle") is AgentState.IDLE
    assert a.detect_state("busy") is AgentState.BUSY
    assert a.detect_state("waiting_input") is AgentState.WAITING_INPUT
    # 폐지된 별칭(start)·구 값(waiting)은 더는 매핑되지 않는다(어휘 통일, ADR-0019).
    assert a.detect_state("start") is None
    assert a.detect_state("waiting") is None
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

        def role_artifacts(self, role, root):
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


# --- 재리뷰 A: artifact_root — 게이트가 실제로 조회할 root ---

def test_codex_artifact_root_uses_codex_home(tmp_path):
    # `-p`는 $CODEX_HOME/<role>.config.toml을 읽는다 — workdir/.codex가 아니다.
    # env에 CODEX_HOME이 있으면 artifact_root는 workdir을 무시하고 그 경로를 쓴다.
    a = CodexAdapter()
    codex_home = tmp_path / "codex_home"
    workdir = tmp_path / "workdir"
    assert a.artifact_root(workdir, {"CODEX_HOME": str(codex_home)}) == codex_home
    assert a.artifact_root(workdir, {"CODEX_HOME": str(codex_home)}) != a.config_dir(workdir)


def test_claude_artifact_root_is_config_dir():
    a = ClaudeCodeAdapter()
    workdir = Path("/work/wt")
    assert a.artifact_root(workdir, {}) == workdir / ".claude"
    assert a.artifact_root(workdir, {}) == a.config_dir(workdir)


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
    assert a.detect_state("starting") is AgentState.STARTING
    assert a.detect_state("idle") is AgentState.IDLE
    assert a.detect_state("busy") is AgentState.BUSY
    assert a.detect_state("waiting_input") is AgentState.WAITING_INPUT
    # 폐지된 별칭(start)·구 값(waiting)은 더는 매핑되지 않는다(어휘 통일, ADR-0019).
    assert a.detect_state("start") is None
    assert a.detect_state("waiting") is None
    assert a.detect_state("bogus") is None
    assert a.detect_state(None) is None


def test_codex_capability_args_exact():
    a = CodexAdapter()
    assert a.capability_args(Capability.READ_ONLY) == ["-s", "read-only"]
    assert a.capability_args(Capability.WRITE_WORKSPACE) == ["-s", "workspace-write"]
    assert a.capability_args(Capability.HOST_CONTROL) == ["-s", "danger-full-access"]


def test_codex_prepare_subagents_returns_empty():
    a = CodexAdapter()
    assert a.prepare_subagents(Path("/work/wt"), SUBAGENT_ROLES) == []


def test_claude_role_artifacts_empty():
    a = ClaudeCodeAdapter()
    for role in ROLES.values():
        assert a.role_artifacts(role, Path("/w/.claude")) == []


def test_codex_role_artifacts_session_binds_role_and_capability():
    # developer_instructions는 B4 인코더로 이스케이프돼 원문 개행이 리터럴 \n으로
    # 바뀌므로 raw substring이 아니라 tomllib으로 왕복해 값을 비교한다.
    a = CodexAdapter()

    leader_artifacts = a.role_artifacts(ROLES["leader"], Path("/w/.codex"))
    assert len(leader_artifacts) == 1
    leader_artifact = leader_artifacts[0]
    assert leader_artifact.path == Path("leader.config.toml")
    parsed_leader = tomllib.loads(leader_artifact.content)
    assert parsed_leader["developer_instructions"] == ROLES["leader"].system_prompt
    assert 'sandbox_mode = "workspace-write"' in leader_artifact.content

    maintainer_artifacts = a.role_artifacts(ROLES["maintainer"], Path("/w/.codex"))
    assert len(maintainer_artifacts) == 1
    maintainer_artifact = maintainer_artifacts[0]
    assert maintainer_artifact.path == Path("maintainer.config.toml")
    assert 'sandbox_mode = "danger-full-access"' in maintainer_artifact.content


def test_codex_role_artifacts_toml_roundtrips():
    # 스키마는 잠정이므로(슬라이스 B 확정 전) 여기서는 핵심만 검증한다:
    # 역할 프롬프트·sandbox가 파일 최상위에 담기고, [profiles.x] 중첩 테이블을
    # 쓰지 않는다는 것. 정확한 키 이름 등은 아직 강고정하지 않는다.
    a = CodexAdapter()
    expected_sandbox_mode = {
        "leader": "workspace-write",
        "maintainer": "danger-full-access",
        "developer": "workspace-write",
        "reviewer": "read-only",
        "tester": "workspace-write",
    }
    for role in ROLES.values():
        artifact = a.role_artifacts(role, Path("/w/.codex"))[0]
        parsed = tomllib.loads(artifact.content)
        assert parsed["developer_instructions"] == role.system_prompt
        assert parsed["sandbox_mode"] == expected_sandbox_mode[role.name]
        assert "profiles" not in parsed


# --- B4: TOML 단일라인 basic string 인코더 경계값 왕복 ---

BOUNDARY_STRINGS = [
    '"',
    "\\",
    "\n",
    "\r",
    "\r\n",
    "\t",
    "\x00",
    '"""""',       # 큰따옴표 5개 연속 (멀티라인 구분자와 혼동될 법한 구간)
    '\\"\\"',      # 백슬래시+큰따옴표 혼합
]


@pytest.mark.parametrize("boundary", BOUNDARY_STRINGS)
def test_toml_basic_string_roundtrips_boundary_values(boundary):
    literal = _toml_basic_string(boundary)
    assert tomllib.loads(f"v = {literal}")["v"] == boundary


@pytest.mark.parametrize("boundary", BOUNDARY_STRINGS)
def test_codex_role_artifacts_developer_instructions_roundtrips_boundary(boundary):
    a = CodexAdapter()
    role = dataclasses.replace(ROLES["leader"], system_prompt=boundary)
    artifact = a.role_artifacts(role, Path("/w/.codex"))[0]
    parsed = tomllib.loads(artifact.content)
    assert parsed["developer_instructions"] == boundary


def test_codex_role_artifacts_model_hint_roundtrips_boundary():
    a = CodexAdapter()
    role = dataclasses.replace(ROLES["leader"], model_hint='a"b\\c')
    artifact = a.role_artifacts(role, Path("/w/.codex"))[0]
    parsed = tomllib.loads(artifact.content)
    assert parsed["model"] == 'a"b\\c'


# --- NB3: RoleArtifact.path 상대경로 계약 ---

def test_role_artifact_rejects_absolute_path(tmp_path):
    # tmp_path 자체가 현재 플랫폼에서 항상 절대경로다(Windows에서 "/etc/passwd"는
    # 드라이브가 없어 pathlib 기준 절대경로가 아니므로 하드코딩하지 않는다).
    with pytest.raises(ValueError):
        RoleArtifact(path=tmp_path / "escape.toml", content="x")


def test_role_artifact_rejects_parent_traversal():
    with pytest.raises(ValueError):
        RoleArtifact(path=Path("../escape.toml"), content="x")


def test_role_artifact_accepts_plain_relative_path():
    RoleArtifact(path=Path("leader.config.toml"), content="x")  # no exception


def test_role_artifact_rejects_windows_root_relative_path():
    # PureWindowsPath로 플랫폼 무관하게 고정한다 — 현재 OS가 POSIX여도
    # "\evil.toml"의 anchor는 "\"(Windows 루트 상대 경로)라 거부돼야 한다.
    with pytest.raises(ValueError):
        RoleArtifact(path=PureWindowsPath("\\evil.toml"), content="x")


def test_role_artifact_rejects_windows_drive_relative_path():
    # "C:evil.toml"의 anchor는 "C:"(드라이브 상대 경로, 절대경로 아님) — 이것도
    # anchor가 있으므로 거부돼야 한다.
    with pytest.raises(ValueError):
        RoleArtifact(path=PureWindowsPath("C:evil.toml"), content="x")


def test_verify_role_provisioned_passes_when_materialized(tmp_path):
    a = CodexAdapter()
    role = ROLES["leader"]
    for artifact in a.role_artifacts(role, tmp_path):
        target = tmp_path / artifact.path
        # write_bytes로 정확한 바이트를 쓴다 — write_text(newline=None 기본)는
        # Windows에서 \n을 \r\n으로 번역해 NB1의 바이트 정확 비교와 어긋난다.
        target.write_bytes(artifact.content.encode("utf-8"))
    a.verify_role_provisioned(role, tmp_path)  # no exception


def test_verify_role_provisioned_fails_when_absent(tmp_path):
    a = CodexAdapter()
    with pytest.raises(RoleNotProvisioned):
        a.verify_role_provisioned(ROLES["leader"], tmp_path)


def test_verify_role_provisioned_fails_on_content_mismatch(tmp_path):
    a = CodexAdapter()
    role = ROLES["leader"]
    for artifact in a.role_artifacts(role, tmp_path):
        target = tmp_path / artifact.path
        target.write_bytes((artifact.content + "x").encode("utf-8"))
    with pytest.raises(RoleNotProvisioned):
        a.verify_role_provisioned(role, tmp_path)


def test_verify_role_provisioned_fails_when_target_is_directory(tmp_path):
    # NB1: exists() 대신 is_file() — 디렉터리면 다른 예외가 새지 않고
    # RoleNotProvisioned로 처리돼야 한다.
    a = CodexAdapter()
    role = ROLES["leader"]
    artifact = a.role_artifacts(role, tmp_path)[0]
    (tmp_path / artifact.path).mkdir(parents=True)
    with pytest.raises(RoleNotProvisioned):
        a.verify_role_provisioned(role, tmp_path)


def test_verify_role_provisioned_fails_on_crlf_vs_lf_mismatch(tmp_path):
    # NB1: read_bytes+decode는 universal-newline 정규화를 하지 않으므로 디스크의
    # CRLF와 명세(LF)가 다르면 통과시키지 않는다.
    a = CodexAdapter()
    role = ROLES["leader"]
    artifact = a.role_artifacts(role, tmp_path)[0]
    crlf_content = artifact.content.replace("\n", "\r\n")
    (tmp_path / artifact.path).write_bytes(crlf_content.encode("utf-8"))
    with pytest.raises(RoleNotProvisioned):
        a.verify_role_provisioned(role, tmp_path)


def test_verify_role_provisioned_fails_on_undecodable_bytes(tmp_path):
    # NB1: UnicodeDecodeError도 RoleNotProvisioned로 감싼다.
    a = CodexAdapter()
    role = ROLES["leader"]
    artifact = a.role_artifacts(role, tmp_path)[0]
    (tmp_path / artifact.path).write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(RoleNotProvisioned):
        a.verify_role_provisioned(role, tmp_path)


def test_claude_verify_role_provisioned_noop(tmp_path):
    a = ClaudeCodeAdapter()
    a.verify_role_provisioned(ROLES["leader"], tmp_path)  # no artifacts, no exception


# --- Round 1 재리뷰(Fable) 반영: OSError 읽기실패 통일 · 제어문자 전수 왕복 ---

def test_verify_role_provisioned_wraps_read_oserror(tmp_path, monkeypatch):
    # NB1: is_file()을 통과해도 read_bytes가 OSError(예: PermissionError)를 내면
    # RoleNotProvisioned로 통일한다(예외 타입 누출 방지).
    a = CodexAdapter()
    role = ROLES["leader"]
    artifact = a.role_artifacts(role, tmp_path)[0]
    (tmp_path / artifact.path).write_bytes(artifact.content.encode("utf-8"))

    def boom(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_bytes", boom)
    with pytest.raises(RoleNotProvisioned):
        a.verify_role_provisioned(role, tmp_path)


@pytest.mark.parametrize("code", list(range(0x20)) + [0x7f])
def test_toml_basic_string_roundtrips_all_control_chars(code):
    # C0 제어문자 전수(U+0000~U+001F) + DEL(U+007F)이 TOML 이스케이프로 나가
    # tomllib 왕복에서 원문이 보존되는지 — codex.py의 \uXXXX 폴백(특히 DEL 분기)
    # 회귀를 잡는다.
    ch = chr(code)
    literal = _toml_basic_string(ch)
    assert tomllib.loads(f"v = {literal}")["v"] == ch


def test_codex_artifact_root_falls_back_to_home_codex(tmp_path, monkeypatch):
    # env에 CODEX_HOME이 없으면 artifact_root는 ~/.codex를 쓴다(ADR-0017 위치 계약).
    # 이 폴백 분기가 깨지면 게이트가 -p가 실제 읽는 위치를 안 봐 fail-closed가 무너진다.
    a = CodexAdapter()
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    assert a.artifact_root(Path("/work/wt"), {}) == fake_home / ".codex"
