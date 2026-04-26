import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# Base 

class BaseAIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str | None: ...


# Disabled 

class DisabledProvider(BaseAIProvider):
    async def generate(self, prompt: str) -> str | None:
        return None


# Ollama 

class OllamaProvider(BaseAIProvider):
    def __init__(self, base_url: str, model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, prompt: str) -> str | None:
        logger.info(f"Ollama: отправляем запрос, модель={self.model}")
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3},
                    },
                )
                response.raise_for_status()
                result = response.json().get("response", "").strip()
                logger.info(f"Ollama: получен ответ, длина={len(result)} символов")
                return result
        except Exception as e:
            logger.error(f"Ollama error: {type(e).__name__}: {e}")
            return None



# OpenAI 

class OpenAIProvider(BaseAIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 300,
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return None


# Factory 

def get_ai_provider() -> BaseAIProvider:
    """
    Выбирает провайдера по AI_PROVIDER в .env.
    Платформа полностью работает при AI_PROVIDER=disabled.
    """
    provider = settings.ai_provider.lower()
    print(f"DEBUG AI_PROVIDER='{provider}'")
    if provider == "ollama":
        model = getattr(settings, "ollama_model", "llama3.2")
        logger.info(f"AI: Ollama ({model})")
        return OllamaProvider(settings.ollama_url, model)

    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning("AI_PROVIDER=openai но OPENAI_API_KEY не задан → disabled")
            return DisabledProvider()
        model = getattr(settings, "openai_model", "gpt-4o-mini")
        logger.info(f"AI: OpenAI ({model})")
        return OpenAIProvider(settings.openai_api_key, model)

    logger.info("AI: disabled")
    return DisabledProvider()
