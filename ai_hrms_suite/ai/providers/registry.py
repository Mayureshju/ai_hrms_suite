from ai_hrms_suite.ai.providers.openai import OpenAIProvider
from ai_hrms_suite.ai.providers.openrouter import OpenRouterProvider
from ai_hrms_suite.ai.providers.anthropic import AnthropicProvider
from ai_hrms_suite.ai.providers.gemini import GeminiProvider


def get_provider(provider_name: str):
    n = (provider_name or "").lower()
    if n == "openai":
        return OpenAIProvider()
    if n == "openrouter":
        return OpenRouterProvider()
    if n == "anthropic":
        return AnthropicProvider()
    if n == "gemini":
        return GeminiProvider()
    raise ValueError(f"Unknown provider: {provider_name}")
