"""
Абстракция LLM-клиента для извлечения контактных данных.
Основной провайдер: Perplexity API (OpenAI-совместимый, модель sonar).
Также поддерживает: OpenAI, GigaChat, Qwen.

Ключевые отличия Perplexity от OpenAI:
- НЕ поддерживает response_format={"type": "json_object"}
- Вместо этого используем строгий system prompt с требованием вернуть только JSON
- Парсим JSON из ответа с fallback на regex-извлечение
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings
from app.models import FallbackReason

logger = logging.getLogger(__name__)

# ── Системный промпт для Perplexity ─────────────────────────────────────────

_SYSTEM_PROMPT = """Ты — специализированный извлекатель контактных данных сотрудников компаний с веб-страниц.

СТРОГИЕ ПРАВИЛА:
1. Извлекай ТОЛЬКО реальных сотрудников данной конкретной компании
2. НИКОГДА не включай политиков (Путин, Медведев, Мишустин и т.д.), знаменитостей, авторов новостей, журналистов или людей упомянутых в новостях/статьях
3. Должность — ТОЛЬКО реальная должность в компании (Директор, Менеджер, Инженер, Бухгалтер и т.д.). Если текст после имени содержит телефон, email, адрес, дату — это НЕ должность
4. Если не уверен что человек работает в этой компании — НЕ включай его
5. ФИО для русских — строго Фамилия Имя Отчество. Для иностранцев — First Last
6. Различай личные и общие email:
   - Общие (НЕ личные): info@, support@, help@, admin@, office@, pr@, secretary@, reception@, contact@, mail@, noreply@, sales@, marketing@, press@, media@, feedback@, webmaster@, postmaster@, hello@, general@, service@, team@, hr@, legal@, billing@, finance@, it@, tech@, dev@, api@
   - Личные: содержат имя/фамилию человека (ivanov@, a.petrov@, sidorova.m@)
7. Телефон нормализуй в формат +7XXXXXXXXXX для России
8. Если должность не найдена или сомнительна — поставь null, НЕ выдумывай
9. Для каждого контакта укажи тип роли: "Топ-менеджмент", "Средний менеджмент", "Специалист"
10. НЕ включай людей, упомянутых только в контексте новостей, пресс-релизов, интервью СМИ

Верни ТОЛЬКО валидный JSON (без markdown, без ```, без пояснений до или после):
{
  "company_name": "название компании или null",
  "inn": "ИНН 10 или 12 цифр или null",
  "kpp": "КПП 9 цифр или null",
  "company_emails": ["info@...", "support@..."],
  "contacts": [
    {
      "full_name": "Фамилия Имя Отчество",
      "position_raw": "должность как на сайте или null",
      "position_normalized": "нормализованная должность или null",
      "personal_email": "personal@email или null",
      "phone": "+7XXXXXXXXXX или null",
      "role_type": "Топ-менеджмент",
      "social_links": {"vk": null, "telegram": null, "linkedin": null}
    }
  ]
}"""

_USER_PROMPT_TEMPLATE = """Компания: {company_name}
URL страницы: {url}

Извлеки контактные данные сотрудников ТОЛЬКО этой компании из текста ниже.
Помни: должность — это ТОЛЬКО название позиции (Директор, Менеджер и т.д.), а НЕ телефон, email или адрес.
{position_hint}

Текст страницы:
{text}"""


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
    """HTTP-ошибка при запросе к LLM."""

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


class PerplexityProvider(BaseLLMProvider):
    """
    Провайдер Perplexity API (OpenAI-совместимый).
    Использует модель sonar.
    НЕ использует response_format — Perplexity его не поддерживает.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "sonar",
        base_url: str = "https://api.perplexity.ai",
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
                # НЕ используем response_format — Perplexity не поддерживает
            )
        except Exception as exc:
            exc_class = type(exc).__name__
            if "timeout" in exc_class.lower() or "Timeout" in str(exc):
                raise LLMTimeoutError(f"Perplexity тайм-аут: {exc}")
            elif "RateLimit" in exc_class or "429" in str(exc):
                raise LLMHTTPError(f"Perplexity rate limit: {exc}", status_code=429)
            elif "Authentication" in exc_class or "401" in str(exc):
                raise LLMHTTPError(f"Perplexity ошибка авторизации: {exc}", status_code=401)
            else:
                raise LLMClientError(f"Perplexity ошибка: {exc}")

        latency = (time.monotonic() - start) * 1000
        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            tokens_prompt=usage.prompt_tokens if usage else 0,
            tokens_completion=usage.completion_tokens if usage else 0,
            model=response.model,
            provider="perplexity",
            latency_ms=latency,
            raw_response=response,
        )


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


def _extract_json_from_text(text: str) -> dict:
    """
    Извлекает JSON из текста ответа LLM.
    Perplexity может обернуть JSON в markdown-блоки или добавить пояснения.
    """
    # Попытка 1: прямой парсинг
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Попытка 2: убрать markdown-обёртку ```json ... ```
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if md_match:
        try:
            return json.loads(md_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Попытка 3: найти первый JSON-объект в тексте
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        candidate = brace_match.group()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Не удалось извлечь JSON из ответа LLM (длина={len(text)})")


class LLMClient:
    """
    Высокоуровневый клиент для взаимодействия с LLM.
    Управляет бюджетом токенов, логирует вызовы, предоставляет fallback-сигналы.
    По умолчанию использует Perplexity API.
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
            if provider == "perplexity":
                base_url = getattr(settings, "LLM_BASE_URL", "https://api.perplexity.ai")
                self._provider = PerplexityProvider(
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                )
            elif provider == "openai":
                base_url = getattr(settings, "LLM_BASE_URL", None)
                self._provider = OpenAIProvider(
                    api_key=api_key,
                    model=model,
                    base_url=base_url if base_url != "https://api.perplexity.ai" else None,
                )
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
        company_name: Optional[str] = None,
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
            company_name=company_name or "неизвестна",
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

        # Парсим JSON из ответа (Perplexity не гарантирует чистый JSON)
        try:
            result = _extract_json_from_text(response.content)
            if not isinstance(result, dict):
                raise ValueError("LLM вернул не объект")
            return result
        except (json.JSONDecodeError, ValueError) as exc:
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
