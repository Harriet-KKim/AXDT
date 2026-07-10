"""결정성(스펙 §7) — 같은 입력 = 같은 출력, line=null 우선 정렬."""
from __future__ import annotations

import json

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree


def _messy_tree(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = (
        docs["requirements/auth.md"]
        .replace("items: [FR-1]", "items: [FR-1, FR-9]")
        .replace(
            "- **FR-1** 사용자는 이메일로 로그인한다.",
            "- **FR-1** 사용자는 이메일로 로그인한다.\n- **FR-2** TBD 나중에 정리.",
        )
    )
    write_tree(tmp_path, docs)
    return tmp_path


def test_same_input_twice_yields_identical_output(tmp_path):
    root = _messy_tree(tmp_path)
    r1 = cli.run(root)
    r2 = cli.run(root)
    assert r1.violations == r2.violations
    assert r1.errors == r2.errors
    assert len(r1.violations) > 1
    assert json.dumps(cli.to_json(r1)) == json.dumps(cli.to_json(r2))


def test_violations_for_same_path_sort_null_line_before_real_line(tmp_path):
    root = _messy_tree(tmp_path)
    result = cli.run(root)
    same_path = [v.line for v in result.violations if v.path.endswith("requirements/auth.md")]

    none_positions = [i for i, ln in enumerate(same_path) if ln is None]
    real_positions = [i for i, ln in enumerate(same_path) if ln is not None]
    assert none_positions and real_positions
    assert max(none_positions) < min(real_positions)


def test_errors_sorted_by_path_then_code_then_message(tmp_path):
    docs = {
        "requirements/b.md": "본문만 있고 frontmatter 없음\n",
        "requirements/a.md": "---\nid: req-a\nid: req-a2\nitems: []\n---\n\n본문\n",
    }
    write_tree(tmp_path, docs)
    result = cli.run(tmp_path)
    paths = [e.path for e in result.errors]
    assert paths == sorted(paths)
