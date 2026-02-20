"""
test_code_chunker.py - code_chunker modülü için unit testler
"""

from pathlib import Path

import pytest

from src.indexer.code_chunker import chunk_code, count_tokens, _file_chunk, _sliding_chunks


class TestCountTokens:
    def test_simple(self):
        tokens = count_tokens("hello world")
        assert tokens > 0

    def test_empty(self):
        assert count_tokens("") == 0


class TestFileChunk:
    def test_returns_single_chunk(self, tmp_path):
        f = tmp_path / "small.py"
        f.write_text("x = 1\ny = 2\n")
        chunks = _file_chunk(str(f), "x = 1\ny = 2\n")
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["chunk_type"] == "file"


class TestChunkCode:
    def test_small_file_returns_one_chunk(self, tmp_path):
        code = "x = 1\n"
        f = tmp_path / "tiny.py"
        f.write_text(code)
        chunks = chunk_code(str(f), strategy="function", max_chunk_size=10000)
        assert len(chunks) >= 1
        assert all("content" in c for c in chunks)
        assert all("metadata" in c for c in chunks)

    def test_python_function_chunking(self, tmp_path):
        code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

def subtract(a, b):
    """Subtract b from a."""
    return a - b
'''
        f = tmp_path / "math.py"
        f.write_text(code)
        chunks = chunk_code(str(f), strategy="function", max_chunk_size=10000)

        chunk_types = [c["metadata"]["chunk_type"] for c in chunks]
        assert "function" in chunk_types

        func_names = [c["metadata"]["name"] for c in chunks if c["metadata"]["chunk_type"] == "function"]
        assert "add" in func_names
        assert "subtract" in func_names

    def test_class_chunking(self, tmp_path):
        code = '''
class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b
'''
        f = tmp_path / "calc.py"
        f.write_text(code)
        chunks = chunk_code(str(f), strategy="class", max_chunk_size=10000)
        assert len(chunks) >= 1
        class_chunks = [c for c in chunks if c["metadata"]["chunk_type"] == "class"]
        assert len(class_chunks) >= 1

    def test_metadata_has_required_fields(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        chunks = chunk_code(str(f))
        for chunk in chunks:
            meta = chunk["metadata"]
            assert "file_path" in meta
            assert "chunk_type" in meta
            assert "line_start" in meta
            assert "line_end" in meta

    def test_non_python_uses_sliding(self, tmp_path):
        content = "\n".join([f"line {i}: some content here" for i in range(200)])
        f = tmp_path / "large.js"
        f.write_text(content)
        chunks = chunk_code(str(f), strategy="function", max_chunk_size=50)
        assert len(chunks) > 1
        for c in chunks:
            assert c["metadata"]["chunk_type"] == "sliding"

    def test_empty_file_returns_empty(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        chunks = chunk_code(str(f))
        assert chunks == []
