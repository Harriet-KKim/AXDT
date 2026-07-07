"""통합 테스트(WSL2 옵트인) — 실 docker/tmux/git daemon로 1사이클.

기본 실행 제외(pyproject: addopts = -m 'not integration').
WSL2에서 `py -m pytest -m integration` 으로 옵트인 실행.
도구가 없으면 skip.
"""
import re
import shutil
import time

import pytest

from axdt.infra import config, leader, naming, tmux

pytestmark = pytest.mark.integration


def _require(tool: str):
    if shutil.which(tool) is None:
        pytest.skip(f"{tool} 없음 — 통합 테스트 skip")


@pytest.fixture
def tools():
    for t in ("docker", "tmux", "git"):
        _require(t)


def test_one_cycle_placeholder(tools, tmp_path, monkeypatch):
    """container build → leader up(provision 포함) → send → capture → down."""
    # canonical seed repo 생성(빈 커밋 + main 브랜치).
    from axdt.infra import proc
    canon = tmp_path / "canon"
    canon.mkdir()
    proc.run(["git", "init", "-b", "main", str(canon)])
    proc.run(["git", "-C", str(canon), "commit", "--allow-empty", "-m", "seed",
              "-c", "user.email=a@b.c", "-c", "user.name=axdt"])

    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.setenv("AXDT_HUB_TRANSPORT", "daemon")
    i = naming.parse("w1.t1-smoke")

    # 호스트 repo 루트(이미지 빌드 context는 현재 프로젝트의 WIP 사용)를 위해
    # build는 별도 보장: 현재 repo 루트에서 이미지 빌드.
    repo_root = config.project_root()
    from axdt.infra import container
    container.build_image(repo_root)

    be = leader.up(root, i, seed_from=canon)
    try:
        time.sleep(1.0)  # placeholder 기동 대기
        be.send_text("ping\n")
        deadline = time.time() + 10
        out = ""
        while time.time() < deadline:
            out += be.read_new_output()
            if re.search(r"received:\s*ping", out):
                break
            time.sleep(0.3)
        assert re.search(r"received:\s*ping", out), f"캡처 출력에 응답 없음:\n{out}"
    finally:
        leader.down(root, i, force=True)

    assert tmux.resolve_window(i) is None  # 정리 확인
