from pathlib import Path
from unittest.mock import patch

from core.llm_agent import generate_llm_insight


def test_llm_agent_fallback_does_not_write_repo_error_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch("urllib.request.urlopen", side_effect=OSError("network unavailable")):
        payload = generate_llm_insight()

    assert "insight" in payload
    assert not Path("llm_error.log").exists()
