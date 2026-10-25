"""Startup configuration tests use synthetic CSVs and never call the network."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("racechip_run_configured", Path(__file__).parents[2] / "scripts/run_configured.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_source_reference_restores_search_without_copying_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    csv = tmp_path / "credentials.csv"
    csv.write_text("SecretId,SecretKey\nsynthetic-id,synthetic-secret\n", encoding="utf-8-sig")
    module.register_source(csv)
    config = module.source_config_path().read_text(encoding="utf-8")
    assert json.loads(config)["source_path"] == str(csv.resolve())
    assert "synthetic-id" not in config and "synthetic-secret" not in config
    assert module.load_search_source()
    import os
    assert os.environ["TENCENTCLOUD_SECRET_KEY"] == "synthetic-secret"
    assert os.environ["SEARCHPRO_AUTH_MODE"] == "tc3"


def test_explicit_shell_configuration_has_priority(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("TENCENTCLOUD_WSA_APIKEY", "synthetic-explicit-key")
    assert module.load_search_source() is False


@pytest.mark.parametrize("csv", ["SecretId,SecretKey\nsynthetic-id,\n", "SecretId,SecretKey\na,b\nc,d\n", "wrong,header\na,b\n"])
def test_invalid_csv_does_not_echo_or_save_values(tmp_path, monkeypatch, csv):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    source = tmp_path / "credentials.csv"
    source.write_text(csv)
    with pytest.raises(ValueError) as error:
        module.register_source(source)
    assert "synthetic-id" not in str(error.value)
    assert not module.source_config_path().exists()


def test_missing_registered_file_has_clear_redacted_error(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    config = module.source_config_path()
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"source_path": str(tmp_path / "missing.csv")}))
    with pytest.raises(ValueError, match="原CSV文件"):
        module.load_search_source()
