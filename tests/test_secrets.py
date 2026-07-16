import csfloat_tracker.core.secrets as secrets


def test_file_fallback_roundtrip(monkeypatch, isolated_data_dir):
    # Force the file backend by disabling keyring detection
    monkeypatch.setattr(secrets, "_keyring", lambda: None)

    assert secrets.get_api_key() is None
    assert secrets.storage_backend() == "file"

    backend = secrets.set_api_key("my-secret-key")
    assert backend == "file"
    assert secrets.get_api_key() == "my-secret-key"
    assert (isolated_data_dir / "secrets.json").exists()

    secrets.delete_api_key()
    assert secrets.get_api_key() is None
    assert not (isolated_data_dir / "secrets.json").exists()


def test_overwrite_key(monkeypatch, isolated_data_dir):
    monkeypatch.setattr(secrets, "_keyring", lambda: None)
    secrets.set_api_key("first")
    secrets.set_api_key("second")
    assert secrets.get_api_key() == "second"
    secrets.delete_api_key()
