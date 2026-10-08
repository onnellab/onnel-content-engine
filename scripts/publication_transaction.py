"""Recoverable local transactions for article files and their two CSV indexes.

The repository commit remains the public deployment boundary. A durable undo
journal prevents an interrupted local preparation from poisoning a retry.
"""
from contextlib import contextmanager
from functools import wraps
import csv
import inspect
import io
import json
import os
from pathlib import Path
import shutil
import tempfile

from short_video_portability import exclusive_file_lock, sync_directory


def _write_staged(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".publication-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return Path(name)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _restore(root, journal):
    manifest = journal / "manifest.json"
    if manifest.is_symlink():
        raise ValueError("linked publication recovery manifest rejected")
    if not manifest.exists():
        # No destination can have changed before the manifest was durable.
        shutil.rmtree(journal)
        return
    state = json.loads(manifest.read_text())
    if not (journal / "committed").exists():
        for index, item in enumerate(state):
            if item["backup"] != f"{index}.before" or Path(item["path"]).is_absolute() or ".." in Path(item["path"]).parts:
                raise ValueError("unsafe publication recovery journal")
            path = root / item["path"]
            if not path.resolve().is_relative_to(root) or path.is_symlink():
                raise ValueError("unsafe publication recovery path")
            if item["existed"]:
                backup = journal / item["backup"]
                if backup.is_symlink() or not backup.is_file():
                    raise ValueError("invalid publication recovery backup")
                staged = _write_staged(path, backup.read_bytes())
                os.replace(staged, path)
                sync_directory(path.parent)
            else:
                path.unlink(missing_ok=True)
                sync_directory(path.parent)
    shutil.rmtree(journal)
    sync_directory(journal.parent)


@contextmanager
def publication_guard(root):
    root = Path(root).resolve()
    data = root / "data"
    if data.is_symlink():
        raise ValueError("linked publication data directory rejected")
    data.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(data / ".publication.lock"):
        journal = data / ".publication-transaction"
        if journal.exists():
            if journal.is_symlink():
                raise ValueError("linked publication journal rejected")
            _restore(root, journal)
        yield


def guarded_publication(function):
    signature = inspect.signature(function)
    @wraps(function)
    def guarded(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        with publication_guard(bound.arguments["topics_path"].parent.parent):
            return function(*args, **kwargs)
    return guarded


def topic_csv_bytes(store, rows):
    from topic_management import TOPIC_HEADER, load_app_names, validate_rows
    validate_rows(rows, load_app_names(store.apps_path))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TOPIC_HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def atomic_replace_files(root, updates):
    """Called while publication_guard is held; stage before changing any target."""
    root = Path(root).resolve()
    normalized = {}
    for path, content in updates.items():
        path = Path(path).absolute()
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("publication destination must stay within the repository")
        # macOS exposes temporary roots through /var -> /private/var. Use the
        # same canonical root for manifest paths and destination replacements.
        path = path.resolve()
        if path in normalized:
            raise ValueError("duplicate canonical publication destination")
        normalized[path] = content
    journal = root / "data/.publication-transaction"
    journal.mkdir()
    staged = {}
    try:
        state = []
        for index, (path, content) in enumerate(normalized.items()):
            existed = path.exists()
            backup = f"{index}.before"
            if existed:
                saved = _write_staged(journal / backup, path.read_bytes())
                os.replace(saved, journal / backup)
            state.append({"path": str(path.relative_to(root)), "existed": existed, "backup": backup})
            staged[path] = _write_staged(path, content)
        manifest = _write_staged(journal / "manifest.json", json.dumps(state).encode())
        os.replace(manifest, journal / "manifest.json")
        sync_directory(journal)
        sync_directory(journal.parent)
        for path, temporary in staged.items():
            os.replace(temporary, path)
            sync_directory(path.parent)
        marker = _write_staged(journal / "committed", b"complete\n")
        os.replace(marker, journal / "committed")
        sync_directory(journal)
    except BaseException:
        _restore(root, journal)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
    _restore(root, journal)
