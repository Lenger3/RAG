"""
query_engine.py - Sorgu işleme, retrieval ve context oluşturma
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict

import yaml

from src.indexer.embedder import Embedder
from src.indexer.code_chunker import count_tokens
from src.retriever.vector_store import VectorStore

logger = logging.getLogger(__name__)

_config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_RETRIEVAL_CONFIG = _config["retrieval"]
_LLM_CONFIG = _config["llm"]


class QueryEngine:
    """
    Kullanıcı sorgularını işler, relevant chunk'ları retriever eder
    ve LLM için context oluşturur.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedder: Optional[Embedder] = None,
        collection_name: Optional[str] = None,
    ):
        self.vector_store = vector_store or VectorStore()
        self.embedder = embedder or Embedder()
        self._collection = None
        if collection_name:
            self.set_collection(collection_name)

    def set_collection(self, collection_name: str):
        """Sorgulanacak collection'ı ayarlar."""
        self._collection = self.vector_store.initialize_collection(collection_name)
        logger.info(f"Query engine collection: {collection_name}")

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None,
        similarity_threshold: Optional[float] = None,
    ) -> List[Dict]:
        """
        Sorguya en benzer kod chunk'larını bulur.

        Args:
            query: Kullanıcı sorgu metni
            top_k: Kaç sonuç döndürülecek (None ise config'den alır)
            filters: Metadata filtreleri (ör: {'language': 'python'})
            similarity_threshold: Minimum benzerlik skoru (0-1)

        Returns:
            [{'content': str, 'metadata': {...}, 'similarity': float}, ...]
        """
        if self._collection is None:
            raise RuntimeError("Collection set edilmedi. set_collection() çağırın.")

        top_k = top_k or _RETRIEVAL_CONFIG["top_k"]
        threshold = similarity_threshold if similarity_threshold is not None else _RETRIEVAL_CONFIG.get("similarity_threshold", 0.0)

        # Query'yi embed et
        logger.info(f"Query embed ediliyor: '{query[:60]}...' " if len(query) > 60 else f"Query embed ediliyor: '{query}'")
        query_embedding = self.embedder.embed_query(query)

        # Vector search
        results = self.vector_store.search(
            collection=self._collection,
            query_embedding=query_embedding,
            n_results=top_k * 2,  # Threshold filtering için fazladan al
            metadata_filter=filters,
        )

        # Similarity threshold filtresi
        if threshold > 0:
            results = [r for r in results if r["similarity"] >= threshold]

        # Top-k'ya kırp
        results = results[:top_k]

        logger.info(f"{len(results)} chunk bulundu (threshold: {threshold})")
        return results

    def build_context(
        self,
        chunks: List[Dict],
        max_tokens: int = 4000,
        include_metadata: bool = True,
    ) -> str:
        """
        LLM için retrieve edilen chunk'lardan context string oluşturur.
        Token limitini aşmadan maksimum context sağlar.

        Args:
            chunks: retrieve() çıktısı
            max_tokens: Maksimum token sayısı
            include_metadata: Dosya yolu ve satır numaralarını ekle

        Returns:
            LLM'e verilecek context string
        """
        context_parts = []
        total_tokens = 0

        for i, chunk in enumerate(chunks, start=1):
            meta = chunk.get("metadata", {})
            file_path = meta.get("file_path", "unknown")
            line_start = meta.get("line_start", "?")
            line_end = meta.get("line_end", "?")
            chunk_type = meta.get("chunk_type", "code")
            name = meta.get("name", "")
            similarity = chunk.get("similarity", 0)

            if include_metadata:
                header = (
                    f"### [{i}] {file_path} "
                    f"(lines {line_start}-{line_end}, type: {chunk_type}"
                    + (f", name: {name}" if name else "")
                    + f", similarity: {similarity:.2f})\n"
                )
            else:
                header = f"### [{i}] {file_path}\n"

            chunk_text = f"{header}```\n{chunk['content']}\n```\n"
            chunk_tokens = count_tokens(chunk_text)

            if total_tokens + chunk_tokens > max_tokens:
                logger.debug(f"Token limiti aşıldı, {i-1} chunk kullanılıyor.")
                break

            context_parts.append(chunk_text)
            total_tokens += chunk_tokens

        context = "\n".join(context_parts)
        logger.info(f"Context oluşturuldu: {total_tokens} token, {len(context_parts)} chunk")
        return context

    def search_and_build(
        self,
        query: str,
        top_k: Optional[int] = None,
        max_context_tokens: int = 4000,
        filters: Optional[Dict] = None,
    ) -> tuple[List[Dict], str]:
        """
        Retrieve + context building işlemini tek çağrıda yapar.

        Returns:
            (chunks, context_string)
        """
        chunks = self.retrieve(query, top_k=top_k, filters=filters)
        context = self.build_context(chunks, max_tokens=max_context_tokens)
        return chunks, context
