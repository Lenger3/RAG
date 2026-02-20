"""
test_repo_cloner.py - repo_cloner modülü için unit testler
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.indexer.repo_cloner import (
    extract_repo_name_from_url,
    list_code_files,
    get_repo_info,
    _is_binary,
    _detect_primary_language,
)


class TestExtractRepoNameFromUrl:
    def test_standard_url(self):
        assert extract_repo_name_from_url("https://github.com/user/myrepo") == "myrepo"

    def test_git_suffix(self):
        assert extract_repo_name_from_url("https://github.com/user/myrepo.git") == "myrepo"

    def test_trailing_slash(self):
        assert extract_repo_name_from_url("https://github.com/user/myrepo/") == "myrepo"


class TestListCodeFiles:
    def test_filters_supported_extensions(self, tmp_path):
        # .py dosyası oluştur
        (tmp_path / "hello.py").write_text("print('hello')")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")

        # .git dizini oluştur (atlanmalı)
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")

        # Mock git repo (ls-files desteği olmadan)
        with patch("src.indexer.repo_cloner.git.Repo") as mock_repo:
            mock_repo.return_value.git.ls_files.side_effect = Exception("not a git repo")
            files = list_code_files(str(tmp_path), extensions=[".py", ".json"])

        file_names = [Path(f).name for f in files]
        assert "hello.py" in file_names
        assert "data.json" in file_names
        assert "image.png" not in file_names

    def test_skips_git_directory(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1")
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main")

        with patch("src.indexer.repo_cloner.git.Repo") as mock_repo:
            mock_repo.return_value.git.ls_files.side_effect = Exception()
            files = list_code_files(str(tmp_path), extensions=[".py"])

        assert all(".git" not in f for f in files)


class TestIsBinary:
    def test_text_file(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello(): pass")
        assert _is_binary(f) is False

    def test_binary_file(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02\x03")
        assert _is_binary(f) is True


class TestDetectPrimaryLanguage:
    def test_python_project(self, tmp_path):
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text("x = 1")
        (tmp_path / "readme.go").write_text("package main")

        lang = _detect_primary_language(tmp_path)
        assert lang == "Python"

    def test_unknown_project(self, tmp_path):
        (tmp_path / "Makefile").write_text("all: build")
        lang = _detect_primary_language(tmp_path)
        assert lang == "Unknown"
