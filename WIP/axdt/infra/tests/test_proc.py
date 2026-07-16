"""proc 모듈 — subprocess 공통 래퍼. 실제 자식 프로세스로 검증(목 없음).

sys.executable(실 Python)을 호출해 결정적·크로스플랫폼으로 동작을 고정한다.
"""
import sys

import pytest

from axdt.infra import proc
from axdt.infra.proc import ProcError


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_run_returns_stdout_on_success():
    r = proc.run(_py("print('ok')"))
    assert r.stdout.strip() == "ok"
    assert r.returncode == 0


def test_run_captures_stderr():
    r = proc.run(
        _py("import sys; sys.stderr.write('boom')"), check=False
    )
    assert "boom" in r.stderr


def test_run_raises_procerror_on_nonzero_when_check():
    with pytest.raises(ProcError) as ei:
        proc.run(_py("import sys; sys.exit(3)"))
    assert ei.value.returncode == 3


def test_run_no_raise_when_check_false():
    r = proc.run(_py("import sys; sys.exit(3)"), check=False)
    assert r.returncode == 3


def test_procerror_carries_argv_and_stderr():
    with pytest.raises(ProcError) as ei:
        proc.run(_py("import sys; sys.stderr.write('xyz'); sys.exit(1)"))
    err = ei.value
    assert err.argv[0] == sys.executable
    assert "xyz" in err.stderr


def test_run_honors_cwd(tmp_path):
    r = proc.run(_py("import os; print(os.getcwd())"), cwd=tmp_path)
    # realpath 비교: macOS /var→/private/var 등 심볼릭 차이 회피
    import os
    assert os.path.realpath(r.stdout.strip()) == os.path.realpath(str(tmp_path))


def test_run_env_overlays_os_environ():
    r = proc.run(
        _py("import os; print(os.environ.get('AXDT_TEST_VAR', 'MISSING'))"),
        env={"AXDT_TEST_VAR": "hello"},
    )
    assert r.stdout.strip() == "hello"


def test_run_env_keeps_base_environment():
    # 부분 env를 줘도 PATH 등 기존 환경은 유지되어 인터프리터가 뜬다.
    r = proc.run(
        _py("import os; print('PATH' in os.environ)"),
        env={"AXDT_TEST_VAR": "x"},
    )
    assert r.stdout.strip() == "True"


def test_run_timeout_converts_to_procerror():
    # timeout 초과 시 subprocess.TimeoutExpired를 ProcError(returncode=-1,
    # stderr="timeout")로 변환한다(check와 무관, R8 중대1).
    with pytest.raises(ProcError) as ei:
        proc.run(_py("import time; time.sleep(5)"), timeout=0.3)
    assert ei.value.returncode == -1
    assert ei.value.stderr == "timeout"


def test_run_timeout_none_is_backward_compatible():
    # 기본값 None(=인자 생략)이면 상한 없이 정상 동작 — 하위호환 순수 추가 확인.
    r = proc.run(_py("print('ok')"), timeout=None)
    assert r.stdout.strip() == "ok"
    assert r.returncode == 0
