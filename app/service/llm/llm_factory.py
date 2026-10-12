"""Chat model provider factory.

Same dispatch-by-name shape as the embeddings factory (Phase 3): one function,
one place that knows how to construct each provider's client. Tools, the
router, and the graph never import langchain_google_genai/openai/anthropic
directly — they only ever call get_llm().
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from app.utils.config import Settings
from app.utils.exception.exceptions import ConfigurationException
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


def get_llm(settings: Settings, config: dict[str, Any]) -> BaseChatModel:
    """Return the configured chat model, dispatching on settings.llm.llm_provider."""
    provider = settings.llm.llm_provider.lower()
    llm_config = config["SETTINGS"]["MODEL_SERVICE"]["LLM"]

    if provider == "fake":
        # NOTE: FakeListChatModel doesn't implement bind_tools() (raises
        # NotImplementedError) — it can exercise this factory in isolation,
        # but NOT power a real running app_car_rental server, since
        # build_graph() always calls llm.bind_tools(TOOLS). Full agent-flow
        # tests use tests/fakes.py::ScriptedChatModel instead, which does
        # support it. Never set LLM_PROVIDER=fake to actually run the app.
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        logger.debug("llm_factory_selected", provider="fake")
        return FakeListChatModel(responses=["This is a test response."])

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.llm.google_api_key:
            raise ConfigurationException(
                detail="GOOGLE_API_KEY is required for llm_provider=google"
            )
        model = llm_config["GOOGLE"][0]
        logger.debug("llm_factory_selected", provider="google", model=model)
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=SecretStr(settings.llm.google_api_key),
            temperature=llm_config["TEMPERATURE"],
            max_output_tokens=llm_config["MAX_TOKENS"],
            top_p=llm_config["TOP_P"],
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.llm.openai_api_key:
            raise ConfigurationException(
                detail="OPENAI_API_KEY is required for llm_provider=openai"
            )
        model = llm_config["OPENAI"][0]
        logger.debug("llm_factory_selected", provider="openai", model=model)
        return ChatOpenAI(
            model=model,
            api_key=SecretStr(settings.llm.openai_api_key),
            temperature=llm_config["TEMPERATURE"],
            max_completion_tokens=llm_config["MAX_TOKENS"],
            top_p=llm_config["TOP_P"],
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.llm.anthropic_api_key:
            raise ConfigurationException(
                detail="ANTHROPIC_API_KEY is required for llm_provider=anthropic"
            )
        model = llm_config["ANTHROPIC"][0]
        logger.debug("llm_factory_selected", provider="anthropic", model=model)
        return ChatAnthropic(
            model_name=model,
            api_key=SecretStr(settings.llm.anthropic_api_key),
            temperature=llm_config["TEMPERATURE"],
            max_tokens_to_sample=llm_config["MAX_TOKENS"],
            top_p=llm_config["TOP_P"],
            timeout=None,
            stop=None,
        )

    raise ConfigurationException(
        detail=f"Unknown llm_provider '{provider}'. Supported: fake, google, openai, anthropic"
    )
