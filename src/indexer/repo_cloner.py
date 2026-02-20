"""
repo_cloner.py - GitHub repository clone ve dosya listeleme işlemleri
"""

import os
import logging
import subprocess
from pathlib import Path
from typing import Optional

import git
import yaml

logger = logging.getLogger(__name__)

# Config yükle
_config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

EXCLUDED_EXTENSIONS = set(_config["git"]["excluded_extensions"])
SUPPORTED_EXTENSIONS = set(_config.get("supported_extensions", []))
CLONE_DEPTH = _config["git"]["clone_depth"]


def clone_repository(repo_url: str, target_path: str) -> str:
    """
    GitHub repository'sini local path'e clone eder.

    Args:
        repo_url: GitHub repo URL (https://github.com/user/repo)
        target_path: Clone edilecek hedef dizin

    Returns:
        Clone edilen repo'nun path'i
    """
    target = Path(target_path)

    # Zaten clone edilmiş mi kontrol et
    if target.exists() and (target / ".git").exists():
        logger.info(f"Repo zaten mevcut: {target}. Güncelleniyor...")
        try:
            repo = git.Repo(target)
            repo.remotes.origin.pull()
            logger.info("Repo başarıyla güncellendi.")
        except Exception as e:
            logger.warning(f"Pull başarısız: {e}. Mevcut repo kullanılıyor.")
        return str(target)

    target.mkdir(parents=True, exist_ok=True)

    logger.info(f"Cloning: {repo_url} -> {target}")
    try:
        git.Repo.clone_from(
            repo_url,
            target,
            depth=CLONE_DEPTH,
            multi_options=["--single-branch"],
        )
        logger.info(f"Clone başarılı: {target}")
    except git.exc.GitCommandError as e:
        logger.error(f"Clone hatası: {e}")
        raise RuntimeError(f"Repository clone edilemedi: {e}") from e

    return str(target)


def get_repo_info(repo_path: str) -> dict:
    """
    Repo hakkında metadata bilgisi çıkarır.

    Args:
        repo_path: Lokal repo dizini

    Returns:
        Repo metadata dict'i
    """
    path = Path(repo_path)
    info = {
        "name": path.name,
        "path": str(path),
        "description": "",
        "language": _detect_primary_language(path),
        "file_count": 0,
        "total_size_bytes": 0,
    }

    # README varsa açıklama al
    for readme_name in ["README.md", "README.rst", "README.txt", "readme.md"]:
        readme_path = path / readme_name
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8", errors="ignore")
                # İlk non-empty satırı açıklama olarak al
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                if lines:
                    # Markdown başlıklarını temizle
                    first_line = lines[0].lstrip("#").strip()
                    info["description"] = first_line[:200]
            except Exception:
                pass
            break

    # Dosya sayısı ve toplam boyut
    try:
        repo = git.Repo(repo_path)
        tracked_files = list(repo.git.ls_files().splitlines())
        info["file_count"] = len(tracked_files)
        total = 0
        for f in tracked_files:
            fp = path / f
            if fp.is_file():
                total += fp.stat().st_size
        info["total_size_bytes"] = total
    except Exception as e:
        logger.warning(f"git ls-files hatası: {e}")

    return info


def list_code_files(repo_path: str, extensions: Optional[list] = None) -> list:
    """
    Repo içindeki kod dosyalarını listeler. Binary ve excluded dosyaları atlar.

    Args:
        repo_path: Lokal repo dizini
        extensions: Dahil edilecek uzantılar (None ise config'den alır)

    Returns:
        Dosya path'lerinin listesi
    """
    if extensions is None:
        extensions = list(SUPPORTED_EXTENSIONS)

    ext_set = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    path = Path(repo_path)

    # git ls-files ile tracked dosyaları al (.gitignore'u otomatik respect eder)
    try:
        repo = git.Repo(repo_path)
        tracked = set(repo.git.ls_files().splitlines())
    except Exception:
        tracked = None

    code_files = []
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue

        # .git dizinini atla
        if ".git" in file_path.parts:
            continue

        # Tracked files kontrolü
        if tracked is not None:
            rel = str(file_path.relative_to(path))
            if rel not in tracked:
                continue

        suffix = file_path.suffix.lower()

        # Excluded extensions
        if suffix in EXCLUDED_EXTENSIONS:
            continue

        # Supported extensions filtresi
        if ext_set and suffix not in ext_set:
            continue

        # Binary dosya kontrolü (ilk 1024 byte'a bak)
        if _is_binary(file_path):
            continue

        code_files.append(str(file_path))

    logger.info(f"{len(code_files)} kod dosyası bulundu: {repo_path}")
    return sorted(code_files)


def extract_repo_name_from_url(repo_url: str) -> str:
    """URL'den repo adını çıkarır."""
    # https://github.com/user/repo veya https://github.com/user/repo.git
    url = repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url.split("/")[-1]


# --- Private helpers ---

def _detect_primary_language(repo_path: Path) -> str:
    """Repo'daki en yaygın kaynak kod dilini tespit eder."""
    counts = {}
    lang_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "JavaScript",
        ".tsx": "TypeScript",
        ".go": "Go",
        ".rs": "Rust",
        ".java": "Java",
        ".cpp": "C++",
        ".c": "C",
        ".rb": "Ruby",
        ".php": "PHP",
    }
    for fp in repo_path.rglob("*"):
        if ".git" in fp.parts or not fp.is_file():
            continue
        lang = lang_map.get(fp.suffix.lower())
        if lang:
            counts[lang] = counts.get(lang, 0) + 1

    if not counts:
        return "Unknown"
    return max(counts, key=counts.get)


def _is_binary(file_path: Path) -> bool:
    """Dosyanın binary olup olmadığını kontrol eder."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
        # NULL byte varsa binary say
        return b"\x00" in chunk
    except Exception:
        return True
