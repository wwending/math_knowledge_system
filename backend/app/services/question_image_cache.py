"""Private, disposable generated-image cache; callers must authorize every access."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from app.services.draft_image_service import normalize_draft_bbox

# Fixed stripes bound lock memory/files; encoding never holds the storage lock.
# OS locks cover independent workers sharing the same local uploads volume.
STRIPES = 16
_locks = [threading.Lock() for _ in range(STRIPES + 1)]
MAX_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 512
LOCK_TIMEOUT = 15
SPEC = "question-region-png-v1-original-size-RGB-L"


@contextmanager
def _exclusive(root: Path, stripe: int = STRIPES):
    deadline = time.monotonic() + LOCK_TIMEOUT
    lock = _locks[stripe]
    if not lock.acquire(timeout=LOCK_TIMEOUT):
        raise TimeoutError("image cache busy")
    try:
        root.mkdir(parents=True, exist_ok=True)
        with (root / f"cache-{stripe}.lock").open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            acquired = False
            try:
                while not acquired:
                    try:
                        handle.seek(0)
                        if os.name == "nt":
                            import msvcrt
                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("image cache busy")
                        time.sleep(0.05)
                yield
            finally:
                if acquired:
                    handle.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        lock.release()


def _digest(source: Path) -> str:
    with source.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _entries(root: Path):
    # Only our hash-named artifacts, never original uploads or arbitrary files.
    return [p for p in root.glob("*.qic") if len(p.stem) == 64 and all(c in "0123456789abcdef" for c in p.stem)]


def _trim(root: Path, max_bytes: int, max_entries: int, reserve: int = 0):
    entries = sorted(_entries(root), key=lambda p: p.stat().st_mtime_ns)
    total = sum(p.stat().st_size for p in entries)
    while entries and (total + reserve > max_bytes or len(entries) + bool(reserve) > max_entries):
        victim = entries.pop(0)
        total -= victim.stat().st_size
        victim.unlink(missing_ok=True)


def _read(target: Path):
    if not target.exists():
        return None
    data = target.read_bytes()
    content = data[65:]
    if len(data) > 65 and data[64:65] == b"\n" and data[:64] == hashlib.sha256(content).hexdigest().encode():
        os.utime(target, None)
        return content, "image/png"
    target.unlink(missing_ok=True)
    return None


def cached_question_image(source_path, crop_bbox, *, root, render, max_bytes=MAX_BYTES, max_entries=MAX_ENTRIES, spec=SPEC):
    source = Path(source_path).resolve()
    root = Path(root).resolve()
    if source == root or root in source.parents:
        raise ValueError("cache may not be an image source")
    bbox = normalize_draft_bbox(crop_bbox)
    # Hash exact bytes, even after a same-size source replacement. Hashing and
    # rendering stay outside the shared storage lock so hits can proceed.
    source_hash = _digest(source)
    key = hashlib.sha256(json.dumps([str(source), source_hash, bbox, spec], sort_keys=True).encode()).hexdigest()
    target = root / f"{key}.qic"
    with _exclusive(root):
        _trim(root, max_bytes, max_entries)
        hit = _read(target)
        if hit is not None:
            return hit
    with _exclusive(root, int(key[:8], 16) % STRIPES):
        with _exclusive(root):
            hit = _read(target)
            if hit is not None:
                return hit
        content, media_type = render(source, crop_bbox)
        if _digest(source) != source_hash:
            raise ValueError("image source changed during rendering; retry")
        data = hashlib.sha256(content).hexdigest().encode() + b"\n" + content
        with _exclusive(root):
            # Atomic writers use this same storage lock; any tmp here was left
            # by a crashed writer, and is disposable, never an original upload.
            for temporary in root.glob("*.tmp"):
                if len(temporary.stem) == 64 and all(c in "0123456789abcdef" for c in temporary.stem):
                    temporary.unlink(missing_ok=True)
            if len(data) <= max_bytes and max_entries > 0:
                _trim(root, max_bytes, max_entries, len(data))
                temporary = root / f"{key}.tmp"
                try:
                    temporary.write_bytes(data)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
        # Hits are read under the storage lock; eviction cannot race streaming.
        return content, media_type
