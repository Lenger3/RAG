# GitHub Repository RAG Sistemi - Antigravity Prompt

## Proje Özeti
GitHub repository'lerini klonlayıp analiz eden, kod tabanını vektör veritabanında indexleyen ve doğal dil sorguları ile kod araması yapabilen bir RAG (Retrieval Augmented Generation) sistemi geliştir.

## Teknik Gereksinimler

### Core Stack
- **Dil**: Python 3.10+
- **Vektör DB**: ChromaDB (local, persistent)
- **Embedding**: Sentence-transformers (local model) veya OpenAI embeddings
- **LLM**: OpenAI GPT veya local model (Ollama entegrasyonu opsiyonel)
- **Kod Parsing**: AST (Python), tree-sitter (multi-language support için)

### Desteklenmesi Gereken Dosya Tipleri
- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
- Markdown (.md)
- JSON (.json)
- YAML (.yaml, .yml)
- Diğer text-based dosyalar

## Proje Yapısı

```
code-rag/
├── src/
│   ├── __init__.py
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── repo_cloner.py       # GitHub repo clone işlemleri
│   │   ├── file_parser.py       # Dosya okuma ve parsing
│   │   ├── code_chunker.py      # Akıllı kod parçalama
│   │   └── embedder.py          # Embedding oluşturma
│   ├── retriever/
│   │   ├── __init__.py
│   │   ├── vector_store.py      # ChromaDB wrapper
│   │   └── query_engine.py      # Sorgulama logic
│   ├── llm/
│   │   ├── __init__.py
│   │   └── generator.py         # LLM ile cevap üretme
│   └── cli/
│       ├── __init__.py
│       └── main.py              # CLI interface
├── data/
│   ├── repos/                   # Clone edilen repo'lar
│   └── chroma_db/               # ChromaDB persistent storage
├── config/
│   └── config.yaml              # Ayarlar
├── tests/
│   └── ...
├── requirements.txt
├── README.md
└── .env.example
```

## Detaylı Modül Açıklamaları

### 1. Repository Cloner (repo_cloner.py)
**Görevler:**
- GitHub URL'den repo clone etme (git veya PyGithub kullanarak)
- Zaten clone edilmiş repo'ları kontrol etme (中duplicate prevention)
- .gitignore kurallarını respect etme
- Binary dosyaları ignore etme (.png, .jpg, .exe, vb.)

**Önemli Fonksiyonlar:**
```python
def clone_repository(repo_url: str, target_path: str) -> str:
    """Clone GitHub repository to local path"""
    
def get_repo_info(repo_path: str) -> dict:
    """Extract repo metadata (name, description, language, etc.)"""
    
def list_code_files(repo_path: str, extensions: list) -> list:
    """List all relevant code files"""
```

### 2. File Parser (file_parser.py)
**Görevler:**
- Dosya encoding'ini detect etme
- Farklı dosya tiplerini okuma
- Python için AST parsing ile fonksiyon, class, import çıkarma
- Metadata extraction (author, file path, last modified)

**Önemli Fonksiyonlar:**
```python
def read_file(file_path: str) -> str:
    """Read file with proper encoding detection"""
    
def parse_python_file(file_path: str) -> dict:
    """Parse Python file and extract functions, classes, imports"""
    # AST kullanarak:
    # - Function definitions (name, args, docstring)
    # - Class definitions
    # - Import statements
    # - Top-level comments
    
def extract_metadata(file_path: str) -> dict:
    """Extract file metadata"""
```

### 3. Code Chunker (code_chunker.py)
**Görevler:**
- Kodu anlamlı parçalara bölme (function-level, class-level)
- Overlap stratejisi (context preservation için)
- Chunk size optimization (token limits için)
- Her chunk için metadata ekleme

**Chunking Stratejileri:**
1. **Function-level chunking**: Her fonksiyon ayrı chunk
2. **Class-level chunking**: Class ve metodları birlikte
3. **File-level chunking**: Küçük dosyalar için tüm dosya
4. **Sliding window**: Büyük dosyalar için overlap ile

**Önemli Fonksiyonlar:**
```python
def chunk_code(file_content: str, file_type: str, strategy: str) -> list:
    """Split code into meaningful chunks"""
    # Return format:
    # [{
    #   'content': 'chunk content',
    #   'metadata': {
    #     'file_path': '...',
    #     'chunk_type': 'function/class/file',
    #     'name': 'function_name',
    #     'line_start': 10,
    #     'line_end': 25
    #   }
    # }]
```

### 4. Embedder (embedder.py)
**Görevler:**
- Chunk'ları embedding'e çevirme
- Batch processing (performans için)
- Caching mekanizması (aynı chunk için tekrar hesaplama önleme)

**Model Seçenekleri:**
- Local: `sentence-transformers/all-MiniLM-L6-v2` (hafif ve hızlı)
- Advanced: `sentence-transformers/all-mpnet-base-v2` (daha iyi quality)
- OpenAI: `text-embedding-ada-002` (en iyi ama ücretli)

**Önemli Fonksiyonlar:**
```python
def create_embeddings(chunks: list, batch_size: int = 32) -> list:
    """Create embeddings for chunks"""
    
def embed_query(query: str) -> list:
    """Embed user query"""
```

### 5. Vector Store (vector_store.py)
**Görevler:**
- ChromaDB collection yönetimi
- Chunk'ları embedding'leri ile kaydetme
- Metadata filtering desteği
- Similarity search

**Önemli Fonksiyonlar:**
```python
def initialize_collection(collection_name: str) -> chromadb.Collection:
    """Initialize or get existing ChromaDB collection"""
    
def add_chunks(chunks: list, embeddings: list, metadata: list):
    """Add chunks to vector store"""
    
def search(query_embedding: list, n_results: int = 5, 
           metadata_filter: dict = None) -> list:
    """Search similar chunks"""
```

### 6. Query Engine (query_engine.py)
**Görevler:**
- User query'yi embed etme
- Relevant chunk'ları retrieve etme
- Sonuçları rank etme ve filtering
- Context window oluşturma (LLM için)

**Önemli Fonksiyonlar:**
```python
def retrieve(query: str, top_k: int = 5, filters: dict = None) -> list:
    """Retrieve relevant code chunks"""
    
def build_context(chunks: list, max_tokens: int = 4000) -> str:
    """Build context for LLM from retrieved chunks"""
```

### 7. LLM Generator (generator.py)
**Görevler:**
- Retrieved context + user query ile prompt oluşturma
- LLM'e request gönderme
- Streaming support (opsiyonel)
- Error handling ve retry logic

**Prompt Template Örneği:**
```python
SYSTEM_PROMPT = """You are a code analysis assistant. Based on the provided code context, 
answer the user's question accurately. Always reference specific files and functions 
when possible. If you're not sure, say so."""

def generate_answer(query: str, context: str, model: str = "gpt-4") -> str:
    """Generate answer using LLM"""
```

### 8. CLI Interface (main.py)
**Komutlar:**
```bash
# Repo indexleme
python -m src.cli.main index --url https://github.com/user/repo

# Sorgulama
python -m src.cli.main query "How is authentication implemented?"

# Collection listeleme
python -m src.cli.main list

# Collection silme
python -m src.cli.main delete --collection repo-name
```

**CLI Features:**
- Rich formatting (colors, tables)
- Progress bars (indexing sırasında)
- Interactive mode (sorular art arda)
- Output formatting (markdown, json)

## Configuration (config.yaml)

```yaml
embedding:
  model: "sentence-transformers/all-MiniLM-L6-v2"
  device: "cpu"  # or "cuda"
  
chunking:
  strategy: "function"  # function, class, file, sliding
  max_chunk_size: 1000
  overlap: 100
  
retrieval:
  top_k: 5
  similarity_threshold: 0.7
  
llm:
  provider: "openai"  # openai, ollama, anthropic
  model: "gpt-4"
  temperature: 0.1
  max_tokens: 2000
  
chromadb:
  persist_directory: "./data/chroma_db"
  
git:
  clone_depth: 1  # shallow clone
  excluded_extensions: [".pyc", ".log", ".bin", ".exe"]
```

## Requirements.txt

```txt
# Core dependencies
chromadb>=0.4.0
sentence-transformers>=2.2.0
gitpython>=3.1.0
PyGithub>=2.1.0

# LLM
openai>=1.0.0
anthropic>=0.18.0  # opsiyonel

# CLI
click>=8.1.0
rich>=13.0.0
python-dotenv>=1.0.0

# Parsing
tree-sitter>=0.20.0  # opsiyonel, multi-language için

# Utils
pyyaml>=6.0
tqdm>=4.65.0
tiktoken>=0.5.0  # token counting için

# Development
pytest>=7.4.0
black>=23.0.0
flake8>=6.0.0
```

## Örnek Kullanım Senaryoları

### 1. Basit Arama
```
Query: "Where is the database connection configured?"
Response: "Database connection is configured in config/database.py, 
specifically in the DatabaseManager class (lines 15-45). 
The connection uses SQLAlchemy with connection pooling..."
```

### 2. Kod Anlama
```
Query: "How does the authentication middleware work?"
Response: "The authentication middleware is implemented in 
src/middleware/auth.py. It uses JWT tokens verified by the 
verify_token() function (lines 23-35). The middleware checks 
the Authorization header and validates the token..."
```

### 3. Bağımlılık Analizi
```
Query: "What external libraries are used for HTTP requests?"
Response: "The project uses 'requests' library (imported in 
src/api/client.py line 3) and 'httpx' for async requests 
(src/async_client.py line 5)..."
```

## Gelişmiş Özellikler (Opsiyonel)

### 1. Multi-Repository Support
- Birden fazla repo'yu aynı anda index etme
- Cross-repository search
- Repo-specific filtering

### 2. Code Change Tracking
- Git history analizi
- Değişen dosyaları re-index etme
- Incremental updates

### 3. Semantic Code Search
- Function signatures ile arama
- Variable/class name ile arama
- Comment-based search

### 4. Code Graph Analysis
- Import dependencies mapping
- Function call graph
- Class inheritance tree

### 5. Web Interface (Streamlit)
```python
# Basit bir Streamlit UI
- Repo URL input
- Query box
- Results with syntax highlighting
- File viewer
```

## Test Stratejisi

### Unit Tests
- Her modül için ayrı test
- Mock data ile testing
- Edge cases

### Integration Tests
- End-to-end indexing test
- Query pipeline test
- Real repo ile test (örnek: famous open source project)

### Performance Tests
- Large repo indexing (1000+ files)
- Query response time
- Memory usage

## Best Practices

1. **Error Handling**: Her external call için try-catch
2. **Logging**: Strukturel logging (JSON format)
3. **Rate Limiting**: GitHub API, LLM API için
4. **Caching**: Embeddings cache, file hash kontrolü
5. **Security**: API keys .env'de, .gitignore ile protect
6. **Documentation**: Docstrings, type hints, README

## Başlangıç İçin Minimal Viable Product (MVP)

**Phase 1: Core Functionality**
1. Single repo clone
2. Python dosyaları için basic parsing
3. ChromaDB ile basit indexing
4. CLI ile query (OpenAI kullanarak)

**Phase 2: Enhancement**
1. Multi-language support
2. Better chunking strategies
3. Metadata filtering
4. Progress tracking

**Phase 3: Advanced**
1. Multi-repo support
2. Web interface
3. Code graph analysis
4. Incremental updates

## Başlamak için İlk Adımlar

```bash
# 1. Proje oluştur
mkdir code-rag && cd code-rag

# 2. Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. Temel yapıyı oluştur
mkdir -p src/{indexer,retriever,llm,cli} data/{repos,chroma_db} config tests

# 4. Dependencies yükle
pip install -r requirements.txt

# 5. .env oluştur
echo "OPENAI_API_KEY=your-key-here" > .env
```

## Başarı Kriterleri

✅ Bir GitHub repo'yu başarıyla clone ve index edebiliyor
✅ "X fonksiyonu nerede?" gibi sorulara doğru cevap veriyor
✅ 1000+ dosyalı repo'yu makul sürede index edebiliyor (<5dk)
✅ Query response time < 3 saniye
✅ Kod örneklerini doğru file path ve line number'ları ile gösteriyor

## İlham Kaynakları

- Sweep AI: AI-powered code assistant
- GitHub Copilot: Code understanding
- Sourcegraph: Code search platform
- Cursor AI: RAG-based code editor

---

**Not**: Bu prompt ile Antigravity'ye projeyi oluşturmasını söyleyebilirsiniz. Detaylı açıklamalar sayesinde sistem tüm bileşenleri doğru şekilde implement edebilecektir.