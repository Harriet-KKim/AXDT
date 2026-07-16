import re
from pathlib import Path

import pytest

from axdt.protocol import converge, message
from axdt.protocol.inject import InjectResult

TOKEN_RE = re.compile(r"^\[axdt:assign:[^:\]]+:[0-9a-f]{8}\]")


def test_render_assign_has_no_newline_or_tab():
    text = message.render_assign("w1.t1-auth-login", Path("plan/task/w1.t1-auth-login.md"))
    assert "\n" not in text
    assert "\t" not in text


def test_render_reject_has_no_newline_or_tab():
    text = message.render_reject("w1.t1-auth-login", "9336a25")
    assert "\n" not in text
    assert "\t" not in text


def test_render_note_has_no_newline_or_tab():
    text = message.render_note("free text note")
    assert "\n" not in text
    assert "\t" not in text


def test_token_format_matches_pattern():
    text = message.render_assign("w1.t1-auth-login", Path("plan/task/w1.t1-auth-login.md"))
    assert TOKEN_RE.match(text)


def test_token_hash8_is_lowercase_hex_of_length_8():
    tok = message.token("note", "-", "hello")
    m = re.match(r"^\[axdt:note:-:([0-9a-f]+)\]$", tok)
    assert m is not None
    assert len(m.group(1)) == 8


def test_token_deterministic_for_same_inputs():
    a = message.token("assign", "w1.t1", "body text")
    b = message.token("assign", "w1.t1", "body text")
    assert a == b


def test_token_hash8_differs_when_body_differs():
    a = message.token("assign", "w1.t1", "body text one")
    b = message.token("assign", "w1.t1", "body text two")
    assert a != b


def test_render_note_uses_dash_task():
    text = message.render_note("hello")
    assert text.startswith("[axdt:note:-:")


def test_render_note_rejects_newline():
    with pytest.raises(ValueError):
        message.render_note("line one\nline two")


def test_render_note_rejects_tab():
    with pytest.raises(ValueError):
        message.render_note("col1\tcol2")


def test_render_note_rejects_carriage_return():
    with pytest.raises(ValueError):
        message.render_note("a\rb")


def test_render_assign_renders_posix_path():
    # Path("docs/interim/plan/x.md")는 Windows에서 WindowsPath가 되어
    # str()이 "\"를 쓴다 — render_assign은 plan.as_posix()로 항상 "/"를 낸다.
    text = message.render_assign("w1.t1-auth-login", Path("docs/interim/plan/x.md"))
    assert "docs/interim/plan/x.md" in text
    assert "\\" not in text


def test_token_rejects_unknown_kind():
    with pytest.raises(ValueError):
        message.token("bogus", "w1.t1", "body")


def test_token_rejects_newline_in_task():
    with pytest.raises(ValueError):
        message.token("assign", "w1.t1\nbogus", "body")


def test_inject_result_has_five_members():
    assert {m.name for m in InjectResult} == {
        "SENT", "UNCONFIRMED", "DEFERRED", "UNAVAILABLE", "NEEDS_HUMAN",
    }


def test_converge_types_are_importable():
    # 스켈레톤 함수는 호출하지 않는다 — 본문이 NotImplementedError이므로
    # 여기서는 타입이 import 가능하고 인스턴스화할 수 있음만 확인한다.
    assert converge.Observation is not None
    assert converge.Instruction is not None
    assert converge.Blocker is not None


def test_converge_exports_rejecting_commit_and_rework_pushed():
    # §5 계약 함수 2개가 __all__에 실리고 실제로 정의돼 있는지만 확인한다
    # (본문은 스켈레톤이라 호출하지 않는다).
    assert "rejecting_commit" in converge.__all__
    assert "rework_pushed" in converge.__all__
    assert callable(converge.rejecting_commit)
    assert callable(converge.rework_pushed)
