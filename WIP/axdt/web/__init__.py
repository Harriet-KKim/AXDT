"""Phase 7 — Local Web Server 브리핑(T1).

interim 파일(``progress.md``·``report/<task>.md``)을 읽기 전용으로 렌더링하는
로컬 웹 서버. 파싱은 ``axdt.progress.table``을 재사용하며 여기서 다시 구현하지
않는다. Python 표준 라이브러리만 사용한다(외부 의존성 없음).

공개 API: make_server(root, host, port) -> 서버 객체, main(argv) -> int(CLI 재노출).
"""
from __future__ import annotations

from axdt.web.server import make_server, main

__all__ = ["make_server", "main"]
