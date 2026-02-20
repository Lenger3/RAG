# Code RAG 🔍

> **Tamamen yerel ve offline** çalışan GitHub kod arama sistemi.  
> API key gerekmez. Veriler buluta gitmez.

GitHub repository'lerini klonlayıp analiz eder, ChromaDB'de indexler ve doğal dil sorguları ile ilgili kod parçalarını bulur — Ollama ile yerel LLM yanıtı üretir.

---

## ✨ Özellikler

- 🖥️ **Terminal arayüzü (TUI)** — fare + klavye destekli interaktif ekran
- 🏠 **Tamamen yerel** — Ollama ile internet bağlantısı gerekmez
- 🌍 **Türkçe sorgu desteği** — Türkçe sorular, İngilizce kodda arama
- ⚡ **Akıllı chunking** — Python AST bazlı fonksiyon/sınıf sınırları
- 🗄️ **ChromaDB** — kalıcı vektör veritabanı

---

## 🚀 Kurulum

```bash
# 1. Sanal ortam oluştur
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

# 2. Bağımlılıkları yükle
pip install -r requirements.txt
```

### Ollama (Yerel LLM)

```bash
# https://ollama.com/download adresinden indirip kur (macOS: .dmg)
# Ardından modeli çek:
ollama pull qwen2.5:3b          # ~2 GB, Türkçe desteği mükemmel
```

| Model | Boyut | Türkçe | Hız |
|---|---|---|---|
| `qwen2.5:3b` ⭐ | ~2 GB | Mükemmel | Çok hızlı |
| `qwen2.5:7b` | ~4.7 GB | Çok iyi | Hızlı |
| `llama3.2:3b` | ~2 GB | Orta | Çok hızlı |
| `gemma3:4b` | ~3.3 GB | İyi | Hızlı |

Farklı model kullanmak için `config/config.yaml`:
```yaml
llm:
  model: "qwen2.5:7b"
```

---

## 🖥️ Terminal Arayüzü (TUI)

```bash
python -m src.ui.tui
```

```
┌─ Code RAG 🔍 ─────────────────────────────────────────┐
│ Koleksiyonlar  │ 🔍 Sorgula │ 📥 İndeksle │ ℹ️ Hakkında │
│                │                                       │
│  DL_Project    │  Koleksiyon: [ DL_Project ▼ ]        │
│  IpCam_...     │  Soru: [_________________________]   │
│                │                                       │
│ [🔄 Yenile]   │  [🔍 Sorgula + LLM] [📄 Sadece Ara]  │
│ [🗑  Sil]     │                                       │
│                │  Sonuçlar burada görünür...           │
└────────────────┴───────────────────────────────────────┘
 q Çıkış  r Yenile  Tab İleri  Enter Sorgula
```

| Sekme | İşlev |
|---|---|
| **🔍 Sorgula** | Koleksiyon seç → soru yaz → Enter veya butona bas → LLM yanıtı |
| **📥 İndeksle** | GitHub URL gir → strateji seç → İndeksle → canlı log izle |
| **ℹ️ Hakkında** | Kullanım kılavuzu |

**Kısayollar:** `q` çıkış · `r` yenile · `Tab` widget geç · `Enter` sorgula

---

## 💻 Komut Satırı (CLI)

TUI yerine terminal komutlarını tercih ediyorsanız:

### Repo İndeksleme

```bash
python -m src.cli.main index --url https://github.com/kullanici/repo
```

| Seçenek | Açıklama | Varsayılan |
|---|---|---|
| `--url, -u` | GitHub repo URL'si | zorunlu |
| `--collection, -c` | Koleksiyon adı | repo adı |
| `--strategy, -s` | `function` \| `class` \| `file` \| `sliding` | `function` |
| `--max-chunk` | Maks token boyutu | `1000` |

### Sorgulama

```bash
# LLM ile yanıt al
python -m src.cli.main query --collection myrepo "yolo modeli ne kullanılmış?"

# Sadece kod bul, LLM yok
python -m src.cli.main query --collection myrepo "authentication" --no-llm

# Streaming mod
python -m src.cli.main query --collection myrepo "ana giriş noktası nerede?" --stream
```

### Koleksiyon Yönetimi

```bash
python -m src.cli.main list                          # listele
python -m src.cli.main delete --collection myrepo   # sil
```

---

## 📁 Proje Yapısı

```
RAG/
├── src/
│   ├── indexer/
│   │   ├── repo_cloner.py     # GitHub repo clone + dosya listeleme
│   │   ├── file_parser.py     # Dosya okuma + encoding tespiti
│   │   ├── code_chunker.py    # AST bazlı fonksiyon/sınıf chunking
│   │   └── embedder.py        # sentence-transformers (yerel)
│   ├── retriever/
│   │   ├── vector_store.py    # ChromaDB wrapper
│   │   └── query_engine.py    # Semantic search + context builder
│   ├── llm/
│   │   └── generator.py       # Ollama entegrasyonu (streaming dahil)
│   ├── ui/
│   │   └── tui.py             # Textual terminal arayüzü
│   └── cli/
│       └── main.py            # Click CLI (index/query/list/delete)
├── data/
│   ├── repos/                 # Clone edilen repolar
│   └── chroma_db/             # ChromaDB vektör veritabanı
├── config/
│   └── config.yaml            # Tüm ayarlar
├── tests/                     # Unit testler
├── requirements.txt
└── .env.example
```

---

## ⚙️ Konfigürasyon

`config/config.yaml` dosyasından tüm ayarlar yönetilebilir:

```yaml
llm:
  model: "qwen2.5:3b"                    # Ollama model adı
  ollama_host: "http://localhost:11434"  # Ollama adresi
  temperature: 0.1                       # Yaratıcılık (0=deterministik)
  max_tokens: 2000

retrieval:
  top_k: 5                               # Kaç chunk getirileceği
  similarity_threshold: 0.3             # Min benzerlik skoru

chunking:
  strategy: "function"                   # function | class | file | sliding
  max_chunk_size: 1000                   # Token cinsinden

embedding:
  model: "sentence-transformers/all-MiniLM-L6-v2"
  device: "cpu"                          # Apple Silicon: "mps" | GPU: "cuda"
```

---

## 🧪 Testler

```bash
pytest tests/ -v
```

---

## 💡 Örnek Sorgular

```bash
# YOLO modeli tespit
python -m src.cli.main query -c myrepo "yolo modeli olarak ne kullanılmış?"

# Authentication akışı
python -m src.cli.main query -c myrepo "authentication nasıl implemente edilmiş?"

# Veritabanı bağlantısı
python -m src.cli.main query -c myrepo "veritabanı bağlantısı nerede yapılıyor?"

# Hangi kütüphaneler kullanılmış?
python -m src.cli.main query -c myrepo "kullanılan dış kütüphaneler neler?"
```
