"""CLI 계약(스펙 §6) — 종료코드 0/1/2, --json 스키마, 기본 경로."""
from __future__ import annotations

import json

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree


def test_exit_code_0_when_clean(tmp_path):
    write_tree(tmp_path, golden_docs())
    assert cli.main([str(tmp_path)]) == 0


def test_exit_code_1_when_only_violations(tmp_path):
    docs = golden_docs()
    del docs["requirements/auth.md"]
    write_tree(tmp_path, docs)
    assert cli.main([str(tmp_path)]) == 1


def test_exit_code_2_when_errors_present_even_with_violations(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = "본문만 있고 frontmatter 없음\n"
    write_tree(tmp_path, docs)
    assert cli.main([str(tmp_path)]) == 2


def test_json_schema_shape_and_keys(tmp_path, capsys):
    docs = golden_docs()
    del docs["requirements/auth.md"]
    write_tree(tmp_path, docs)

    code = cli.main([str(tmp_path), "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert payload["schema_version"] == 1
    assert payload["ok"] is False
    assert isinstance(payload["violations"], list) and payload["violations"]
    assert isinstance(payload["errors"], list)
    v = payload["violations"][0]
    assert set(v.keys()) == {"path", "line", "code", "message"}
    summary = payload["summary"]
    assert set(summary.keys()) == {"files", "violations", "errors", "by_code"}
    assert summary["violations"] == len(payload["violations"])
    assert summary["errors"] == len(payload["errors"])
    assert code == 1


def test_json_errors_shape_and_exit_code_2_on_malformed(tmp_path, capsys):
    docs = golden_docs()
    docs["requirements/auth.md"] = "본문만 있고 frontmatter 없음\n"
    write_tree(tmp_path, docs)

    code = cli.main([str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["ok"] is False
    assert isinstance(payload["errors"], list) and payload["errors"]
    e = payload["errors"][0]
    assert set(e.keys()) == {"path", "code", "message"}
    assert e["code"].startswith("E_")
    assert payload["summary"]["errors"] == len(payload["errors"])
    assert payload["summary"]["errors"] >= 1


def test_json_ok_true_and_errors_empty_on_clean_tree(tmp_path, capsys):
    write_tree(tmp_path, golden_docs())
    cli.main([str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "schema_version": 1,
        "ok": True,
        "violations": [],
        "errors": [],
        "summary": {"files": 3, "violations": 0, "errors": 0, "by_code": {}},
    }


def test_default_root_argument_is_docs_sot():
    args = cli.build_parser().parse_args([])
    assert args.path == "docs/sot"


def test_text_output_omits_line_for_file_level_violation(tmp_path, capsys):
    docs = golden_docs()
    del docs["requirements/auth.md"]
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c1 = next(v for v in result.violations if v.code == "C1")
    assert c1.line is None  # 전제 확인: 이 위반은 파일/디렉터리 수준(line 없음)

    cli.main([str(tmp_path)])
    out = capsys.readouterr().out

    # line 생략 포맷("경로 · 코드 · 메시지")과 완전히 일치하는 줄이 있어야 한다
    # (윈도우 절대경로의 드라이브 콜론(C:)과 혼동하지 않도록 문자열 비교로 검증).
    expected_line = f"{c1.path} · {c1.code} · {c1.message}"
    assert expected_line in out.splitlines()
