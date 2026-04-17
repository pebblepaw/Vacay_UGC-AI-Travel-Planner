import asyncio
import sys
import types
from pathlib import Path

import pytest
import yaml

import backend.app_config as app_config_module
import backend.llm as llm_module
import backend.services.gemini_analyzer as gemini_analyzer_module
from backend.services.automation import browser_use_worker as browser_use_module


class FakeChatOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeChatGoogleGenerativeAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def install_fake_chat_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "langchain_openai",
        types.SimpleNamespace(ChatOpenAI=FakeChatOpenAI),
    )
    monkeypatch.setitem(
        sys.modules,
        "langchain_google_genai",
        types.SimpleNamespace(ChatGoogleGenerativeAI=FakeChatGoogleGenerativeAI),
    )


def write_app_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "assistant": {
                    "language": "English",
                },
                "copy": {
                    "booking": {
                        "no_results": "I could not get usable live results from {provider}.",
                    }
                },
                "llm": {
                    "provider_preference": "auto",
                    "roles": {
                        "default": "cheap_tools",
                        "orchestrator": "high_reasoning",
                        "critic": "high_reasoning",
                        "travel_editor": "cheap_tools",
                        "search_agent": "cheap_tools",
                        "booking_agent": "cheap_tools",
                        "booking_intent": "high_reasoning",
                        "chitchat": "cheap_text",
                        "browser_use": "cheap_tools",
                        "video_analyzer": "multimodal_analysis",
                    },
                    "profiles": {
                        "high_reasoning": {
                            "gemini": "gemini-2.5-pro",
                            "dashscope": "qwen-max",
                        },
                        "cheap_tools": {
                            "gemini": "gemini-2.5-flash",
                            "dashscope": "qwen-plus",
                        },
                        "cheap_text": {
                            "gemini": "gemini-2.5-flash",
                            "dashscope": "qwen-turbo",
                        },
                        "multimodal_analysis": {
                            "gemini": "gemini-2.5-flash",
                            "dashscope": "qwen2.5-vl-3b-instruct",
                        },
                    },
                },
            },
            sort_keys=False,
        )
    )


def reset_config_cache() -> None:
    app_config_module.load_app_config.cache_clear()


def test_get_agent_llm_falls_back_to_gemini_when_dashscope_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_fake_chat_modules(monkeypatch)
    config_path = tmp_path / "config.yaml"
    write_app_config(config_path)
    monkeypatch.setattr(app_config_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "DASHSCOPE_API_KEY", None)
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "gemini-key")
    reset_config_cache()

    llm = llm_module.get_agent_llm(role="travel_editor", temperature=0.4)

    assert isinstance(llm, FakeChatGoogleGenerativeAI)
    assert llm.kwargs["model"] == "gemini-2.5-flash"
    assert llm.kwargs["api_key"] == "gemini-key"
    assert llm.kwargs["temperature"] == 0.4


def test_get_agent_llm_uses_dashscope_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_fake_chat_modules(monkeypatch)
    config_path = tmp_path / "config.yaml"
    write_app_config(config_path)
    monkeypatch.setattr(app_config_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(
        llm_module.settings,
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    reset_config_cache()

    llm = llm_module.get_agent_llm(role="orchestrator")

    assert isinstance(llm, FakeChatOpenAI)
    assert llm.kwargs["model"] == "qwen-max"
    assert llm.kwargs["api_key"] == "dashscope-key"
    assert (
        llm.kwargs["base_url"]
        == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def test_browser_use_shim_uses_the_resolved_provider_and_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_fake_chat_modules(monkeypatch)
    config_path = tmp_path / "config.yaml"
    write_app_config(config_path)
    monkeypatch.setattr(app_config_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(browser_use_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "DASHSCOPE_API_KEY", None)
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "gemini-key")
    reset_config_cache()

    shim = browser_use_module.build_browser_use_llm()

    assert isinstance(shim, browser_use_module._LLMProviderShim)
    assert shim.provider == "gemini"
    assert shim.model == "gemini-2.5-flash"
    assert shim.model_name == "gemini-2.5-flash"
    assert isinstance(shim._llm, FakeChatGoogleGenerativeAI)


def test_get_agent_llm_raises_when_no_provider_can_be_initialized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    write_app_config(config_path)
    monkeypatch.setattr(app_config_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "DASHSCOPE_API_KEY", None)
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "")
    reset_config_cache()

    with pytest.raises(RuntimeError):
        llm_module.get_agent_llm(role="search_agent")


def test_resolve_agent_llm_config_uses_role_profile_models(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    write_app_config(config_path)
    monkeypatch.setattr(app_config_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "gemini-key")
    reset_config_cache()

    orchestrator_config = llm_module.resolve_agent_llm_config(role="orchestrator")
    worker_config = llm_module.resolve_agent_llm_config(role="travel_editor")

    assert orchestrator_config.provider == "gemini"
    assert orchestrator_config.model == "gemini-2.5-pro"
    assert worker_config.model == "gemini-2.5-flash"


def test_app_config_exposes_language_and_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    write_app_config(config_path)
    monkeypatch.setattr(app_config_module.settings, "APP_CONFIG_PATH", config_path)
    reset_config_cache()

    config = app_config_module.load_app_config()

    assert config.assistant.language == "English"
    assert "Respond in English" in app_config_module.get_assistant_language_instruction()
    assert (
        app_config_module.render_copy("booking.no_results", provider="trip.com")
        == "I could not get usable live results from trip.com."
    )


def test_app_config_language_drives_prompt_instruction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    write_app_config(config_path)
    raw = yaml.safe_load(config_path.read_text())
    raw["assistant"]["language"] = "Chinese"
    config_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    monkeypatch.setattr(app_config_module.settings, "APP_CONFIG_PATH", config_path)
    reset_config_cache()

    assert app_config_module.get_assistant_language_instruction() == (
        "Respond in Chinese unless the user explicitly asks for another language."
    )


def test_gemini_analyzer_uses_google_genai_client_and_role_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    write_app_config(config_path)
    monkeypatch.setattr(app_config_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(llm_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(gemini_analyzer_module.settings, "APP_CONFIG_PATH", config_path)
    monkeypatch.setattr(gemini_analyzer_module.settings, "GEMINI_API_KEY", "gemini-key")
    reset_config_cache()

    captured: dict[str, object] = {}

    class FakeFilesAPI:
        def upload(self, *, file, config=None):
            captured["upload_file"] = file
            return "uploaded-file"

    class FakeModelsAPI:
        def generate_content(self, *, model, contents, config=None):
            captured["model_name"] = model
            captured["contents"] = contents
            return types.SimpleNamespace(
                text='{"city":"Queenstown","locations":[],"activities":[],"vibes":[],"confidence":"high"}'
            )

    class FakeClient:
        def __init__(self, *, api_key: str):
            captured["api_key"] = api_key
            self.files = FakeFilesAPI()
            self.models = FakeModelsAPI()

    monkeypatch.setattr(
        gemini_analyzer_module,
        "genai",
        types.SimpleNamespace(Client=FakeClient),
    )

    service = gemini_analyzer_module.GeminiAnalyzerService()
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    result = asyncio.run(service.analyze_video(str(video_path), "Queenstown clip"))

    assert captured["api_key"] == "gemini-key"
    assert service.model_name == "gemini-2.5-flash"
    assert captured["upload_file"] == str(video_path)
    assert captured["model_name"] == "gemini-2.5-flash"
    assert isinstance(captured["contents"], list)
    assert captured["contents"][0].startswith("Video title: 'Queenstown clip'")
    assert captured["contents"][1] == "uploaded-file"
    assert result.metadata["city"] == "Queenstown"
