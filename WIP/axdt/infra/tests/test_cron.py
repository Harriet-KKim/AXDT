"""cron 모듈 — crontab watcher 등록/해제. 텍스트 빌드는 순수."""
from axdt.infra import cron, proc


def test_build_text_has_marker_and_schedule():
    text = cron.build_crontab_text(
        "", interval_min=5, watcher_cmd="axdt-watcher",
        cwd="/proj", lockfile="/tmp/axdt.lock")
    assert cron.MARKER_BEGIN in text and cron.MARKER_END in text
    assert "*/5 * * * *" in text
    assert "cd /proj" in text
    assert "flock" in text
    assert "axdt-watcher" in text


def test_build_text_preserves_other_lines():
    existing = "0 0 * * * other-job\n"
    text = cron.build_crontab_text(
        existing, interval_min=10, watcher_cmd="w", cwd="/p", lockfile="/l")
    assert "other-job" in text


def test_build_text_replaces_existing_block_idempotent():
    first = cron.build_crontab_text(
        "", interval_min=5, watcher_cmd="old", cwd="/p", lockfile="/l")
    second = cron.build_crontab_text(
        first, interval_min=5, watcher_cmd="new", cwd="/p", lockfile="/l")
    assert second.count(cron.MARKER_BEGIN) == 1   # 블록 중복 없음
    assert "new" in second
    assert "old" not in second


def test_install_writes_crontab(fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 0, "", "")
    cron.install(interval_min=5, watcher_cmd="axdt-watcher", cwd="/proj")
    assert fake_proc.find("crontab") is not None


def test_uninstall_removes_block(fake_proc):
    existing = cron.build_crontab_text(
        "", interval_min=5, watcher_cmd="w", cwd="/p", lockfile="/l")

    def h(argv, kw):
        if "-l" in argv:
            return proc.ProcResult(argv, 0, existing, "")
        return proc.ProcResult(argv, 0, "", "")
    fake_proc.handler = h
    cron.uninstall()
    assert fake_proc.find("crontab") is not None
