# Code RAG 🔍

GitHub repository'lerini klonlayıp analiz eden, ChromaDB'de indexleyen ve doğal dil sorguları ile kod araması yapabilen RAG sistemi.

## Kurulum

```bash
# 1. Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 2. Bağımlılıkları yükle
pip install -r requirements.txt

# 3. .env dosyasını oluştur
cp .env.example .env
# .env dosyasını açıp OPENAI_API_KEY'i girin
```

## Kullanım

### Repo İndeksleme

```bash
python -m src.cli.main index --url https://github.com/pallets/click
```

Seçenekler:
- `--url, -u` GitHub repo URL'si (zorunlu)
- `--collection, -c` Koleksiyon adı (varsayılan: repo adı)
- `--strategy, -s` Chunking stratejisi: `function` | `class` | `file` | `sliding` (varsayılan: `function`)
- `--max-chunk` Maksimum chunk token boyutu (varsayılan: 1000)
- `--embedding` Embedding sağlayıcı: `local` | `openai` (varsayılan: `local`)

### Sorgulama

```bash
python -m src.cli.main query --collection click "How is command group implemented?"
```

Seçenekler:
- `--collection, -c` Koleksiyon adı (zorunlu)
- `--top-k, -k` Kaç chunk getirileceği (varsayılan: 5)
- `--no-llm` Sadece retrieve sonuçlarını göster (LLM olmadan)
- `--stream` Streaming modda cevap al
- `--embedding` Embedding sağlayıcı

### Koleksiyonları Listele

```bash
python -m src.cli.main list
```

### Koleksiyon Sil

```bash
python -m src.cli.main delete --collection click
```

## Testler

```bash
pytest tests/ -v
```

## Proje Yapısı

```
code-rag/
├── src/
│   ├── indexer/
│   │   ├── repo_cloner.py     # GitHub repo clone
│   │   ├── file_parser.py     # Dosya okuma + AST parsing
│   │   ├── code_chunker.py    # Akıllı kod chunking
│   │   └── embedder.py        # Embedding oluşturma
│   ├── retriever/
│   │   ├── vector_store.py    # ChromaDB wrapper
│   │   └── query_engine.py    # Sorgulama + context building
│   ├── llm/
│   │   └── generator.py       # OpenAI GPT yanıt üretici
│   └── cli/
│       └── main.py            # CLI interface
├── data/
│   ├── repos/                 # Clone edilen repo'lar
│   └── chroma_db/             # ChromaDB veritabanı
├── config/config.yaml         # Ayarlar
├── tests/                     # Unit testler
├── requirements.txt
└── .env.example
```

## Konfigürasyon

`config/config.yaml` dosyasından tüm ayarlar yönetilebilir:

- **embedding.model**: Kullanılacak sentence-transformers modeli
- **chunking.strategy**: Varsayılan chunking stratejisi
- **retrieval.top_k**: Varsayılan retrieve edilen chunk sayısı
- **llm.model**: OpenAI model adı (gpt-4o-mini, gpt-4, vb.)
- **chromadb.persist_directory**: ChromaDB depolama dizini

## Örnek Sorgular

```bash
# Kimlik doğrulama nasıl implemente edilmiş?
python -m src.cli.main query -c myrepo "How is authentication implemented?"

# Hangi external kütüphaneler kullanılıyor?
python -m src.cli.main query -c myrepo "What external libraries are used for HTTP requests?"

# Veritabanı bağlantısı nerede yapılıyor?
python -m src.cli.main query -c myrepo "Where is the database connection configured?"
```
