from scripts import check_provider


def test_smoke_check_needs_explicit_environment_key(monkeypatch, capsys):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert check_provider.main(["--provider", "groq"]) == 2
    assert "Set GROQ_API_KEY" in capsys.readouterr().out


def test_smoke_check_sanitises_failures(monkeypatch, capsys):
    monkeypatch.setenv("GROQ_API_KEY", "not-a-real-secret")
    monkeypatch.setattr(check_provider, "verify_api_key", lambda *args: (True, None))
    def fail(*args, **kwargs):
        raise RuntimeError("token=not-a-real-secret")
    monkeypatch.setattr(check_provider, "_call_llm", fail)
    assert check_provider.main(["--provider", "groq"]) == 1
    assert "not-a-real-secret" not in capsys.readouterr().out
