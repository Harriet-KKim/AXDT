"""JudgmentKey, CompletenessSweepKey, FullBindingKey, normalize_finding_digest —
판정 키·완전성 스윕 키·완전 결속 키·digest 정규화(§2.2, §3).

normalize_finding_digest는 ②검토 CI와 컨트롤러가 반드시 같은 구현을 import하는 단일 정규화 함수다
(규칙 ②의 "검사기가 단일 구현으로 고정" 조항, §2.2). 마크다운 구조는 정규화하지 않는다.
"""
import hashlib
import re
import unicodedata
from dataclasses import dataclass

DIGEST_ALGO = "sha256"
DIGEST_VERSION = 2                     # 정규화·직렬화 규약 버전 — 바뀌면 digest도 바뀜
#   v2: 경계 보존 length-prefix 직렬화(v1의 단순 US join 충돌 제거).

_LEN_SEP = b"\x1f"                     # US (unit separator): length-prefix와 내용 사이 구분
_SPACE_TAB_RUN_RE = re.compile(r"[ \t]+")


@dataclass(frozen=True)
class JudgmentKey:
    """정합성 판정 키 — 4성분(규칙 §② 판정 키). 게이트는 비교만(성분 계산은 ② CI·컨트롤러).
    재사용·무효화·승인 stale의 결속 단위(정합성·공백 검토)."""
    tree_hash: str                     # (1) target-content projection 트리 해시
    rule_fingerprint: str              # (2) 적용 rule 지문
    review_policy_epoch: str           # (3) 검토 정책 epoch
    rule_catalog_manifest_digest: str  # (4) 규칙 카탈로그 manifest digest


@dataclass(frozen=True)
class CompletenessSweepKey:
    """선언 완전성 스윕 키 — 3성분(규칙 §② 완전성 스윕 키). 게이트는 비교만.
    재사용·무효화·승인 stale의 결속 단위(선언 완전성 검토)."""
    projection_tree_hash: str          # target-content projection 트리 해시(판정 키 (1)과 같은 입력)
    active_catalog_input_digest: str   # 활성 rule 카탈로그 본문 전량 digest(README·_TEMPLATE 제외)
    review_policy_epoch: str           # 검토 정책 epoch(판정 키 (3)과 같은 입력)


@dataclass(frozen=True)
class FullBindingKey:
    """해당 검토의 키(판정 키 또는 완전성 스윕 키) + (F-n + 내용 digest). finding 단위 대조 키.
    표시는 자기 검토의 키에만 결속한다 — 두 키 타입·값이 다르면 동등성이 성립하지 않아
    정합성 finding 결정이 완전성 finding을 닫지 못한다(교차 무효화 없음, 규칙 §②)."""
    review_key: "JudgmentKey | CompletenessSweepKey"
    finding_id: str                    # F-n
    content_digest: str                # 정규화 해시(§2.2)


def _normalize_text(s: str) -> str:
    """NFC -> 개행 LF 통일 -> 앞뒤 공백 제거 -> 연속 공백(스페이스·탭만) 1칸 축약. 개행은 보존."""
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.strip()
    s = _SPACE_TAB_RUN_RE.sub(" ", s)
    return s


def _frame(s: str) -> bytes:
    """조각을 length-prefix로 감싼다: `<utf8 바이트 길이>\x1f<utf8 바이트>`.
    내용에 0x1f가 들어와도 정확히 length 바이트만 읽으므로 경계가 주입에 무관하게 보존된다."""
    data = s.encode("utf-8")
    return str(len(data)).encode("ascii") + _LEN_SEP + data


def normalize_finding_digest(axis: str, refs: "tuple[str, ...]",
                             severity: str, body: str) -> str:
    """finding 내용 digest의 정규화 해시(§2.2). 결정적.
    유니코드 NFC -> 개행 LF 통일 -> 앞뒤 공백 제거·연속 공백 1칸 축약(대상은
    스페이스·탭만, 개행은 보존) -> refs 정렬(중복 제거) -> 각 필드·각 ref를 length-prefix로
    경계 보존 직렬화((DIGEST_VERSION, axis, refs 개수+refs, severity, body)) -> DIGEST_ALGO 해시.
    length-prefix라 필드/ref 값에 US(0x1f)가 섞여도 경계가 이동하지 않는다(v2). refs 개수를
    payload에 실어 `()` 와 `("",)`가 다른 digest를 낸다. 마크다운 구조는 정규화하지 않는다(§2.2).
    ② 검토 CI와 컨트롤러가 **이 함수 하나를 똑같이 import**한다(단일 구현, 규칙 ②)."""
    norm_axis = _normalize_text(axis)
    norm_severity = _normalize_text(severity)
    norm_body = _normalize_text(body)
    norm_refs = sorted(set(_normalize_text(r) for r in refs))

    payload = b"".join((
        _frame(str(DIGEST_VERSION)),
        _frame(norm_axis),
        _frame(str(len(norm_refs))),          # refs 개수(빈 튜플 vs 빈 문자열 ref 구분)
        *(_frame(r) for r in norm_refs),
        _frame(norm_severity),
        _frame(norm_body),
    ))
    return hashlib.new(DIGEST_ALGO, payload).hexdigest()
