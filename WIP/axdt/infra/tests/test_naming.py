"""naming 모듈 — SoT 규칙 rule-branch-workspace-naming 강제 검증."""
from pathlib import Path

import pytest

from axdt.infra import naming
from axdt.infra.naming import Identifier, NamingError


# --- parse: 유효 식별자 ---

def test_parse_valid_identifier_extracts_parts():
    i = naming.parse("w3.t12-auth-login")
    assert i.wave == 3
    assert i.task == 12
    assert i.slug == "auth-login"


def test_value_roundtrips_parsed_identifier():
    assert naming.parse("w3.t12-auth-login").value == "w3.t12-auth-login"


def test_parse_single_word_slug():
    i = naming.parse("w1.t1-setup")
    assert (i.wave, i.task, i.slug) == (1, 1, "setup")


def test_parse_multi_digit_numbers():
    i = naming.parse("w10.t250-x")
    assert (i.wave, i.task) == (10, 250)


# --- parse: 무효 식별자 ---

@pytest.mark.parametrize("bad", [
    "w03.t12-auth",     # wave 선행 0
    "w3.t012-auth",     # task 선행 0
    "w0.t1-x",          # wave 0
    "w3.t0-x",          # task 0
    "w3/t12-auth",      # 슬래시
    "w3.t12-Auth",      # 대문자 slug
    "w3.t12-auth_login",  # 언더스코어
    "w3.t12-",          # 빈 slug
    "w3.t12",           # slug 없음
    "wa.tb-x",          # 숫자 아님
    "x3.t12-auth",      # w 접두 아님
    "w3.t12-auth-",     # trailing dash
    "w3.t12--auth",     # 연속 dash
    "axdt-w3.t12-auth",  # 렌더된 컨테이너명을 식별자로
    "",
])
def test_parse_rejects_invalid(bad):
    with pytest.raises(NamingError):
        naming.parse(bad)


# --- is_valid ---

def test_is_valid_true_for_good():
    assert naming.is_valid("w3.t12-auth-login") is True


def test_is_valid_false_for_bad():
    assert naming.is_valid("w03.t12-auth") is False


# --- validate ---

def test_validate_passes_silently_for_good():
    naming.validate("w3.t12-auth-login")  # no raise


def test_validate_raises_for_bad():
    with pytest.raises(NamingError):
        naming.validate("w3/t12-x")


# --- 렌더 헬퍼: 한 식별자가 모두를 구동 ---

def test_branch_equals_identifier():
    i = naming.parse("w3.t12-auth-login")
    assert naming.branch(i) == "w3.t12-auth-login"


def test_container_prefixes_axdt():
    i = naming.parse("w3.t12-auth-login")
    assert naming.container(i) == "axdt-w3.t12-auth-login"


def test_workspace_dir_under_workspaces():
    i = naming.parse("w3.t12-auth-login")
    assert naming.workspace_dir(i) == Path("workspaces") / "w3.t12-auth-login"


def test_tmux_window_equals_identifier():
    i = naming.parse("w3.t12-auth-login")
    assert naming.tmux_window(i) == "w3.t12-auth-login"


# --- Identifier 불변식 (직접 생성도 검증 통과해야) ---

def test_identifier_direct_construction_rejects_zero():
    with pytest.raises(NamingError):
        Identifier(wave=0, task=0, slug="x")


def test_identifier_direct_construction_rejects_bad_slug():
    with pytest.raises(NamingError):
        Identifier(wave=3, task=12, slug="Auth_Login")


def test_identifier_direct_construction_accepts_valid():
    i = Identifier(wave=3, task=12, slug="auth-login")
    assert i.value == "w3.t12-auth-login"
