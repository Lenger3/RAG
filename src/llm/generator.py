"""
generator.py - LLM ile cevap üretme modülü (OpenAI GPT + Ollama)
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional, Iterator

import yaml
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_LLM_CONFIG = _config["llm"]

SYSTEM_PROMPT = """You are an expert code analysis assistant. You have been given relevant code snippets \
from a GitHub repository to answer the user's question.

Guidelines:
- Always reference specific files and function/class names when answering
- Include line numbers when mentioning specific code sections
- If the answer is not in the provided context, say so clearly
- Be concise but thorough
- Format code examples using markdown code blocks with the appropriate language
- If multiple files are involved, explain how they interact
- You can answer in the same language as the user's question (Turkish, English, etc.)"""


class LLMGenerator:
    """
    OpenAI GPT veya Ollama (local) ile kod analizi cevabı üretir.
    config.yaml'da llm.provider ile seçilir: 'openai' veya 'ollama'
    """

    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        self.provider = provider or _LLM_CONFIG.get("provider", "openai")
        self.model = model or _LLM_CONFIG.get("model", "qwen2.5:3b")
        self.temperature = temperature if temperature is not None else _LLM_CONFIG.get("temperature", 0.1)
        self.max_tokens = max_tokens or _LLM_CONFIG.get("max_tokens", 2000)
        self._openai_client = None
        self._ollama_host = _LLM_CONFIG.get("ollama_host", "http://localhost:11434")

    # ── Public API ──────────────────────────────────────────────────────────

    def generate_answer(self, query: str, context: str, stream: bool = False) -> str:
        """Context + sorgudan cevap üretir (string döner)."""
        if self.provider == "ollama":
            return self._ollama_generate(query, context)
        else:
            return self._openai_generate(query, context)

    def generate_stream(self, query: str, context: str) -> Iterator[str]:
        """Streaming modda token token cevap üretir."""
        if self.provider == "ollama":
            yield from self._ollama_stream(query, context)
        else:
            yield from self._openai_stream(query, context)

    def answer_without_context(self, query: str) -> str:
        """Context olmadan direkt LLM'e sor (fallback)."""
        return self.generate_answer(query, context="")

    # ── Ollama ──────────────────────────────────────────────────────────────

    def _ollama_generate(self, query: str, context: str) -> str:
        try:
            import ollama
        except ImportError:
            raise RuntimeError("ollama paketi yüklü değil. 'pip install ollama' çalıştırın.")

        user_message = self._build_user_message(query, context)
        logger.info(f"Ollama isteği: model={self.model}, host={self._ollama_host}")

        client = ollama.Client(host=self._ollama_host)
        response = client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            options={
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        )
        answer = response["message"]["content"]
        logger.info(f"Ollama cevabı: {len(answer)} karakter")
        return answer

    def _ollama_stream(self, query: str, context: str) -> Iterator[str]:
        try:
            import ollama
        except ImportError:
            raise RuntimeError("ollama paketi yüklü değil.")

        user_message = self._build_user_message(query, context)
        client = ollama.Client(host=self._ollama_host)

        stream = client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            options={"temperature": self.temperature, "num_predict": self.max_tokens},
            stream=True,
        )
        for chunk in stream:
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token

    # ── OpenAI ──────────────────────────────────────────────────────────────

    def _get_openai_client(self):
        if self._openai_client is None:
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "OPENAI_API_KEY bulunamadı. "
                        ".env dosyasına OPENAI_API_KEY=... ekleyin."
                    )
                self._openai_client = OpenAI(api_key=api_key)
                logger.info(f"OpenAI client başlatıldı, model: {self.model}")
            except ImportError:
                raise RuntimeError("openai paketi yüklü değil.")
        return self._openai_client

    def _openai_generate(self, query: str, context: str) -> str:
        client = self._get_openai_client()
        user_message = self._build_user_message(query, context)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stream=False,
                )
                answer = response.choices[0].message.content
                logger.info(f"OpenAI cevabı: {len(answer)} karakter, tokens: {response.usage.total_tokens}")
                return answer
            except Exception as e:
                if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limit, {wait}s bekleniyor...")
                    time.sleep(wait)
                    continue
                raise

    def _openai_stream(self, query: str, context: str) -> Iterator[str]:
        client = self._get_openai_client()
        user_message = self._build_user_message(query, context)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        response = client.chat.completions.create(
            model=self.model, messages=messages,
            temperature=self.temperature, max_tokens=self.max_tokens,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _build_user_message(self, query: str, context: str) -> str:
        if context:
            return f"## Code Context\n\n{context}\n\n## Question\n\n{query}"
        return f"## Question\n\n{query}"
