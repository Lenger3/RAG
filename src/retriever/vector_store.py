"""
vector_store.py - ChromaDB persistent vector store wrapper
"""

import logging
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

import chromadb
import yaml

logger = logging.getLogger(__name__)

_config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_CHROMA_CONFIG = _config["chromadb"]


class VectorStore:
    """
    ChromaDB tabanlı persistent vector store.
    Her repo için ayrı collection kullanır.
    """

    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory or _CHROMA_CONFIG["persist_directory"]
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        logger.info(f"ChromaDB başlatıldı: {self.persist_directory}")

    def initialize_collection(self, collection_name: str) -> chromadb.Collection:
        """
        Collection'ı oluşturur veya mevcut olanı getirir.

        Args:
            collection_name: Collection adı (genellikle repo adı)

        Returns:
            ChromaDB Collection nesnesi
        """
        # ChromaDB collection ismi constraints: alphanumeric + hyphens/underscores
        safe_name = _sanitize_collection_name(collection_name)
        collection = self.client.get_or_create_collection(
            name=safe_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Collection hazır: {safe_name} ({collection.count()} döküman)")
        return collection

    def add_chunks(
        self,
        collection: chromadb.Collection,
        chunks: List[Dict],
        embeddings: List[List[float]],
    ):
        """
        Chunk'ları embedding'leriyle birlikte collection'a ekler.
        Batch'ler halinde işler.

        Args:
            collection: ChromaDB collection
            chunks: [{'content': str, 'metadata': {...}}, ...]
            embeddings: her chunk için embedding vektörü
        """
        if not chunks:
            return

        batch_size = 100
        total_added = 0

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i: i + batch_size]
            batch_embeddings = embeddings[i: i + batch_size]

            ids = [str(uuid.uuid4()) for _ in batch_chunks]
            documents = [c["content"] for c in batch_chunks]
            metadatas = []
            for c in batch_chunks:
                meta = {k: str(v) for k, v in c["metadata"].items()}
                metadatas.append(meta)

            collection.add(
                ids=ids,
                documents=documents,
                embeddings=batch_embeddings,
                metadatas=metadatas,
            )
            total_added += len(batch_chunks)
            logger.debug(f"Eklendi: {total_added}/{len(chunks)} chunk")

        logger.info(f"Toplam {total_added} chunk eklendi: {collection.name}")

    def search(
        self,
        collection: chromadb.Collection,
        query_embedding: List[float],
        n_results: int = 5,
        metadata_filter: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Benzer chunk'ları arar.

        Args:
            collection: ChromaDB collection
            query_embedding: Sorgu embedding vektörü
            n_results: Kaç sonuç döndürülecek
            metadata_filter: ChromaDB where filtresi (opsiyonel)

        Returns:
            [{'content': str, 'metadata': {...}, 'distance': float}, ...]
        """
        count = collection.count()
        if count == 0:
            return []

        n_results = min(n_results, count)

        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if metadata_filter:
            kwargs["where"] = metadata_filter

        results = collection.query(**kwargs)

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "content": doc,
                "metadata": meta,
                "distance": dist,
                "similarity": 1 - dist,  # cosine similarity
            })

        return output

    def delete_collection(self, collection_name: str) -> bool:
        """Collection'ı siler."""
        safe_name = _sanitize_collection_name(collection_name)
        try:
            self.client.delete_collection(safe_name)
            logger.info(f"Collection silindi: {safe_name}")
            return True
        except Exception as e:
            logger.error(f"Collection silinirken hata ({safe_name}): {e}")
            return False

    def list_collections(self) -> List[Dict]:
        """Mevcut collection'ların listesini döner."""
        collections = self.client.list_collections()
        return [{"name": c.name, "count": c.count()} for c in collections]

    def get_collection(self, collection_name: str) -> Optional[chromadb.Collection]:
        """Collection'ı adıyla getirir, yoksa None döner."""
        safe_name = _sanitize_collection_name(collection_name)
        try:
            return self.client.get_collection(safe_name)
        except Exception:
            return None


def _sanitize_collection_name(name: str) -> str:
    """ChromaDB için geçerli collection adı oluşturur."""
    import re
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    if len(sanitized) < 3:
        sanitized += "_col"
    return sanitized[:63]
