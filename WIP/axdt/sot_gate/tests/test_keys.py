"""Tests for sot_gate.keys — JudgmentKey/FullBindingKey and normalize_finding_digest (§2.2, §3, §6 test_keys)."""
import dataclasses

import pytest

from axdt.sot_gate.keys import (
    JudgmentKey,
    FullBindingKey,
    normalize_finding_digest,
    DIGEST_ALGO,
    DIGEST_VERSION,
)


class TestJudgmentKeyFrozen:
    def test_frozen(self):
        k = JudgmentKey(tree_hash="t1", rule_fingerprint="r1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            k.tree_hash = "t2"

    def test_equality(self):
        assert JudgmentKey("t1", "r1") == JudgmentKey("t1", "r1")
        assert JudgmentKey("t1", "r1") != JudgmentKey("t1", "r2")
        assert JudgmentKey("t1", "r1") != JudgmentKey("t2", "r1")

    def test_hashable(self):
        # frozen dataclasses are hashable by default -> usable as dict/set keys
        s = {JudgmentKey("t1", "r1"), JudgmentKey("t1", "r1")}
        assert len(s) == 1


class TestFullBindingKeyFrozen:
    def test_frozen(self):
        j = JudgmentKey("t1", "r1")
        k = FullBindingKey(judgment=j, finding_id="F-1", content_digest="d1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            k.finding_id = "F-2"

    def test_equality(self):
        j = JudgmentKey("t1", "r1")
        a = FullBindingKey(judgment=j, finding_id="F-1", content_digest="d1")
        b = FullBindingKey(judgment=JudgmentKey("t1", "r1"), finding_id="F-1", content_digest="d1")
        c = FullBindingKey(judgment=j, finding_id="F-2", content_digest="d1")
        d = FullBindingKey(judgment=j, finding_id="F-1", content_digest="d2")
        assert a == b
        assert a != c
        assert a != d


class TestNormalizeFindingDigestConstants:
    def test_digest_algo_is_sha256(self):
        assert DIGEST_ALGO == "sha256"

    def test_digest_version_is_2(self):
        # A1: 경계 보존 canonical serialization으로 규약이 바뀌어 1 -> 2.
        assert DIGEST_VERSION == 2


class TestNormalizeFindingDigestDeterminism:
    """공백/항목순서/NFC/개행(CRLF<->LF) 변형이 같은 digest를 낸다(§2.2)."""

    def test_extra_internal_whitespace_same_digest(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1", "ref-2"), "high", "hello world")
        d2 = normalize_finding_digest("axis-a", ("ref-1", "ref-2"), "high", "hello    world")
        assert d1 == d2

    def test_tabs_collapse_same_digest(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "hello world")
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "high", "hello\t\tworld")
        assert d1 == d2

    def test_leading_trailing_whitespace_same_digest(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "hello world")
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "high", "  hello world  \n")
        assert d1 == d2

    def test_ref_order_same_digest(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1", "ref-2"), "high", "body")
        d2 = normalize_finding_digest("axis-a", ("ref-2", "ref-1"), "high", "body")
        assert d1 == d2

    def test_ref_duplicates_collapse_same_digest(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1", "ref-2"), "high", "body")
        d2 = normalize_finding_digest("axis-a", ("ref-1", "ref-1", "ref-2"), "high", "body")
        assert d1 == d2

    def test_unicode_nfc_same_digest(self):
        # "e" + combining acute (NFD) vs precomposed "é" (NFC) must normalize to the same digest.
        nfd_body = "café"   # cafe + combining acute -> "café" (NFD)
        nfc_body = "café"          # café (NFC)
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", nfd_body)
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "high", nfc_body)
        assert d1 == d2

    def test_crlf_lf_same_digest(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "line1\r\nline2")
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "high", "line1\nline2")
        assert d1 == d2

    def test_cr_only_same_digest(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "line1\rline2")
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "high", "line1\nline2")
        assert d1 == d2

    def test_newline_not_collapsed(self):
        # newlines themselves are preserved, not squashed into a single space -> different from single-line variant
        d_multiline = normalize_finding_digest("axis-a", ("ref-1",), "high", "line1\nline2")
        d_oneline = normalize_finding_digest("axis-a", ("ref-1",), "high", "line1 line2")
        assert d_multiline != d_oneline

    def test_indentation_depth_collapses_to_single_space(self):
        # B4/m4: 줄 안의 연속 공백(들여쓰기 깊이)은 1칸으로 축약된다 — 코드블록 4칸 ≡ 문단 1칸.
        # 스펙 §2.2가 감수한 트레이드오프임을 회귀 방지로 못박는다(개행은 보존).
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "line1\n    line2")
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "high", "line1\n line2")
        assert d1 == d2


class TestNormalizeFindingDigestDistinctness:
    """축·참조·심각도·본문이 다르면 다른 digest."""

    def test_different_axis(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "body")
        d2 = normalize_finding_digest("axis-b", ("ref-1",), "high", "body")
        assert d1 != d2

    def test_different_refs(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "body")
        d2 = normalize_finding_digest("axis-a", ("ref-2",), "high", "body")
        assert d1 != d2

    def test_different_severity(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "body")
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "low", "body")
        assert d1 != d2

    def test_different_body(self):
        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "body one")
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "high", "body two")
        assert d1 != d2


class TestNormalizeFindingDigestVersion:
    def test_digest_version_change_changes_digest(self, monkeypatch):
        import axdt.sot_gate.keys as keys_mod

        d1 = normalize_finding_digest("axis-a", ("ref-1",), "high", "body")
        monkeypatch.setattr(keys_mod, "DIGEST_VERSION", 99)
        d2 = normalize_finding_digest("axis-a", ("ref-1",), "high", "body")
        assert d1 != d2


class TestNormalizeFindingDigestBoundaryPreserving:
    """A1: 필드 구분자(US 0x1f) 재사용 충돌 방지 — 경계 보존 canonical serialization.
    아래 쌍들은 이전 구현(순수 US join)에서 같은 digest로 충돌했다. 서로 달라야 한다."""

    def test_refs_split_vs_joined_differ(self):
        # refs=("a","b") 와 refs=("a\x1fb",) 는 서로 다른 digest여야 한다(refs 경계).
        d1 = normalize_finding_digest("axis-a", ("a", "b"), "high", "body")
        d2 = normalize_finding_digest("axis-a", ("a\x1fb",), "high", "body")
        assert d1 != d2

    def test_field_boundary_injection_differ(self):
        # ("ax",("r\x1fs",),"b","X")  vs  ("ax",("r",),"s","b\x1fX")
        # 이전엔 payload가 "…ax\x1fr\x1fs\x1fb\x1fX"로 동일했다.
        d1 = normalize_finding_digest("ax", ("r\x1fs",), "b", "X")
        d2 = normalize_finding_digest("ax", ("r",), "s", "b\x1fX")
        assert d1 != d2

    def test_empty_refs_tuple_differs_from_empty_string_ref(self):
        # refs=() 와 refs=("",) 는 원소 개수가 다르므로 다른 digest여야 한다.
        d1 = normalize_finding_digest("axis-a", (), "high", "body")
        d2 = normalize_finding_digest("axis-a", ("",), "high", "body")
        assert d1 != d2

    def test_whitespace_only_ref_normalizes_to_empty_string_ref(self):
        # ("  ",) 는 정규화(strip)로 ("",)와 같아진다 — 이건 같은 digest가 맞다(브리프 A1).
        d1 = normalize_finding_digest("axis-a", ("  ",), "high", "body")
        d2 = normalize_finding_digest("axis-a", ("",), "high", "body")
        assert d1 == d2


class TestNormalizeFindingDigestReturnType:
    def test_returns_hexdigest_string(self):
        d = normalize_finding_digest("axis-a", ("ref-1",), "high", "body")
        assert isinstance(d, str)
        assert len(d) == 64  # sha256 hexdigest length
        int(d, 16)  # must be valid hex


class TestNormalizeFindingDigestKnownAnswer:
    """T2: v2 payload 규약을 known-answer(골든)로 고정한다.
    _frame이 문자 수(len(s))가 아니라 **UTF-8 바이트 길이**(len(data))를 쓰고, refs 개수
    프레임이 존재함을 절대값으로 못박는다. 어느 하나라도 mutation되면 payload 바이트가 바뀌어
    아래 golden hexdigest가 달라진다 -> DIGEST_VERSION bump 없는 무단 포맷 드리프트를 잡는다.
    (골든 값은 DIGEST_VERSION=2 현재 구현으로 산출. 규약이 정당히 바뀌면 버전과 함께 갱신한다.)"""

    def test_golden_multibyte(self):
        # 멀티바이트 axis·body(char 수 != byte 수) + refs 2개(개수 프레임).
        digest = normalize_finding_digest("교차정합성", ("R-1", "T-2"), "blocking", "본문 é 텍스트")
        assert digest == "be7139721d901f4e424315e3b3fd262a733a575353c65d21bd96cc12df468651"

    def test_golden_multibyte_axis_empty_refs(self):
        # "é"는 1 char / 2 byte — byte-length 프레임을 드러낸다. refs=() (개수 0 프레임).
        digest = normalize_finding_digest("é", (), "s", "b")
        assert digest == "84f25bede2c0e0166da3f9585a35d6c93ecc84a25cf47f66f49084d1c6e9de09"
