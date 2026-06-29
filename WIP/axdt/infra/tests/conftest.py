"""테스트 공용 픽스처 — proc.run 가로채기(외부 도구 없이 argv 검증)."""
import pytest

from axdt.infra import proc


class FakeProc:
    """proc.run 대체. argv 기록 + 테스트가 출력/에러를 프로그램."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.kwargs: list[dict] = []
        # 기본: 빈 성공. 테스트가 handler를 바꿔 stdout/에러를 지정.
        self.handler = lambda argv, kw: proc.ProcResult(argv, 0, "", "")

    def __call__(self, argv, **kw):
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        self.kwargs.append(kw)
        return self.handler(argv, kw)

    def last(self) -> list[str]:
        return self.calls[-1]

    def find(self, *needles: str) -> list[str] | None:
        """모든 needle을 포함하는 첫 호출 argv를 반환."""
        for argv in self.calls:
            joined = " ".join(argv)
            if all(n in joined for n in needles):
                return argv
        return None


@pytest.fixture
def fake_proc(monkeypatch):
    fp = FakeProc()
    monkeypatch.setattr(proc, "run", fp)
    return fp
