"""infra.config의 progress 경로 확장(progress_path/report_dir) 검증."""
from axdt.infra import config


def test_progress_path(tmp_path):
    assert config.progress_path(tmp_path) == tmp_path / "docs" / "interim" / "progress.md"


def test_report_dir(tmp_path):
    assert config.report_dir(tmp_path) == tmp_path / "docs" / "interim" / "report"
