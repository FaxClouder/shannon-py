from shannon_py.config import Settings


def test_settings_defaults_use_mock_provider() -> None:
    settings = Settings()

    assert settings.default_provider == "mock"
    assert settings.default_model == "mock-default"
    assert settings.enable_shell_tools is False
    assert settings.max_input_chars == 100_000
