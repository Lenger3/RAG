"""
tui.py - Code RAG Terminal Kullanıcı Arayüzü (Textual)
Çalıştır: python -m src.ui.tui
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListView,
    ListItem,
    Markdown,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_collections() -> list[dict]:
    try:
        from src.retriever.vector_store import VectorStore
        return VectorStore().list_collections()
    except Exception:
        return []


# ── Pane Widgets ──────────────────────────────────────────────────────────────

class QueryPane(Static):
    DEFAULT_CSS = """
    QueryPane {
        height: 1fr;
        layout: vertical;
    }
    #query_form {
        height: auto;
        padding: 1 2;
        border-bottom: solid $accent-darken-2;
    }
    #query_form Label { color: $text-muted; margin-top: 1; }
    #query_form Input { margin-bottom: 1; }
    #query_form Select { margin-bottom: 1; }
    #query_buttons { height: auto; }
    #query_buttons Button { margin-right: 1; }
    #results_area {
        height: 1fr;
        padding: 1 2;
    }
    #result_log {
        height: 1fr;
        border: solid $accent-darken-2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="query_form"):
            yield Label("Koleksiyon:")
            yield Select([], id="col_select", prompt="Koleksiyon seçin...")
            yield Label("Soru:")
            yield Input(placeholder="Kodda ne arıyorsunuz?", id="question_input")
            with Horizontal(id="query_buttons"):
                yield Button("🔍 Sorgula + LLM", id="query_llm_btn", variant="primary")
                yield Button("📄 Sadece Ara", id="query_nollm_btn", variant="default")
        with Vertical(id="results_area"):
            yield RichLog(id="result_log", highlight=True, markup=True, wrap=True)


class IndexPane(Static):
    DEFAULT_CSS = """
    IndexPane {
        height: 1fr;
        layout: vertical;
    }
    #index_form {
        height: auto;
        padding: 1 2;
        border-bottom: solid $accent-darken-2;
    }
    #index_form Label { color: $text-muted; margin-top: 1; }
    #index_form Input { margin-bottom: 1; }
    #index_form Select { margin-bottom: 1; }
    #index_btn { margin-top: 1; width: 20; }
    #index_log {
        height: 1fr;
        margin: 1 2;
        border: solid $accent-darken-2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="index_form"):
            yield Label("GitHub URL:")
            yield Input(placeholder="https://github.com/kullanici/repo", id="index_url")
            yield Label("Koleksiyon adı (opsiyonel):")
            yield Input(placeholder="repo adı otomatik alınır", id="index_col_name")
            yield Label("Chunking stratejisi:")
            yield Select(
                [
                    ("function — fonksiyon bazlı (önerilen)", "function"),
                    ("class — sınıf bazlı", "class"),
                    ("file — dosya bazlı", "file"),
                    ("sliding — kayan pencere", "sliding"),
                ],
                value="function",
                id="index_strategy",
            )
            yield Button("🚀 İndeksle", id="index_btn", variant="success")
        yield RichLog(id="index_log", highlight=True, markup=True, wrap=True)


class AboutPane(Static):
    DEFAULT_CSS = """
    AboutPane {
        height: 1fr;
        padding: 2 4;
        overflow-y: scroll;
    }
    """

    def compose(self) -> ComposeResult:
        yield Markdown("""
# Code RAG 🔍

**Tamamen offline** çalışan GitHub kod arama sistemi.

## Nasıl Çalışır?

1. **📥 İndeksle** sekmesine geçin, GitHub URL'si girin ve İndeksle'ye basın
2. Sistem repo'yu clone eder, kodu chunk'lara böler ve ChromaDB'ye saklar
3. **🔍 Sorgula** sekmesinden doğal dil ile arama yapın
4. Sonuçlar + Ollama (yerel LLM) ile Türkçe cevap oluşturulur

## Gereksinimler

- **Ollama** çalışıyor olmalı → [ollama.com](https://ollama.com)
- Model kurulu olmalı: `ollama pull qwen2.5:3b`

## Kısayollar

| Tuş | İşlev |
|-----|-------|
| `q` | Çıkış |
| `r` | Koleksiyonları yenile |
| `Enter` | Sorgula (soru kutusunda) |
| `Tab` | Widget'lar arası geç |
""")


class SideBar(Static):
    DEFAULT_CSS = """
    SideBar {
        width: 28;
        height: 1fr;
        border-right: solid $accent-darken-2;
        padding: 0 1;
        layout: vertical;
    }
    SideBar Label.section {
        color: $accent;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }
    SideBar ListView {
        height: 1fr;
        border: none;
    }
    SideBar Button {
        width: 1fr;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Koleksiyonlar", classes="section")
        yield ListView(id="collection_listview")
        yield Button("🔄 Yenile", id="refresh_btn", variant="default")
        yield Button("🗑  Sil", id="delete_btn", variant="error")

    def refresh_list(self) -> None:
        lv = self.query_one("#collection_listview", ListView)
        lv.clear()
        cols = _get_collections()
        if not cols:
            lv.append(ListItem(Label("[dim]Henüz koleksiyon yok[/dim]")))
        else:
            for c in cols:
                lv.append(
                    ListItem(
                        Label(f"[cyan]{c['name']}[/cyan]  [dim]{c['count']} chunk[/dim]"),
                        id=f"col_{c['name']}"
                    )
                )


# ── Main App ──────────────────────────────────────────────────────────────────

class CodeRagApp(App):
    TITLE = "Code RAG 🔍"
    SUB_TITLE = "GitHub Kod Arama — Tamamen Yerel"

    CSS = """
    Screen { layout: horizontal; }
    #main { width: 1fr; height: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "Çıkış"),
        Binding("r", "refresh", "Yenile"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield SideBar(id="sidebar")
            with TabbedContent(id="main"):
                with TabPane("🔍 Sorgula", id="tab_query"):
                    yield QueryPane(id="query_pane")
                with TabPane("📥 İndeksle", id="tab_index"):
                    yield IndexPane(id="index_pane")
                with TabPane("ℹ️  Hakkında", id="tab_about"):
                    yield AboutPane(id="about_pane")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_all()

    def _refresh_all(self) -> None:
        """Koleksiyon listesini ve select'i güncelle."""
        self.query_one(SideBar).refresh_list()

        cols = _get_collections()
        options = [(c["name"], c["name"]) for c in cols]
        try:
            sel = self.query_one("#col_select", Select)
            sel.set_options(options)
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self._refresh_all()
        self.notify("Koleksiyonlar yenilendi", severity="information")

    # ── Sidebar Buttons ───────────────────────────────────────────────────────

    @on(Button.Pressed, "#refresh_btn")
    def on_refresh_btn(self) -> None:
        self._refresh_all()
        self.notify("Yenilendi", severity="information")

    @on(Button.Pressed, "#delete_btn")
    def on_delete_btn(self) -> None:
        try:
            sel = self.query_one("#col_select", Select)
            if sel.value == Select.BLANK:
                self.notify("Önce Sorgula sekmesinden koleksiyon seçin", severity="warning")
                return
            collection = str(sel.value)
            from src.retriever.vector_store import VectorStore
            VectorStore().delete_collection(collection)
            self.notify(f"'{collection}' silindi", severity="warning")
            self._refresh_all()
        except Exception as e:
            self.notify(f"Silinemedi: {e}", severity="error")

    # ── Query Buttons ─────────────────────────────────────────────────────────

    @on(Button.Pressed, "#query_llm_btn")
    def on_query_llm(self) -> None:
        self._run_query(use_llm=True)

    @on(Button.Pressed, "#query_nollm_btn")
    def on_query_nollm(self) -> None:
        self._run_query(use_llm=False)

    @on(Input.Submitted, "#question_input")
    def on_question_enter(self, event: Input.Submitted) -> None:
        self._run_query(use_llm=True)

    # ── Index Button ──────────────────────────────────────────────────────────

    @on(Button.Pressed, "#index_btn")
    def on_index_btn(self) -> None:
        self._run_index()

    # ── Workers ───────────────────────────────────────────────────────────────

    @work(thread=True)
    def _run_query(self, use_llm: bool) -> None:
        log = self.query_one("#result_log", RichLog)
        self.call_from_thread(log.clear)

        sel = self.query_one("#col_select", Select)
        question = self.query_one("#question_input", Input).value.strip()

        if sel.value == Select.BLANK:
            self.call_from_thread(self.notify, "Koleksiyon seçin", severity="warning")
            return
        if not question:
            self.call_from_thread(self.notify, "Soru girin", severity="warning")
            return

        collection = str(sel.value)
        self.call_from_thread(log.write, f"[bold cyan]🔍 Aranıyor:[/bold cyan] {question}\n\n")

        try:
            from src.indexer.embedder import Embedder
            from src.retriever.vector_store import VectorStore
            from src.retriever.query_engine import QueryEngine

            engine = QueryEngine(
                vector_store=VectorStore(),
                embedder=Embedder(),
                collection_name=collection,
            )
            chunks, context = engine.search_and_build(question)

            if not chunks:
                self.call_from_thread(log.write, "[yellow]⚠ İlgili kod bulunamadı.[/yellow]\n")
                return

            self.call_from_thread(log.write, f"[bold]📄 {len(chunks)} kod parçası bulundu:[/bold]\n\n")
            for i, chunk in enumerate(chunks, 1):
                meta = chunk["metadata"]
                fname = Path(meta.get("file_path", "?")).name
                sim = chunk.get("similarity", 0)
                name = meta.get("name", fname)
                lines = f"{meta.get('line_start','?')}-{meta.get('line_end','?')}"
                self.call_from_thread(
                    log.write,
                    f"  [green]{i}.[/green] [cyan]{fname}[/cyan]  [bold]{name}[/bold]"
                    f"  satır [blue]{lines}[/blue]  benzerlik [red]{sim:.2f}[/red]\n"
                )

            self.call_from_thread(log.write, "\n[dim]────────────────────────────────────[/dim]\n")
            for i, chunk in enumerate(chunks, 1):
                fp = Path(chunk["metadata"].get("file_path", "")).name
                self.call_from_thread(log.write, f"\n[bold dim]── [{i}] {fp} ──[/bold dim]\n")
                self.call_from_thread(log.write, chunk["content"] + "\n")

            if use_llm:
                self.call_from_thread(log.write, "\n[dim]────────────────────────────────────[/dim]\n")
                self.call_from_thread(log.write, "[bold magenta]💬 AI Yanıtı (Ollama):[/bold magenta]\n\n")
                try:
                    from src.llm.generator import LLMGenerator
                    gen = LLMGenerator()
                    for token in gen.generate_stream(question, context):
                        self.call_from_thread(log.write, token)
                    self.call_from_thread(log.write, "\n")
                except Exception as e:
                    err = str(e).lower()
                    if "connection refused" in err or "connecterror" in err:
                        self.call_from_thread(
                            log.write,
                            "\n[red]❌ Ollama çalışmıyor![/red]\n"
                            "  Önce başlatın: [bold]ollama serve[/bold]\n"
                            "  Model kurulumu: [bold]ollama pull qwen2.5:3b[/bold]\n"
                        )
                    else:
                        self.call_from_thread(log.write, f"\n[red]❌ LLM hatası: {e}[/red]\n")

        except Exception as e:
            self.call_from_thread(log.write, f"[red]❌ Hata: {e}[/red]\n")

    @work(thread=True)
    def _run_index(self) -> None:
        log = self.query_one("#index_log", RichLog)
        self.call_from_thread(log.clear)

        url = self.query_one("#index_url", Input).value.strip()
        col_name_input = self.query_one("#index_col_name", Input).value.strip()
        strategy = str(self.query_one("#index_strategy", Select).value)

        if not url:
            self.call_from_thread(self.notify, "GitHub URL girin", severity="warning")
            return

        self.call_from_thread(log.write, f"[bold cyan]🚀 İndeksleme başlatılıyor[/bold cyan]\nURL: {url}\n\n")

        try:
            from src.indexer.repo_cloner import (
                clone_repository, get_repo_info, list_code_files, extract_repo_name_from_url
            )
            from src.indexer.file_parser import extract_metadata
            from src.indexer.code_chunker import chunk_code
            from src.indexer.embedder import Embedder
            from src.retriever.vector_store import VectorStore

            repo_name = extract_repo_name_from_url(url)
            collection = col_name_input or repo_name
            clone_path = str(Path("data/repos") / repo_name)

            self.call_from_thread(log.write, f"[green]→[/green] Clone: [cyan]{repo_name}[/cyan]\n")
            clone_repository(url, clone_path)
            info = get_repo_info(clone_path)
            self.call_from_thread(
                log.write,
                f"[green]✓[/green] Clone tamamlandı ({info['file_count']} dosya, {info['language']})\n"
            )

            files = list_code_files(clone_path)
            self.call_from_thread(log.write, f"[green]→[/green] {len(files)} dosya chunk'lanıyor...\n")

            all_chunks, skipped = [], 0
            for fp in files:
                try:
                    chunks = chunk_code(fp, strategy=strategy, max_chunk_size=1000)
                    for chunk in chunks:
                        chunk["metadata"]["repo_name"] = repo_name
                        chunk["metadata"]["language"] = extract_metadata(fp)["language"]
                    all_chunks.extend(chunks)
                except Exception:
                    skipped += 1

            self.call_from_thread(
                log.write,
                f"[green]✓[/green] {len(all_chunks)} chunk ({skipped} dosya atlandı)\n"
            )
            self.call_from_thread(log.write, "[green]→[/green] Embedding oluşturuluyor...\n")

            embedder = Embedder()
            all_embeddings = []
            batch_size = 64
            total = len(all_chunks)
            for i in range(0, total, batch_size):
                batch = all_chunks[i: i + batch_size]
                embeddings = embedder.create_embeddings(batch, batch_size=batch_size)
                all_embeddings.extend(embeddings)
                pct = min(100, int((i + len(batch)) / total * 100))
                self.call_from_thread(log.write, f"  [{pct}%]\r")

            self.call_from_thread(log.write, f"\n[green]✓[/green] {len(all_embeddings)} embedding hazır\n")
            self.call_from_thread(log.write, "[green]→[/green] Veritabanına kaydediliyor...\n")

            vs = VectorStore()
            col_obj = vs.initialize_collection(collection)
            vs.add_chunks(col_obj, all_chunks, all_embeddings)

            self.call_from_thread(
                log.write,
                f"\n[bold green]✅ Tamamlandı![/bold green]\n"
                f"  Koleksiyon : [cyan]{collection}[/cyan]\n"
                f"  Chunk sayısı: [yellow]{len(all_chunks)}[/yellow]\n\n"
                f"Şimdi [bold]🔍 Sorgula[/bold] sekmesine geçebilirsiniz.\n"
            )
            self.call_from_thread(self.notify, f"'{collection}' indexlendi!", severity="information")
            self.call_from_thread(self._refresh_all)

        except Exception as e:
            self.call_from_thread(log.write, f"\n[bold red]❌ Hata:[/bold red] {e}\n")
            self.call_from_thread(self.notify, f"Hata: {e}", severity="error")


def main():
    CodeRagApp().run()


if __name__ == "__main__":
    main()
