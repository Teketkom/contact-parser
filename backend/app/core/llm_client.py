"""
Абстракция LLM-клиента для извлечения контактных данных.
Поддерживает провайдеры: OpenAI, GigaChat, Qwen.
Отслеживает бюджет токенов, логирует промпты и ответы,
автоматически сигнализирует о необходимости переключения на резервный вариант.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings
from app.models import FallbackReason

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Ты — специализированный парсер контактных данных с веб-страниц компаний.
Твоя задача — извлечь из предоставленного HTML/текста структурированные контактные данные.

Правила:
1. Возвращай ТОЛЬКО валидный JSON и ничего более.
2. Не придумывай данные — только то, что явно присутствует в тексте.
3. Телефоны нормализуй в международный формат +7XXXXXXXXXX для России.
4. ФИО возвращай в формате "Фамилия Имя Отчество".
5. Если поле не найдено — используй null.
6. ИНН — 10 или 12 цифр, КПП — 9 цифр.

Формат ответа:
{
  "company_name": "...",
  "inn": "...",
  "kpp": "...",
  "company_email": "...",
  "contacts": [
    {
      "full_name": "...",
      "position_raw": "...",
      "personal_email": "...",
      "phone": "...",
      "social_links": {
        "vk": null, "telegram": null, "linkedin": null,
        "facebook": null, "instagram": null, "twitter": null
      }
    }
  ]
}"""

_USER_PROMPT_TEMPLATE = """Извлеки контактные данные из следующего текста страницы {url}:

{text}

{position_hint}"""


@dataclass
class LLMResponse:
    """Ответ LLM-провайдера."""
    content: str
    tokens_prompt: int = 0
    tokens_completion: int = 0
    model: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    raw_response: Optional[Any] = None


@dataclass
class TokenBudget:
    """Отслеживает расход токенов на сессию."""
    limit: int
    used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    request_count: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit

    def consume(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.used += prompt + completion
        self.request_count += 1


class LLMClientError(Exception):
    """Базовое исключение LLM-клиента."""

    def __init__(self, message: str, reason: FallbackReason = FallbackReason.LLM_UNAVAILABLE):
        super().__init__(message)
        self.reason = reason


class LLMTimeoutError(LLMClientError):
    """Превышен тайм-аут запроса к LLM."""

    def __init__(self, message: str = "Превышен тайм-аут LLM"):
        super().__init__(message, FallbackReason.LLM_TIMEOUT)


class LLMHTTPError(LLMClientError):
    """ХТТП-ошибка при запросе к LLM."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message, FallbackReason.LLM_HTTP_ERROR)
        self.status_code = status_code


class TokenBudgetExhaustedError(LLMClientError):
    """Бюджет токенов исчерпан."""

    def __init__(self):
        super().__init__(
            "Бюджет токенов LLM исчерпан",
            FallbackReason.TOKEN_BUDGET_EXHAUSTED,
        )


class BaseLLMProvider:
    """Базовый класс провайдера LLM."""

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> LLMResponse:
        raise NotImplementedError


class OpenAIProvider(BaseLLMProvider):
    """Провайдер OpenAI (включая совместимые API: OpenRouter, Azure и т.д.)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("Установите пакет: pip install openai")

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=settings.LLM_TIMEOUT,
        )
        self.model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> LLMResponse:
        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            exc_class = type(exc).__name__
            if "timeout" in exc_class.lower() or "Timeout" in str(exc):
                raise LLMTimeoutError(f"OpenAI тайм-аут: {exc}")
            elif "RateLimit" in exc_class or "429" in str(exc):
                raise LLMHTTPError(f"OpenAI rate limit: {exc}", status_code=429)
            elif "Authentication" in exc_class or "401" in str(exc):
                raise LLMHTTPError(f"OpenAI ошибка авторизации: {exc}", status_code=401)
            else:
                raise LLMClientError(f"OpenAI ошибка: {exc}")

        latency = (time.monotonic() - start) * 1000
        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            tokens_prompt=usage.prompt_tokens if usage else 0,
            tokens_completion=usage.completion_tokens if usage else 0,
            model=response.model,
            provider="openai",
            latency_ms=latency,
            raw_response=response,
        )


class GigaChatProvider(BaseLLMProvider):
    """Провайдер GigaChat (Сбербанк)."""

    def __init__(self, credentials: str, model: str = "GigaChat") -> None:
        self.credentials = credentials
        self.model = model
        self._access_token: Optional[str] = None
        self._token_expires: float = 0.0

    async def _get_token(self) -> str:
        import httpx

        if self._access_token and time.monotonic() < self._token_expires:
            return self._access_token

        try:
            async with httpx.AsyncClient(verify=settings.GIGACHAT_VERIFY_SSL) as client:
                response = await client.post(
                    "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                    headers={
                        "Authorization": f"Basic {self.credentials}",
                        "RqUID": str(__import__("uuid").uuid4()),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"scope": settings.GIGACHAT_SCOPE},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                self._access_token = data["access_token"]
                self._token_expires = time.monotonic() + data.get("expires_at", 1800) - 60
                return self._access_token
        except Exception as exc:
            raise LLMHTTPError(f"GigaChat: ошибка получения токена: {exc}")

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> LLMResponse:
        import httpx

        token = await self._get_token()
        start = time.monotonic()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(
                verify=settings.GIGACHAT_VERIFY_SSL,
                timeout=settings.LLM_TIMEOUT,
            ) as client:
                response = await client.post(
                    "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code == 429:
                    raise LLMHTTPError("GigaChat: превышен лимит запросов", 429)
                response.raise_for_status()
                data = response.json()
        except LLMHTTPError:
            raise
        except Exception as exc:
            if hasattr(exc, '__class__') and 'Timeout' in type(exc).__name__:
                raise LLMTimeoutError(f"GigaChat тайм-аут: {exc}")
            raise LLMHTTPError(f"GigaChat HTTP-ошибка: {exc}")

        latency = (time.monotonic() - start) * 1000
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            tokens_prompt=usage.get("prompt_tokens", 0),
            tokens_completion=usage.get("completion_tokens", 0),
            model=data.get("model", self.model),
            provider="gigachat",
            latency_ms=latency,
        )


class QwenProvider(BaseLLMProvider):
    """Провайдер Qwen (Alibaba Cloud DashScope)."""

    def __init__(self, api_key: str, model: str = "qwen-turbo") -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("Установите пакет: pip install openai")

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=settings.LLM_TIMEOUT,
        )
        self.model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> LLMResponse:
        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            if "timeout" in str(exc).lower():
                raise LLMTimeoutError(f"Qwen тайм-аут: {exc}")
            raise LLMClientError(f"Qwen ошибка: {exc}")

        latency = (time.monotonic() - start) * 1000
        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            tokens_prompt=usage.prompt_tokens if usage else 0,
            tokens_completion=usage.completion_tokens if usage else 0,
            model=response.model,
            provider="qwen",
            latency_ms=latency,
        )


class LLMClient:
    """
    Высокоуровневый клиент для взаимодействия с LLM.
    Управляет бюджетом токенов, логирует вызовы, предоставляет fallback-сигналы.
    """

    def __init__(self) -> None:
        self._provider: Optional[BaseLLMProvider] = None
        self._budget = TokenBudget(limit=settings.LLM_SESSION_TOKEN_BUDGET)
        self._prompt_log: list[dict[str, Any]] = []
        self._initialized = False

    def _init_provider(self) -> None:
        if self._initialized:
            return

        provider = settings.LLM_PROVIDER.lower()
        api_key = settings.LLM_API_KEY
        model = settings.LLM_MODEL

        if not api_key:
            logger.warning("LLM_API_KEY не задан — вариант B (AI) будет недоступен")
            self._initialized = True
            return

        try:
            if provider == "openai":
                self._provider = OpenAIProvider(api_key=api_key, model=model)
            elif provider == "gigachat":
                self._provider = GigaChatProvider(credentials=api_key, model=model)
            elif provider == "qwen":
                self._provider = QwenProvider(api_key=api_key, model=model)
            else:
                logger.error("Неизвестный LLM провайдер: %s", provider)
        except Exception as exc:
            logger.error("Ошибка инициализации LLM провайдера: %s", exc)

        self._initialized = True

    @property
    def is_available(self) -> bool:
        self._init_provider()
        return self._provider is not None and not self._budget.exhausted

    @property
    def tokens_used(self) -> int:
        return self._budget.used

    async def extract_contacts(
        self,
        text: str,
        page_url: str,
        target_positions: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Вызывает LLM для извлечения контактных данных из текста страницы.
        """
        self._init_provider()

        if self._provider is None:
            raise LLMClientError(
                "LLM провайдер не инициализирован",
                FallbackReason.LLM_UNAVAILABLE,
            )

        if self._budget.exhausted:
            raise TokenBudgetExhaustedError()

        max_chars = settings.LLM_MAX_TOKENS_PER_REQUEST * 3
        truncated_text = text[:max_chars]
        if len(text) > max_chars:
            truncated_text += "\n[текст обрезан]"

        position_hint = ""
        if target_positions:
            positions_str = ", ".join(target_positions)
            position_hint = f"\nЦелевые должности для поиска: {positions_str}"

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            url=page_url,
            text=truncated_text,
            position_hint=position_hint,
        )

        log_entry: dict[str, Any] = {
            "url": page_url,
            "prompt_chars": len(user_prompt),
            "timestamp": time.time(),
        }

        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self._provider.complete(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    max_tokens=settings.LLM_MAX_TOKENS_PER_REQUEST,
                ),
                timeout=settings.LLM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Тайм-аут {settings.LLM_TIMEOUT}с при запросе к LLM")
        except LLMClientError:
            raise
        except Exception as exc:
            raise LLMClientError(f"Неожиданная ошибка LLM: {exc}")

        self._budget.consume(response.tokens_prompt, response.tokens_completion)
        log_entry.update({
            "tokens_prompt": response.tokens_prompt,
            "tokens_completion": response.tokens_completion,
            "latency_ms": response.latency_ms,
            "model": response.model,
            "provider": response.provider,
        })
        self._prompt_log.append(log_entry)

        logger.debug(
            "LLM[%s] %s: %d+%d токенов, %.0fмс",
            response.provider,
            page_url,
            response.tokens_prompt,
            response.tokens_completion,
            response.latency_ms,
        )

        if self._budget.exhausted:
            logger.warning(
                "Бюджет токенов LLM исчерпан: использовано %d из %d",
                self._budget.used,
                self._budget.limit,
            )

        try:
            result = json.loads(response.content)
            if not isinstance(result, dict):
                raise ValueError("LLM вернул не объект")
            return result
        except json.JSONDecodeError as exc:
            import re
            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            raise LLMClientError(f"LLM вернул невалидный JSON: {exc}")

    def get_budget_status(self) -> dict[str, Any]:
        return {
            "limit": self._budget.limit,
            "used": self._budget.used,
            "remaining": self._budget.remaining,
            "exhausted": self._budget.exhausted,
            "request_count": self._budget.request_count,
            "prompt_tokens": self._budget.prompt_tokens,
            "completion_tokens": self._budget.completion_tokens,
        }

    def get_prompt_log(self) -> list[dict[str, Any]]:
        return list(self._prompt_log)

    def reset_budget(self) -> None:
        self._budget = TokenBudget(limit=settings.LLM_SESSION_TOKEN_BUDGET)
        logger.info("Бюджет токенов LLM сброшен")
