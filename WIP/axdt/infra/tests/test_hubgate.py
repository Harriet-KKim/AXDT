"""hubgate — pre-receive 판정 로직(ADR-0007 (a)+(b)) 단위 테스트.

spec §6.1a(:211-221) 각 조항의 독립 오라클: 테스트는 SoT/spec 문면이 정의한 동작을
검증하는 것이지, 구현을 베낀 미러가 아니다. glob 문법의 정본은 SoT 블록 헤더
(docs/sot/rule/protected-paths.md)이며, 여기 SAMPLE_PROTECTED_PATHS_MD는 그 문법으로
쓰인 예시 정책 텍스트다(실제 저장소 SoT 반영과 무관 — 파싱기 자체를 검증하기 위한 픽스처).
실제 git을 통한 end-to-end 통합(허브 push)은 test_hub.py(§6-G)가 맡는다.
"""
import io
import sys

import pytest

from axdt.infra import hubgate, proc

# --- 공용 픽스처 텍스트 ---

SAMPLE_PROTECTED_PATHS_MD = """# 보호 경로는 지정된 주체만 수정한다

본문 설명. deny docs/should/not/match 처럼 보이는 문장이 있어도 코드펜스 밖이면 무시된다.

```axdt-protected-paths
# task-push 축 정책(Phase 3 강제 집합, 파서 검증용 예시)
deny docs/sot/**
deny docs/interim/progress.md
deny docs/interim/plan/**
deny docs/interim/**/README.md

report-owns docs/interim/report
```

기타 설명 본문.

```axdt-critical-paths
critical docs/sot/rule/**
critical .github/workflows/**
```
"""

GOOD_POLICY_TEXT = (
    "```axdt-protected-paths\n"
    "deny docs/sot/**\n"
    "report-owns docs/interim/report\n"
    "```\n"
)


def _policy(*rules: tuple[str, str]) -> hubgate.Policy:
    return hubgate.Policy(rules=[hubgate.Rule(kind=k, arg=a) for k, a in rules])


# =====================================================================
# A. (a) 이식(spec:213)
# =====================================================================


def test_check_ref_allowlist_rejects_zero_sha_deletion():
    reason = hubgate.check_ref_allowlist(hubgate.ZERO_SHA, "refs/heads/w1.t2-cli")
    assert reason is not None


def test_check_ref_allowlist_rejects_sha256_zero_deletion():
    # F6: 삭제 판정은 해시 길이와 무관해야 한다(SHA-256 저장소는 64-제로).
    reason = hubgate.check_ref_allowlist("0" * 64, "refs/heads/w1.t2-cli")
    assert reason is not None


@pytest.mark.parametrize(
    "ref",
    [
        "refs/heads/main",
        "refs/heads/sot/x",
        "refs/tags/v1",
        "refs/heads/W1.t1-a",  # 대문자
        "refs/heads/w1.t1-",  # 빈 slug
        "refs/heads/w0.t1-a",  # wave 0
    ],
)
def test_check_ref_allowlist_rejects_non_task_refs(ref):
    reason = hubgate.check_ref_allowlist("a" * 40, ref)
    assert reason is not None


def test_check_ref_allowlist_passes_valid_task_ref():
    assert hubgate.check_ref_allowlist("a" * 40, "refs/heads/w1.t2-cli") is None


@pytest.mark.parametrize(
    "ident,valid",
    [
        ("w1.t2-cli", True),
        ("w10.t3-a-b", True),
        ("w0.t1-a", False),
        ("w1.t0-a", False),
        ("W1.t1-a", False),
        ("w1.t1-", False),
        ("w1.t1-A", False),
    ],
)
def test_allowed_ref_matches_naming(ident, valid):
    import axdt.infra.naming as naming

    assert naming.is_valid(ident) == valid
    assert (
        hubgate.check_ref_allowlist("a" * 40, f"refs/heads/{ident}") is None
    ) == valid


# =====================================================================
# B. 파서(spec:220)
# =====================================================================


def test_parse_policy_extracts_only_deny_and_report_owns_ignoring_comments_and_blanks():
    policy = hubgate.parse_policy(SAMPLE_PROTECTED_PATHS_MD)
    assert policy is not None
    assert [(r.kind, r.arg) for r in policy.rules] == [
        ("deny", "docs/sot/**"),
        ("deny", "docs/interim/progress.md"),
        ("deny", "docs/interim/plan/**"),
        ("deny", "docs/interim/**/README.md"),
        ("report-owns", "docs/interim/report"),
    ]


def test_parse_policy_ignores_critical_paths_block_lines():
    policy = hubgate.parse_policy(SAMPLE_PROTECTED_PATHS_MD)
    args = [r.arg for r in policy.rules]
    assert "docs/sot/rule/**" not in args
    assert ".github/workflows/**" not in args
    assert not any(r.kind == "critical" for r in policy.rules)


def test_parse_policy_ignores_prose_outside_fence():
    policy = hubgate.parse_policy(SAMPLE_PROTECTED_PATHS_MD)
    args = [r.arg for r in policy.rules]
    assert "docs/should/not/match" not in args


def test_parse_policy_returns_none_when_fence_absent():
    assert hubgate.parse_policy("# no policy fence\njust prose text\n") is None


def test_parse_policy_raises_on_unknown_directive():
    text = "```axdt-protected-paths\nallow docs/x\n```\n"
    with pytest.raises(hubgate.PolicyParseError):
        hubgate.parse_policy(text)


def test_parse_policy_raises_on_malformed_line_missing_arg():
    text = "```axdt-protected-paths\ndeny\n```\n"
    with pytest.raises(hubgate.PolicyParseError):
        hubgate.parse_policy(text)


def test_parse_policy_raises_on_unterminated_fence():
    text = "```axdt-protected-paths\ndeny docs/x\n"
    with pytest.raises(hubgate.PolicyParseError):
        hubgate.parse_policy(text)


# =====================================================================
# C. glob(spec:218) — 정본은 SoT 블록 헤더, 여기는 검증자
# =====================================================================


@pytest.mark.parametrize("path", ["docs/sot/x", "docs/sot/a/b.md"])
def test_glob_trailing_double_star_matches(path):
    assert hubgate.match_glob("docs/sot/**", path)


@pytest.mark.parametrize("path", ["docs/sotx", "docs/other/y"])
def test_glob_trailing_double_star_respects_segment_boundary(path):
    assert not hubgate.match_glob("docs/sot/**", path)


@pytest.mark.parametrize(
    "path",
    [
        "docs/interim/README.md",  # 0 세그먼트(경계 사례)
        "docs/interim/a/README.md",  # 1 세그먼트
        "docs/interim/a/b/README.md",  # 2 세그먼트
    ],
)
def test_glob_middle_double_star_matches_zero_or_more_segments(path):
    assert hubgate.match_glob("docs/interim/**/README.md", path)


@pytest.mark.parametrize("path", ["docs/interim/READMEx.md", "docs/README.md"])
def test_glob_middle_double_star_respects_segment_boundary(path):
    assert not hubgate.match_glob("docs/interim/**/README.md", path)


def test_glob_trailing_double_star_plan_dir():
    assert hubgate.match_glob("docs/interim/plan/**", "docs/interim/plan/w1.md")
    assert not hubgate.match_glob("docs/interim/plan/**", "docs/interim/planx")


def test_glob_root_literal_readme_matches_only_root():
    assert hubgate.match_glob("README.md", "README.md")
    assert not hubgate.match_glob("README.md", "docs/README.md")
    assert not hubgate.match_glob("README.md", "sub/README.md")


def test_glob_root_literal_dotfile_matches_only_root():
    assert hubgate.match_glob(".gitignore", ".gitignore")
    assert not hubgate.match_glob(".gitignore", "sub/.gitignore")


@pytest.mark.parametrize("path", ["foo", "a/foo", "a/b/foo"])
def test_glob_leading_double_star(path):
    # F9: 선행 "**"는 뒤따르는 리터럴 앞에 0개 이상 세그먼트를 허용해야 한다.
    assert hubgate.match_glob("**/foo", path)


def test_glob_single_star_does_not_cross_separator():
    # F9: 단일 "*"는 한 세그먼트 내에서만(구분자 넘어가지 않고) 매칭해야 한다.
    assert hubgate.match_glob("docs/*", "docs/a")
    assert not hubgate.match_glob("docs/*", "docs/a/b")


@pytest.mark.parametrize("path", ["a", "a/b", "docs/sot/x", "a\nb", "a/b\nc"])
def test_glob_whole_double_star_matches_anything_including_newline(path):
    # R4/spec:218: 패턴 전체가 "**"면 어떤 경로든(구분자·개행 포함) 매칭해야 한다.
    # git 경로에 개행이 들어갈 수 있는데(diff -z가 raw 전달), `.*`는 개행을 빠뜨려
    # bare `deny **` 전면 차단이 개행 포함 경로를 비껴가는 갭이 있었다.
    assert hubgate.match_glob("**", path)


# =====================================================================
# D. report-owns(spec:217)
# =====================================================================


def test_report_owns_allows_own_identifier_report():
    policy = _policy(("report-owns", "docs/interim/report"))
    assert not hubgate.is_path_denied(
        "docs/interim/report/w1.t2-cli.md", policy, "w1.t2-cli"
    )


def test_report_owns_denies_other_task_identifier():
    policy = _policy(("report-owns", "docs/interim/report"))
    assert hubgate.is_path_denied(
        "docs/interim/report/w1.t3-x.md", policy, "w1.t2-cli"
    )


def test_report_owns_denies_subdirectory_under_owned_dir():
    policy = _policy(("report-owns", "docs/interim/report"))
    assert hubgate.is_path_denied(
        "docs/interim/report/w1.t2-cli/sub.md", policy, "w1.t2-cli"
    )


def test_report_owns_denies_filename_missing_slug():
    policy = _policy(("report-owns", "docs/interim/report"))
    assert hubgate.is_path_denied(
        "docs/interim/report/w1.t2.md", policy, "w1.t2-cli"
    )


def test_report_owns_irrelevant_outside_owned_dir():
    policy = _policy(("report-owns", "docs/interim/report"))
    assert not hubgate.is_path_denied("docs/other/file.md", policy, "w1.t2-cli")


def test_report_owns_denies_dir_itself_as_file():
    # F5/spec:217: "<dir> 아래 변경은 <dir>/w<n>.t<n>-<slug>.md만 허용" — <dir> 자체가
    # (디렉터리가 아니라) 파일로 대체되는 변경도 거부돼야 한다.
    policy = _policy(("report-owns", "docs/interim/report"))
    assert hubgate.is_path_denied(
        "docs/interim/report", policy, "w1.t2-cli"
    )


# =====================================================================
# E. 논리곱·deny 우선(spec:217)
# =====================================================================


def test_deny_overrides_report_owns_allow_on_same_path():
    # 인위적 정책: report-owns만 보면 자기 식별자 report라 허용되겠지만, deny가 같은
    # 경로를 명시 거부하면 전체 거부(deny 최우선).
    policy = _policy(
        ("deny", "docs/interim/report/w1.t2-cli.md"),
        ("report-owns", "docs/interim/report"),
    )
    assert hubgate.is_path_denied(
        "docs/interim/report/w1.t2-cli.md", policy, "w1.t2-cli"
    )


# =====================================================================
# F. 판정순서·fail-closed(spec:215-216·221) — check_update, fake_proc로 git 모킹
# =====================================================================

_OLD = "0" * 40
_NEW = "a" * 40
_TASK_REF = "refs/heads/w1.t2-cli"


def _make_handler(
    *,
    main_exists=True,
    show_ref_rc=None,
    blob_exists=True,
    ls_tree_rc=0,
    show_rc=0,
    policy_text=GOOD_POLICY_TEXT,
    merge_base_rc=0,
    diff_rc=0,
    changed=(),
):
    """git 호출을 argv 내용으로 구분하는 통합 핸들러 팩토리(F2).

    주의: ``"show-ref" in argv``는 원소가 통짜 ``"show-ref"``라 ``"show" in argv``엔
    안 걸린다 — 순서(show-ref → ls-tree → merge-base → diff → show)로 먼저 매칭.
    ``show_ref_rc``/``ls_tree_rc``는 부재(skip)와 조회 오류(fail-closed)를 exit code로
    구분하는 R3-1 케이스용 — 지정 없으면 ``main_exists``/``blob_exists``의 기존
    이진(존재/부재) 의미로 폴백한다.
    """

    def handler(argv, kw):
        if "show-ref" in argv:
            rc = show_ref_rc if show_ref_rc is not None else (0 if main_exists else 1)
            return proc.ProcResult(argv, rc, "", "")
        if "ls-tree" in argv:
            if ls_tree_rc != 0:
                return proc.ProcResult(argv, ls_tree_rc, "", "fatal")
            out = "100644 blob abc\tpath\n" if blob_exists else ""
            return proc.ProcResult(argv, 0, out, "")
        if "merge-base" in argv:
            if merge_base_rc != 0:
                return proc.ProcResult(argv, merge_base_rc, "", "no common ancestor")
            return proc.ProcResult(argv, 0, "deadbeef" * 5 + "\n", "")
        if "diff" in argv:
            if diff_rc != 0:
                return proc.ProcResult(argv, diff_rc, "", "diff failed")
            payload = "".join(p + "\0" for p in changed)
            return proc.ProcResult(argv, 0, payload, "")
        if "show" in argv:
            return proc.ProcResult(
                argv, show_rc, policy_text if show_rc == 0 else "", "boom" if show_rc else ""
            )
        raise AssertionError(f"unexpected git call: {argv}")

    return handler


def test_check_update_skips_b_when_main_absent(tmp_path, fake_proc):
    # show-ref rc=1(git 계약상 "부재") → skip(전환기, spec:221).
    fake_proc.handler = _make_handler(main_exists=False)
    assert hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF) is None


def test_check_update_fails_closed_when_show_ref_errors(tmp_path, fake_proc):
    # R3-1: show-ref가 rc=1(부재)이 아니라 그 외 비영(repo/ref 조회 오류)로 죽으면
    # fail-open(skip)이 아니라 fail-closed여야 한다(spec:216).
    fake_proc.handler = _make_handler(show_ref_rc=128)
    reason = hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF)
    assert reason is not None


def test_check_update_skips_b_when_policy_blob_absent(tmp_path, fake_proc):
    # ls-tree rc=0 & 빈 출력("부재") → skip(전환기, spec:221).
    fake_proc.handler = _make_handler(blob_exists=False)
    assert hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF) is None


def test_check_update_fails_closed_when_ls_tree_errors(tmp_path, fake_proc):
    # R3-1: ls-tree가 비영(rc!=0)으로 죽으면(부재가 아니라 조회 오류) fail-closed.
    fake_proc.handler = _make_handler(ls_tree_rc=128)
    reason = hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF)
    assert reason is not None


def test_check_update_fails_closed_when_policy_read_fails(tmp_path, fake_proc):
    # 신규 핵심(F2): main·파일은 존재(부재가 아님)하는데 git show 자체가 실패
    # (객체 손상 등) — 예전엔 이것도 None(스킵/fail-open)으로 뭉개졌다.
    fake_proc.handler = _make_handler(show_rc=128)
    reason = hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF)
    assert reason is not None


def test_check_update_skips_b_when_fence_absent(tmp_path, fake_proc):
    fake_proc.handler = _make_handler(policy_text="# no block\n")
    assert hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF) is None


def test_check_update_fails_closed_on_policy_parse_error(tmp_path, fake_proc):
    fake_proc.handler = _make_handler(
        policy_text="```axdt-protected-paths\nallow docs/x\n```\n"
    )
    reason = hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF)
    assert reason is not None


def test_check_update_fails_closed_when_merge_base_missing(tmp_path, fake_proc):
    fake_proc.handler = _make_handler(merge_base_rc=1)
    reason = hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF)
    assert reason is not None


def test_check_update_fails_closed_when_diff_collect_fails(tmp_path, fake_proc):
    # F9/M4: diff 수집 실패도 fail-closed여야 한다.
    fake_proc.handler = _make_handler(diff_rc=1)
    reason = hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF)
    assert reason is not None


def test_check_update_passes_when_protected_paths_untouched(tmp_path, fake_proc):
    fake_proc.handler = _make_handler(changed=["src/main.py", "test/test_x.py"])
    assert hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF) is None


def test_check_update_rejects_when_protected_path_touched(tmp_path, fake_proc):
    fake_proc.handler = _make_handler(changed=["docs/sot/x"])
    reason = hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF)
    assert reason is not None


def test_check_update_rejects_before_any_git_call_when_ref_invalid(tmp_path, fake_proc):
    # (a)에서 이미 거부되면 (b) git 조회는 전혀 발생하지 않아야 한다(판정순서).
    def _no_calls_allowed(argv, kw):
        raise AssertionError(f"(a) 거부 후에는 git을 호출하면 안 됨: {argv}")

    fake_proc.handler = _no_calls_allowed
    reason = hubgate.check_update(tmp_path, _OLD, _NEW, "refs/heads/main")
    assert reason is not None


def test_merge_base_uses_fully_qualified_main_ref(tmp_path, fake_proc):
    # F3: ADR-0007:29,63 — 정책은 신뢰 ref(refs/heads/main)에서만 읽는다. merge-base도
    # 짧은 "main"이 아니라 완전지정 refs/heads/main을 써야 refs/tags/main 오조회를 피한다.
    seen_argv = {}
    inner = _make_handler(changed=[])

    def handler(argv, kw):
        if "merge-base" in argv:
            seen_argv["argv"] = argv
        return inner(argv, kw)

    fake_proc.handler = handler
    assert hubgate.check_update(tmp_path, _OLD, _NEW, _TASK_REF) is None
    assert hubgate._POLICY_REF in seen_argv["argv"]
    assert "main" not in seen_argv["argv"]  # 짧은 "main" 원소로 호출하면 안 됨


# =====================================================================
# 엔트리(main) — stdin 루프·exit code·ASCII stderr
# =====================================================================


def test_main_rejects_when_any_update_violates(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"{_OLD} {_NEW} refs/heads/main\n"))
    rc = hubgate.main([str(tmp_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "AXDT hub" in captured.err
    assert captured.err.isascii()


def test_main_stderr_ascii_when_ref_is_non_ascii(monkeypatch, tmp_path, capsys):
    # (a)에서 이미 거부되는 비ASCII ref(naming 패턴 불일치) — F2 이후에도 git 호출
    # 없이 (a)에서 거부되므로 fake_proc 불필요.
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(f"{_OLD} {_NEW} refs/heads/한글\n")
    )
    rc = hubgate.main([str(tmp_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.isascii()


def test_main_stderr_ascii_when_denied_path_is_non_ascii(monkeypatch, tmp_path, fake_proc, capsys):
    # (b) 거부 사유에 비ASCII 경로(spec:219가 -z로 raw하게 받는 그 경로)가 실려도
    # stderr는 ASCII로 정규화돼야 한다(spec:212).
    fake_proc.handler = _make_handler(changed=["docs/sot/한글.md"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"{_OLD} {_NEW} {_TASK_REF}\n"))
    rc = hubgate.main([str(tmp_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.isascii()


def test_main_stderr_escapes_control_chars_in_path(monkeypatch, tmp_path, fake_proc, capsys):
    # R3-2: 거부 사유에 실린 raw 경로(diff -z가 넘긴 그대로)가 개행을 포함하면
    # backslashreplace(비ASCII 전용)는 통과시킨다 — 개행이 그대로 stderr에 실리면
    # 가짜 "AXDT hub: ..." 줄을 위조할 수 있다. ASCII 제어문자도 escape해야 막힌다.
    fake_proc.handler = _make_handler(changed=["docs/sot/a\nAXDT hub: fake"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"{_OLD} {_NEW} {_TASK_REF}\n"))
    rc = hubgate.main([str(tmp_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.isascii()
    assert captured.err.rstrip("\n").count("\n") == 0
    assert "\\x0a" in captured.err


def test_main_accepts_when_all_updates_pass(monkeypatch, tmp_path, fake_proc):
    fake_proc.handler = _make_handler(main_exists=False)  # (b) skip, (a)만 통과
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"{_OLD} {_NEW} {_TASK_REF}\n"))
    rc = hubgate.main([str(tmp_path)])
    assert rc == 0


def test_main_requires_exactly_one_argv():
    rc = hubgate.main([])
    assert rc == 1


def test_main_handles_malformed_line(monkeypatch, tmp_path, capsys):
    # F8: stdin 줄이 "<old> <new> <ref>" 3필드가 아니면(공백 부족) traceback 없이
    # 정상적으로 거부(rc==1)하고 ASCII stderr를 낸다.
    monkeypatch.setattr(sys, "stdin", io.StringIO("only two\n"))
    rc = hubgate.main([str(tmp_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.isascii()


def test_main_processes_multiple_lines_and_skips_blank(monkeypatch, tmp_path, fake_proc, capsys):
    # F9: 여러 줄 + 빈 줄 혼합 stdin — 빈 줄은 무시되고, 각 유효한 줄은 독립 판정된다.
    fake_proc.handler = _make_handler(main_exists=False)  # (b) skip, (a)만 관여
    lines = "\n".join(
        [
            f"{_OLD} {_NEW} {_TASK_REF}",  # 통과
            "",  # 빈 줄 — 무시돼야 함
            f"{_OLD} {_NEW} refs/heads/main",  # (a) 거부
        ]
    ) + "\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(lines))
    rc = hubgate.main([str(tmp_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.count("AXDT hub") == 1  # 통과 줄은 사유 출력 없음, 거부 줄만 1건
