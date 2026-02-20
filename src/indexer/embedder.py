"""
embedder.py - Kod chunk'larından embedding oluşturma (local sentence-transformers)
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_EMBEDDING_CONFIG = _config["embedding"]


class Embedder:
    """
    Chunk'ları embedding vektörlerine dönüştürür.
    Local sentence-transformers kullanır (tamamen offline çalışır).
    """

    def __init__(self, model: Optional[str] = None):
        self.model_name = model or _EMBEDDING_CONFIG.get("model", "sentence-transformers/all-MiniLM-L6-v2")
        self._model = None
        self._cache: dict = {}

    def _load_model(self):
        """Model lazy-loading (ilk embed çağrısında yüklenir)."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            device = _EMBEDDING_CONFIG.get("device", "cpu")
            logger.info(f"Sentence-transformer yükleniyor: {self.model_name} ({device})")
            self._model = SentenceTransformer(self.model_name, device=device)
            logger.info("Model başarıyla yüklendi.")
        except ImportError:
            logger.error("sentence-transformers paketi yüklü değil.")
            raise

    def _cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def create_embeddings(self, chunks: list, batch_size: int = 32) -> list:
        """
        Chunk listesi için embedding listesi oluşturur.

        Args:
            chunks: [{'content': str, 'metadata': {...}}, ...] listesi
            batch_size: Batch boyutu

        Returns:
            Embedding vektörlerinin listesi (chunks ile aynı sırada)
        """
        self._load_model()
        texts = [c["content"] for c in chunks]
        return self._embed_texts(texts, batch_size)

    def embed_query(self, query: str) -> list:
        """
        Tek bir sorgu metnini embed eder.

        Args:
            query: Sorgu metni

        Returns:
            Embedding vektörü (float listesi)
        """
        self._load_model()
        cached = self._cache.get(self._cache_key(query))
        if cached is not None:
            return cached

        result = self._embed_texts([query], batch_size=1)[0]
        self._cache[self._cache_key(query)] = result
        return result

    def _embed_texts(self, texts: list, batch_size: int) -> list:
        """Metinleri batch batch embed eder."""
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            result = self._model.encode(batch, show_progress_bar=False)
            if hasattr(result, "tolist"):
                batch_embeddings = result.tolist()
            else:
                batch_embeddings = [r.tolist() if hasattr(r, "tolist") else list(r) for r in result]
            all_embeddings.extend(batch_embeddings)
            logger.debug(f"Embedded batch {i // batch_size + 1}, toplam: {len(all_embeddings)}/{len(texts)}")

        return all_embeddings

    def get_embedding_dimension(self) -> int:
        """Embedding boyutunu döner."""
        return len(self.embed_query("test"))
