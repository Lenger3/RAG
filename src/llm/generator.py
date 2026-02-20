"""
generator.py - LLM ile cevap üretme modülü (Ollama - local)
"""

import logging
from pathlib import Path
from typing import Optional, Iterator

import yaml

logger = logging.getLogger(__name__)

_config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_LLM_CONFIG = _config["llm"]

SYSTEM_PROMPT = """Sen bir kod analizi asistanısın. Sana bir GitHub repository'sinden ilgili kod parçaları verilmiştir.

Kurallar:
- Cevaplarında her zaman dosya adı ve fonksiyon/sınıf adlarına referans ver
- Belirli kod bölümlerinden bahsederken satır numaralarını belirt
- Eğer cevap sağlanan context'te yoksa bunu açıkça söyle
- Kısa ama kapsamlı ol
- Kod örneklerini uygun dilde markdown kod bloğu olarak formatla
- Birden fazla dosya ilgiliyse nasıl etkileşime girdiklerini açıkla
- Kullanıcının soru dilinde (Türkçe veya İngilizce) cevap ver"""


class LLMGenerator:
    """
    Ollama ile yerel LLM kullanarak kod analizi cevabı üretir.
    Ollama çalışıyor olmalı: https://ollama.com
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        self.model = model or _LLM_CONFIG.get("model", "qwen2.5:3b")
        self.temperature = temperature if temperature is not None else _LLM_CONFIG.get("temperature", 0.1)
        self.max_tokens = max_tokens or _LLM_CONFIG.get("max_tokens", 2000)
        self._host = _LLM_CONFIG.get("ollama_host", "http://localhost:11434")

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_answer(self, query: str, context: str) -> str:
        """Context + sorgudan cevap üretir."""
        return self._chat(query, context, stream=False)

    def generate_stream(self, query: str, context: str) -> Iterator[str]:
        """Streaming modda token token cevap üretir."""
        yield from self._stream(query, context)

    def answer_without_context(self, query: str) -> str:
        """Context olmadan direkt LLM'e sor."""
        return self.generate_answer(query, context="")

    # ── Ollama ───────────────────────────────────────────────────────────────

    def _get_client(self):
        try:
            import ollama
            return ollama.Client(host=self._host)
        except ImportError:
            raise RuntimeError(
                "ollama paketi yüklü değil. "
                "Çalıştırın: pip install ollama"
            )

    def _chat(self, query: str, context: str, stream: bool = False) -> str:
        client = self._get_client()
        logger.info(f"Ollama isteği: model={self.model}")

        response = client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_message(query, context)},
            ],
            options={
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        )
        answer = response["message"]["content"]
        logger.info(f"Cevap üretildi: {len(answer)} karakter")
        return answer

    def _stream(self, query: str, context: str) -> Iterator[str]:
        client = self._get_client()
        stream = client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_message(query, context)},
            ],
            options={"temperature": self.temperature, "num_predict": self.max_tokens},
            stream=True,
        )
        for chunk in stream:
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token

    # ── Helper ───────────────────────────────────────────────────────────────

    def _build_message(self, query: str, context: str) -> str:
        if context:
            return f"## Kod Bağlamı\n\n{context}\n\n## Soru\n\n{query}"
        return f"## Soru\n\n{query}"
