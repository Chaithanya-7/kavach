import pytest


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Isolated workspace: CWD is an empty temp dir, no env override."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FRAMEWORK_CONFIG", raising=False)
    return tmp_path
