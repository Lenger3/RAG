"""
main.py - GitHub RAG CLI interface
"""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

# Logging ayarları
logging.basicConfig(
    level=logging.WARNING,  # CLI'de sadece uyarı/hata göster
    format="%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="code-rag")
def cli():
    """
    🔍 Code RAG - GitHub repository'lerini doğal dil ile sorgula.

    \b
    Komutlar:
      index   Bir GitHub reposunu indexle
      query   Kod tabanını sorgula
      list    İndeksli repoları listele
      delete  Bir koleksiyonu sil
    """
    pass


@cli.command()
@click.option("--url", "-u", required=True, help="GitHub repo URL (ör: https://github.com/user/repo)")
@click.option("--collection", "-c", default=None, help="Collection adı (varsayılan: repo adı)")
@click.option(
    "--strategy",
    "-s",
    default="function",
    type=click.Choice(["function", "class", "file", "sliding"]),
    show_default=True,
    help="Chunking stratejisi",
)
@click.option("--max-chunk", default=1000, show_default=True, help="Maks chunk token boyutu")
@click.option("--embedding", default="local", type=click.Choice(["local", "openai"]), show_default=True)
def index(url: str, collection: str, strategy: str, max_chunk: int, embedding: str):
    """Bir GitHub reposunu clone et ve indexle."""
    from src.indexer.repo_cloner import (
        clone_repository, get_repo_info, list_code_files, extract_repo_name_from_url
    )
    from src.indexer.file_parser import read_file, extract_metadata
    from src.indexer.code_chunker import chunk_code
    from src.indexer.embedder import Embedder
    from src.retriever.vector_store import VectorStore

    repo_name = extract_repo_name_from_url(url)
    collection_name = collection or repo_name
    clone_path = str(Path("data/repos") / repo_name)

    console.print(Panel(
        f"[bold cyan]🚀 İndeksleme başlatılıyor[/bold cyan]\n"
        f"  Repo  : [yellow]{url}[/yellow]\n"
        f"  Koleksiyon: [green]{collection_name}[/green]\n"
        f"  Strateji: [blue]{strategy}[/blue]",
        border_style="cyan",
    ))

    # 1. Clone
    with console.status("[bold green]Repository clone ediliyor...[/bold green]"):
        try:
            clone_repository(url, clone_path)
        except Exception as e:
            console.print(f"[red]❌ Clone hatası: {e}[/red]")
            sys.exit(1)

    repo_info = get_repo_info(clone_path)
    console.print(f"[green]✓[/green] Clone tamamlandı: [bold]{repo_info['name']}[/bold] "
                  f"({repo_info['language']}, {repo_info['file_count']} dosya)")

    # 2. Dosyaları tara
    with console.status("[bold green]Kod dosyaları taranıyor...[/bold green]"):
        files = list_code_files(clone_path)

    console.print(f"[green]✓[/green] {len(files)} kod dosyası bulundu.")

    if not files:
        console.print("[yellow]⚠ İndekslenecek dosya bulunamadı.[/yellow]")
        return

    # 3. Chunk + embed + store
    embedder = Embedder(provider=embedding)
    vector_store = VectorStore()
    collection_obj = vector_store.initialize_collection(collection_name)

    all_chunks = []
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        parse_task = progress.add_task("[cyan]Dosyalar parse ediliyor...", total=len(files))

        for file_path in files:
            try:
                chunks = chunk_code(file_path, strategy=strategy, max_chunk_size=max_chunk)
                # Metadata'ya repo info ekle
                for chunk in chunks:
                    chunk["metadata"]["repo_name"] = repo_name
                    chunk["metadata"]["language"] = extract_metadata(file_path)["language"]
                all_chunks.extend(chunks)
            except Exception as e:
                logger.debug(f"Parse atlandı ({file_path}): {e}")
                skipped += 1
            progress.advance(parse_task)

    console.print(f"[green]✓[/green] {len(all_chunks)} chunk oluşturuldu ({skipped} dosya atlandı).")

    if not all_chunks:
        console.print("[yellow]⚠ Chunk oluşturulamadı.[/yellow]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        embed_task = progress.add_task("[magenta]Embedding oluşturuluyor...", total=len(all_chunks))

        batch_size = 64
        all_embeddings = []
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i: i + batch_size]
            embeddings = embedder.create_embeddings(batch, batch_size=batch_size)
            all_embeddings.extend(embeddings)
            progress.advance(embed_task, len(batch))

    console.print(f"[green]✓[/green] {len(all_embeddings)} embedding oluşturuldu.")

    with console.status("[bold green]Vektör veritabanına kaydediliyor...[/bold green]"):
        vector_store.add_chunks(collection_obj, all_chunks, all_embeddings)

    console.print(Panel(
        f"[bold green]✅ İndeksleme tamamlandı![/bold green]\n"
        f"  Koleksiyon : [cyan]{collection_name}[/cyan]\n"
        f"  Toplam chunk: [yellow]{len(all_chunks)}[/yellow]\n\n"
        f"Sorgu için:\n"
        f"  [bold]python -m src.cli.main query --collection {collection_name} \"sorunuz\"[/bold]",
        border_style="green",
    ))


@cli.command()
@click.argument("question")
@click.option("--collection", "-c", required=True, help="Sorgulanacak koleksiyon adı")
@click.option("--top-k", "-k", default=5, show_default=True, help="Kaç benzer chunk getirileceği")
@click.option("--no-llm", is_flag=True, help="LLM kullanma, sadece retrieve sonuçlarını göster")
@click.option("--stream", is_flag=True, help="LLM cevabını streaming modda göster")
@click.option("--embedding", default="local", type=click.Choice(["local", "openai"]), show_default=True)
def query(question: str, collection: str, top_k: int, no_llm: bool, stream: bool, embedding: str):
    """Kod tabanını doğal dil ile sorgula."""
    from src.indexer.embedder import Embedder
    from src.retriever.vector_store import VectorStore
    from src.retriever.query_engine import QueryEngine

    console.print(Panel(
        f"[bold cyan]🔍 Sorgu[/bold cyan]\n{question}",
        border_style="cyan",
    ))

    embedder = Embedder(provider=embedding)
    vector_store = VectorStore()

    # Collection var mı kontrol et
    col = vector_store.get_collection(collection)
    if col is None:
        console.print(f"[red]❌ Koleksiyon bulunamadı: '{collection}'[/red]")
        console.print("  Mevcut koleksiyonlar için: [bold]python -m src.cli.main list[/bold]")
        sys.exit(1)

    engine = QueryEngine(vector_store=vector_store, embedder=embedder, collection_name=collection)

    with console.status("[bold green]Benzer kod parçaları aranıyor...[/bold green]"):
        chunks, context = engine.search_and_build(question, top_k=top_k)

    if not chunks:
        console.print("[yellow]⚠ İlgili kod bulunamadı.[/yellow]")
        return

    # Retrieve sonuçlarını göster
    console.print(f"\n[bold]📄 Bulunan {len(chunks)} kod parçası:[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Dosya", style="cyan", no_wrap=False)
    table.add_column("Tip", style="green", width=10)
    table.add_column("İsim", style="yellow")
    table.add_column("Satırlar", style="blue", width=10)
    table.add_column("Benzerlik", style="red", width=10)

    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        fp = meta.get("file_path", "?")
        # Repo path'ini kısalt
        try:
            fp_short = str(Path(fp).relative_to(Path.cwd()))
        except Exception:
            fp_short = Path(fp).name

        table.add_row(
            str(i),
            fp_short,
            meta.get("chunk_type", "?"),
            meta.get("name", ""),
            f"{meta.get('line_start', '?')}-{meta.get('line_end', '?')}",
            f"{chunk.get('similarity', 0):.2f}",
        )

    console.print(table)

    if no_llm:
        # Context'i göster
        console.print("\n[bold]📝 Kod İçerikleri:[/bold]")
        for i, chunk in enumerate(chunks, 1):
            console.print(f"\n[dim]─── [{i}] {chunk['metadata'].get('file_path', '')} ───[/dim]")
            console.print(chunk["content"])
        return

    # LLM ile cevap üret
    try:
        from src.llm.generator import LLMGenerator
        generator = LLMGenerator()

        console.print("\n[bold]💬 AI Cevabı:[/bold]")

        if stream:
            console.print("")
            for token in generator.generate_stream(question, context):
                console.print(token, end="")
            console.print("")
        else:
            with console.status("[bold green]AI cevap üretiyor...[/bold green]"):
                answer = generator.generate_answer(question, context)
            console.print(Markdown(answer))

    except ValueError as e:
        console.print(f"\n[yellow]⚠ LLM kullanılamıyor: {e}[/yellow]")
        console.print("[dim]--no-llm flag'i ile sadece retrieve sonuçlarını görebilirsiniz.[/dim]")
    except Exception as e:
        err_str = str(e).lower()
        if "insufficient_quota" in err_str or "429" in err_str:
            console.print("\n[red]❌ OpenAI kota aşıldı (429 - insufficient_quota)[/red]")
            console.print("[dim]OpenAI hesabınızda kredi kalmamış. Seçenekler:[/dim]")
            console.print("  1. [cyan]https://platform.openai.com/account/billing[/cyan] adresinden kredi yükleyin")
            console.print(f"  2. [bold]python -m src.cli.main query --collection {collection} \"{question}\" --no-llm[/bold]")
        elif "api_key" in err_str or "authentication" in err_str:
            console.print("\n[red]❌ Geçersiz API key.[/red]")
            console.print("  .env dosyasında [bold]OPENAI_API_KEY[/bold]'i kontrol edin.")
        else:
            console.print(f"\n[red]❌ LLM hatası: {e}[/red]")
            console.print(f"  [bold]python -m src.cli.main query --collection {collection} \"{question}\" --no-llm[/bold]")


@cli.command(name="list")
def list_collections():
    """İndekslenmiş repository koleksiyonlarını listele."""
    from src.retriever.vector_store import VectorStore

    vector_store = VectorStore()
    collections = vector_store.list_collections()

    if not collections:
        console.print("[yellow]Henüz hiç koleksiyon yok.[/yellow]")
        console.print("  İndekslemek için: [bold]python -m src.cli.main index --url <github-url>[/bold]")
        return

    table = Table(title="📚 İndekslenmiş Repository'ler", show_header=True, header_style="bold cyan")
    table.add_column("Koleksiyon Adı", style="cyan")
    table.add_column("Chunk Sayısı", style="yellow", justify="right")

    for col in collections:
        table.add_row(col["name"], str(col["count"]))

    console.print(table)


@cli.command()
@click.option("--collection", "-c", required=True, help="Silinecek koleksiyon adı")
@click.option("--yes", "-y", is_flag=True, help="Onay sormadan sil")
def delete(collection: str, yes: bool):
    """Bir koleksiyonu ve tüm indexlenmiş verilerini sil."""
    from src.retriever.vector_store import VectorStore

    if not yes:
        confirmed = click.confirm(
            f"[bold red]{collection}[/bold red] koleksiyonu silinecek. Emin misiniz?",
            default=False,
        )
        if not confirmed:
            console.print("[yellow]İptal edildi.[/yellow]")
            return

    vector_store = VectorStore()
    success = vector_store.delete_collection(collection)
    if success:
        console.print(f"[green]✓[/green] Koleksiyon silindi: [bold]{collection}[/bold]")
    else:
        console.print(f"[red]❌ Silinemedi: '{collection}' bulunamadı.[/red]")


if __name__ == "__main__":
    cli()
