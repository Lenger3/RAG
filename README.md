# Code RAG 🔍

GitHub repository'lerini klonlayıp analiz eden, ChromaDB'de indexleyen ve **tamamen yerel** olarak doğal dil sorguları ile kod araması yapabilen RAG sistemi.

> 🏠 **Tamamen offline çalışır** — API key gerekmez, veriler buluta gitmez.

## Kurulum

```bash
# 1. Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac

# 2. Bağımlılıkları yükle
pip install -r requirements.txt
```

## Ollama Kurulumu (Yerel LLM)

```bash
# 1. Ollama'yı yükle → https://ollama.com/download (macOS: .dmg indir ve aç)

# 2. Türkçe desteği güçlü, hafif bir model çek
ollama pull qwen2.5:3b     # ~2GB — önerilen
# veya
ollama pull qwen2.5:7b     # ~4.7GB — daha iyi kalite
```

Kullanılabilir modeller:

| Model | Boyut | Türkçe | Hız |
|---|---|---|---|
| `qwen2.5:3b` ⭐ | ~2 GB | Mükemmel | Çok hızlı |
| `qwen2.5:7b` | ~4.7 GB | Çok iyi | Hızlı |
| `llama3.2:3b` | ~2 GB | Orta | Çok hızlı |
| `gemma3:4b` | ~3.3 GB | İyi | Hızlı |

Modeli değiştirmek için `config/config.yaml` dosyasından:
```yaml
llm:
  model: "qwen2.5:7b"
```

---

## Kullanım

### Repo İndeksleme

```bash
python -m src.cli.main index --url https://github.com/kullanici/repo
```

Seçenekler:
- `--url, -u` GitHub repo URL'si (zorunlu)
- `--collection, -c` Koleksiyon adı (varsayılan: repo adı)
- `--strategy, -s` Chunking stratejisi: `function` | `class` | `file` | `sliding`
- `--max-chunk` Maksimum chunk token boyutu (varsayılan: 1000)

### Sorgulama

```bash
# LLM ile cevap al
python -m src.cli.main query --collection myrepo "hangi model kullanılmış?"

# Sadece kod parçalarını getir (LLM olmadan)
python -m src.cli.main query --collection myrepo "authentication" --no-llm

# Streaming modda cevap
python -m src.cli.main query --collection myrepo "ana giriş noktası nerede?" --stream
```

Seçenekler:
- `--collection, -c` Koleksiyon adı (zorunlu)
- `--top-k, -k` Kaç chunk getirileceği (varsayılan: 5)
- `--no-llm` Sadece retrieve sonuçlarını göster
- `--stream` Streaming modda cevap al

### Koleksiyonları Listele

```bash
python -m src.cli.main list
```

### Koleksiyon Sil

```bash
python -m src.cli.main delete --collection myrepo
```

---

## Proje Yapısı

```
RAG/
├── src/
│   ├── indexer/
│   │   ├── repo_cloner.py     # GitHub repo clone + dosya listeleme
│   │   ├── file_parser.py     # Dosya okuma + Python AST parsing
│   │   ├── code_chunker.py    # function / class / sliding chunking
│   │   └── embedder.py        # sentence-transformers embedding (local)
│   ├── retriever/
│   │   ├── vector_store.py    # ChromaDB wrapper
│   │   └── query_engine.py    # Semantic search + context builder
│   ├── llm/
│   │   └── generator.py       # Ollama LLM entegrasyonu
│   └── cli/
│       └── main.py            # CLI (index / query / list / delete)
├── data/
│   ├── repos/                 # Clone edilen repo'lar
│   └── chroma_db/             # ChromaDB vektör veritabanı
├── config/config.yaml         # Tüm ayarlar
├── tests/                     # Unit testler (32 test)
└── requirements.txt
```

## Konfigürasyon (`config/config.yaml`)

```yaml
llm:
  model: "qwen2.5:3b"           # Ollama model adı
  ollama_host: "http://localhost:11434"
  temperature: 0.1
  max_tokens: 2000

retrieval:
  top_k: 5
  similarity_threshold: 0.3     # Düşürtmek → daha fazla sonuç

chunking:
  strategy: "function"          # function | class | file | sliding
  max_chunk_size: 1000

embedding:
  model: "sentence-transformers/all-MiniLM-L6-v2"
  device: "cpu"                 # Apple Silicon: "mps", GPU: "cuda"
```

## Testler

```bash
pytest tests/ -v
```

## Örnek Sorgular

```bash
# Hangi YOLO versiyonu kullanılmış?
python -m src.cli.main query -c myrepo "yolo modeli olarak ne kullanılmış"

# Authentication nasıl yapılmış?
python -m src.cli.main query -c myrepo "authentication nasıl implemente edilmiş?"

# Veritabanı bağlantısı nerede?
python -m src.cli.main query -c myrepo "veritabanı bağlantısı nerede?"

# Hangi dış kütüphaneler kullanılıyor?
python -m src.cli.main query -c myrepo "kullanılan kütüphaneler neler?"
```
