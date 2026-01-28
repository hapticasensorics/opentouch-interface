from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable, Optional


DEFAULT_CACHE_DIR = Path(os.getenv("OPENTOUCH_RERUN_CACHE_DIR", "./cache")).resolve()
_HASH_CHUNK_SIZE = 1024 * 1024


def touch_hash(touch_path: Path) -> str:
    """Compute a stable hash of a .touch file's contents."""
    digest = hashlib.sha256()
    with touch_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_rrd_path_for_hash(
    touch_path: Path, hash_value: str, cache_dir: Path
) -> Path:
    safe_stem = touch_path.stem.replace(" ", "_")
    filename = f"{safe_stem}-{hash_value[:12]}.rrd"
    return cache_dir / filename


def cache_rrd_path(touch_path: Path, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    """Return the cache path for a .touch file's converted .rrd."""
    return _cache_rrd_path_for_hash(touch_path, touch_hash(touch_path), cache_dir)


def get_cached_rrd(touch_path: Path, cache_dir: Path = DEFAULT_CACHE_DIR) -> Optional[Path]:
    """Return the cached .rrd path if it exists."""
    cached_path = cache_rrd_path(touch_path, cache_dir=cache_dir)
    if cached_path.exists() and cached_path.stat().st_size > 0:
        return cached_path
    return None


def get_or_create_rrd(
    touch_path: Path,
    converter: Callable[[Path, Path], None],
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Return a cached .rrd, converting if needed."""
    hash_value = touch_hash(touch_path)
    cached_path = _cache_rrd_path_for_hash(touch_path, hash_value, cache_dir)
    if cached_path.exists() and cached_path.stat().st_size > 0:
        return cached_path

    cache_dir.mkdir(parents=True, exist_ok=True)

    converter(touch_path, cached_path)

    if not cached_path.exists() or cached_path.stat().st_size == 0:
        raise RuntimeError(f"Conversion failed to produce {cached_path}")

    return cached_path
