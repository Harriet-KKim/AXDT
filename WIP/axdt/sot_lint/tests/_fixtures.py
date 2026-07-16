"""테스트 전용 헬퍼 — 위반 0인 골든 SoT 트리와 파일 쓰기 유틸.

`test_` 접두가 아니라 pytest가 테스트 모듈로 수집하지 않는다.
"""
from __future__ import annotations

from pathlib import Path

REQ_AUTH = """---
id: req-auth
title: 인증 요구
items: [FR-1]
related: []
rules: []
---

# 인증 요구

## 기능 요구
- **FR-1** 사용자는 이메일로 로그인한다.

## 수용 기준
- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.
"""

SPEC_AUTH = """---
id: spec-auth
title: 인증 사양
items: [SP-1]
related: []
covers: [FR-1]
rules: []
---

# 인증 사양

## 구성요소
- **SP-1** 로그인 API 엔드포인트.

## 수용 기준
- [ ] **SP-1** POST /login이 200과 토큰을 반환한다.
"""

TD_AUTH = """---
id: td-auth
title: 인증 테스트 설계
items: [TD-1]
related: []
covers: [FR-1, SP-1]
rules: []
---

# 인증 테스트 설계

## 테스트 조건
- **TD-1** 올바른 자격증명으로 로그인하면 세션이 발급된다.

## 추적성
- **FR-1 / SP-1** ← **TD-1**

## 수용 기준
- [ ] **TD-1** 응답에 세션 토큰이 포함됨을 관찰한다.
"""


def golden_docs() -> dict[str, str]:
    """3종 각 1문서, 상호 covers·items가 전부 맞아떨어지는 위반 0 트리."""
    return {
        "requirements/auth.md": REQ_AUTH,
        "specification/auth.md": SPEC_AUTH,
        "test-design/auth.md": TD_AUTH,
    }


def write_tree(root: Path, docs: dict[str, str]) -> Path:
    for rel, text in docs.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root
