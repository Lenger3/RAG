"""
file_parser.py - Dosya okuma, encoding detection ve Python AST parsing
"""

import ast
import logging
import os
from pathlib import Path
from typing import Optional

import chardet

logger = logging.getLogger(__name__)


def read_file(file_path: str) -> Optional[str]:
    """
    Dosyayı uygun encoding ile okur.

    Args:
        file_path: Dosya yolu

    Returns:
        Dosya içeriği string olarak, başarısız olursa None
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"Dosya bulunamadı: {file_path}")
        return None

    # Önce UTF-8 dene
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        pass

    # chardet ile encoding tespiti
    try:
        raw = path.read_bytes()
        detected = chardet.detect(raw)
        encoding = detected.get("encoding") or "latin-1"
        return raw.decode(encoding, errors="replace")
    except Exception as e:
        logger.error(f"Dosya okunamadı {file_path}: {e}")
        return None


def parse_python_file(file_path: str) -> dict:
    """
    Python dosyasını AST ile parse eder; fonksiyon, class ve import bilgilerini çıkarır.

    Args:
        file_path: .py dosyası yolu

    Returns:
        {
            'functions': [...],
            'classes': [...],
            'imports': [...],
            'module_docstring': str,
        }
    """
    content = read_file(file_path)
    if content is None:
        return {"functions": [], "classes": [], "imports": [], "module_docstring": ""}

    result = {
        "functions": [],
        "classes": [],
        "imports": [],
        "module_docstring": "",
    }

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.warning(f"Syntax hatası {file_path}: {e}")
        return result

    # Module docstring
    result["module_docstring"] = ast.get_docstring(tree) or ""

    for node in ast.walk(tree):
        # Fonksiyonlar
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Sadece top-level veya class içindeki metodlar
            func_info = {
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "docstring": ast.get_docstring(node) or "",
                "args": [arg.arg for arg in node.args.args],
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "decorators": [_get_decorator_name(d) for d in node.decorator_list],
            }
            result["functions"].append(func_info)

        # Sınıflar
        elif isinstance(node, ast.ClassDef):
            class_info = {
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "docstring": ast.get_docstring(node) or "",
                "bases": [_get_name(b) for b in node.bases],
                "methods": [],
            }
            for item in ast.walk(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item != node:
                    class_info["methods"].append(item.name)
            result["classes"].append(class_info)

        # İmportlar
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append({
                    "type": "import",
                    "module": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result["imports"].append({
                    "type": "from_import",
                    "module": module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                })

    return result


def extract_metadata(file_path: str) -> dict:
    """
    Dosya hakkında metadata bilgisi döner.

    Args:
        file_path: Dosya yolu

    Returns:
        Metadata dict
    """
    path = Path(file_path)
    stat = path.stat() if path.exists() else None

    ext = path.suffix.lower()
    language_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".sh": "shell",
        ".toml": "toml",
        ".txt": "text",
    }

    return {
        "file_path": str(file_path),
        "file_name": path.name,
        "extension": ext,
        "language": language_map.get(ext, "unknown"),
        "size_bytes": stat.st_size if stat else 0,
        "last_modified": stat.st_mtime if stat else 0.0,
    }


def get_line_count(content: str) -> int:
    """İçerikteki satır sayısını döner."""
    return len(content.splitlines())


# --- Private helpers ---

def _get_decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_get_name(node.value)}.{node.attr}"
    elif isinstance(node, ast.Call):
        return _get_decorator_name(node.func)
    return "unknown"


def _get_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_get_name(node.value)}.{node.attr}"
    return "unknown"
