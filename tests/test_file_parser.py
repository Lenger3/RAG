"""
test_file_parser.py - file_parser modülü için unit testler
"""

import tempfile
from pathlib import Path

import pytest

from src.indexer.file_parser import (
    read_file,
    parse_python_file,
    extract_metadata,
    get_line_count,
)


class TestReadFile:
    def test_reads_utf8(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("# Merhaba dünya\nx = 1", encoding="utf-8")
        content = read_file(str(f))
        assert "Merhaba dünya" in content

    def test_returns_none_nonexistent(self):
        result = read_file("/nonexistent/path/file.py")
        assert result is None

    def test_reads_latin1(self, tmp_path):
        f = tmp_path / "latin.py"
        f.write_bytes("# caf\xe9\nx = 1".encode("latin-1"))
        content = read_file(str(f))
        assert content is not None
        assert "x = 1" in content


class TestParsePythonFile:
    def test_parses_functions(self, tmp_path):
        code = '''
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello {name}"

def world():
    pass
'''
        f = tmp_path / "test.py"
        f.write_text(code)
        result = parse_python_file(str(f))

        func_names = [fn["name"] for fn in result["functions"]]
        assert "hello" in func_names
        assert "world" in func_names

    def test_parses_classes(self, tmp_path):
        code = '''
class MyClass(Base):
    """A sample class."""

    def method(self):
        pass
'''
        f = tmp_path / "test.py"
        f.write_text(code)
        result = parse_python_file(str(f))

        class_names = [c["name"] for c in result["classes"]]
        assert "MyClass" in class_names
        assert result["classes"][0]["bases"] == ["Base"]

    def test_parses_imports(self, tmp_path):
        code = "import os\nfrom pathlib import Path\n"
        f = tmp_path / "test.py"
        f.write_text(code)
        result = parse_python_file(str(f))

        modules = [i["module"] for i in result["imports"]]
        assert "os" in modules
        assert "pathlib" in modules

    def test_handles_syntax_error(self, tmp_path):
        code = "def broken(:\n    pass\n"
        f = tmp_path / "bad.py"
        f.write_text(code)
        result = parse_python_file(str(f))
        # Hata olsa bile boş dict dönmeli
        assert result["functions"] == []
        assert result["classes"] == []

    def test_module_docstring(self, tmp_path):
        code = '"""Module docstring."""\n\nx = 1\n'
        f = tmp_path / "test.py"
        f.write_text(code)
        result = parse_python_file(str(f))
        assert result["module_docstring"] == "Module docstring."


class TestExtractMetadata:
    def test_python_language(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("x = 1")
        meta = extract_metadata(str(f))
        assert meta["language"] == "python"
        assert meta["extension"] == ".py"

    def test_markdown_language(self, tmp_path):
        f = tmp_path / "README.md"
        f.write_text("# Hello")
        meta = extract_metadata(str(f))
        assert meta["language"] == "markdown"

    def test_size_bytes(self, tmp_path):
        content = "x" * 100
        f = tmp_path / "file.py"
        f.write_text(content)
        meta = extract_metadata(str(f))
        assert meta["size_bytes"] == 100


class TestGetLineCount:
    def test_count(self):
        assert get_line_count("line1\nline2\nline3") == 3

    def test_empty(self):
        assert get_line_count("") == 0  # splitlines("") == []

    def test_single_line(self):
        assert get_line_count("single") == 1
