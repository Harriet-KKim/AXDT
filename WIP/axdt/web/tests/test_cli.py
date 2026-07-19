"""CLI 인자 파싱(build_parser) 계약 검증. 서버를 실제로 구동하지는 않는다."""
from __future__ import annotations

import pytest

from axdt.web.server import build_parser


def test_defaults():
    args = build_parser().parse_args([])
    assert args.root == "docs/interim"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_overrides():
    args = build_parser().parse_args(
        ["--root", "some/other/interim", "--host", "0.0.0.0", "--port", "9000"]
    )
    assert args.root == "some/other/interim"
    assert args.host == "0.0.0.0"
    assert args.port == 9000


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "--root" in out
    assert "--host" in out
    assert "--port" in out
