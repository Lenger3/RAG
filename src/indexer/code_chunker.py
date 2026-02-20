"""
code_chunker.py - Kodu anlamlı parçalara (chunk) bölen modül
"""

import ast
import logging
from pathlib import Path
from typing import Optional

import tiktoken

from src.indexer.file_parser import read_file, parse_python_file

logger = logging.getLogger(__name__)

try:
    _tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    _tokenizer = None


def count_tokens(text: str) -> int:
    """Token sayısını döner."""
    if _tokenizer:
        return len(_tokenizer.encode(text))
    return len(text.split())


def chunk_code(
    file_path: str,
    strategy: str = "function",
    max_chunk_size: int = 1000,
    overlap: int = 100,
) -> list:
    """
    Kod dosyasını anlamlı chunk'lara böler.

    Args:
        file_path: Dosya yolu
        strategy: 'function', 'class', 'file', 'sliding'
        max_chunk_size: Maksimum token sayısı
        overlap: Sliding window için overlap token sayısı

    Returns:
        Liste: [{'content': str, 'metadata': {...}}, ...]
    """
    ext = Path(file_path).suffix.lower()
    content = read_file(file_path)
    if not content:
        return []

    # Strateji açıkça 'file' ise veya çok küçükse tek chunk yap
    if strategy == "file":
        return _file_chunk(file_path, content)

    # Python dosyaları için AST bazlı chunking
    if ext == ".py" and strategy in ("function", "class"):
        chunks = _python_chunks(file_path, content, strategy, max_chunk_size)
        if chunks:
            return chunks
        # AST başarısız olursa file-chunk
        return _file_chunk(file_path, content)

    # Büyük dosyalar için sliding window, küçükler için file-chunk
    token_count = count_tokens(content)
    if token_count <= max_chunk_size:
        return _file_chunk(file_path, content)

    return _sliding_chunks(file_path, content, max_chunk_size, overlap)


# --- Chunking stratejileri ---

def _file_chunk(file_path: str, content: str) -> list:
    """Tüm dosyayı tek chunk olarak döner."""
    lines = content.splitlines()
    return [{
        "content": content,
        "metadata": {
            "file_path": file_path,
            "chunk_type": "file",
            "name": Path(file_path).name,
            "line_start": 1,
            "line_end": len(lines),
        }
    }]


def _python_chunks(
    file_path: str,
    content: str,
    strategy: str,
    max_chunk_size: int,
) -> list:
    """Python dosyasını AST ile fonksiyon/class seviyesinde chunk'a böler."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    lines = content.splitlines()
    chunks = []

    # Top-level node'ları (fonksiyon ve class) bul
    top_nodes = [
        node for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    if not top_nodes:
        return []

    for node in top_nodes:
        start = node.lineno - 1
        end = node.end_lineno
        node_lines = lines[start:end]
        chunk_content = "\n".join(node_lines)

        # Büyük node'ları sub-chunk'lara böl
        if count_tokens(chunk_content) > max_chunk_size:
            if isinstance(node, ast.ClassDef) and strategy == "class":
                # Class metodlarını ayrı chunk'a al
                sub_chunks = _split_class_methods(file_path, node, lines, max_chunk_size)
                chunks.extend(sub_chunks)
                continue

        chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"
        chunks.append({
            "content": chunk_content,
            "metadata": {
                "file_path": file_path,
                "chunk_type": chunk_type,
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
            }
        })

    # Module-level kod (imports, top-level statements)
    module_doc = ast.get_docstring(tree) or ""
    module_lines = []
    node_line_ranges = {(n.lineno, n.end_lineno) for n in top_nodes}
    for i, line in enumerate(lines, start=1):
        in_node = any(start <= i <= end for start, end in node_line_ranges)
        if not in_node:
            module_lines.append(line)

    module_content = "\n".join(module_lines).strip()
    if module_content:
        chunks.insert(0, {
            "content": module_content,
            "metadata": {
                "file_path": file_path,
                "chunk_type": "module",
                "name": Path(file_path).stem + " (module)",
                "line_start": 1,
                "line_end": len(lines),
            }
        })

    return chunks


def _split_class_methods(
    file_path: str,
    class_node: ast.ClassDef,
    lines: list,
    max_chunk_size: int,
) -> list:
    """Büyük class'ı metod bazlı chunk'lara böler."""
    chunks = []

    # Class header (metod harici kısım)
    method_nodes = [
        n for n in ast.iter_child_nodes(class_node)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    # Class docstring + signature
    class_header_end = method_nodes[0].lineno - 1 if method_nodes else class_node.end_lineno
    header_lines = lines[class_node.lineno - 1: class_header_end]
    if header_lines:
        chunks.append({
            "content": "\n".join(header_lines),
            "metadata": {
                "file_path": file_path,
                "chunk_type": "class_header",
                "name": class_node.name,
                "line_start": class_node.lineno,
                "line_end": class_header_end,
            }
        })

    # Her metod ayrı chunk
    for method in method_nodes:
        method_content = "\n".join(lines[method.lineno - 1: method.end_lineno])
        chunks.append({
            "content": method_content,
            "metadata": {
                "file_path": file_path,
                "chunk_type": "method",
                "name": f"{class_node.name}.{method.name}",
                "line_start": method.lineno,
                "line_end": method.end_lineno,
            }
        })

    return chunks


def _sliding_chunks(
    file_path: str,
    content: str,
    max_chunk_size: int,
    overlap: int,
) -> list:
    """Sliding window ile satır bazlı chunk'lar oluşturur."""
    lines = content.splitlines()
    chunks = []
    i = 0
    chunk_idx = 0

    while i < len(lines):
        chunk_lines = []
        token_count = 0

        j = i
        while j < len(lines) and token_count < max_chunk_size:
            line_tokens = count_tokens(lines[j])
            if token_count + line_tokens > max_chunk_size and chunk_lines:
                break
            chunk_lines.append(lines[j])
            token_count += line_tokens
            j += 1

        if not chunk_lines:
            # Tek satır çok büyükse zorla ekle
            chunk_lines = [lines[i]]
            j = i + 1

        chunk_content = "\n".join(chunk_lines)
        chunks.append({
            "content": chunk_content,
            "metadata": {
                "file_path": file_path,
                "chunk_type": "sliding",
                "name": f"{Path(file_path).name} chunk {chunk_idx}",
                "line_start": i + 1,
                "line_end": i + len(chunk_lines),
            }
        })

        # Overlap: bir önceki chunk'ın sonundaki satırları tekrar ekle
        overlap_lines = max(0, len(chunk_lines) - overlap // max(1, count_tokens("\n".join(chunk_lines)) // max(1, len(chunk_lines))))
        i = max(i + 1, j - overlap_lines)
        chunk_idx += 1

    return chunks
