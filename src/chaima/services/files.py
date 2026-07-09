from __future__ import annotations

import os
import uuid as uuid_pkg
from pathlib import Path

UPLOADS_ROOT = Path(os.environ.get("CHAIMA_UPLOADS_DIR", "uploads"))

# Extensions safe to serve verbatim from the unauthenticated /uploads mount.
# Anything else (e.g. .html, .svg, .js smuggled in the client filename) is
# stored as .bin so browsers never execute it as active content. Callers
# validate content-type before saving; this only constrains the stored name.
_SAFE_EXTENSIONS = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif"}
)


def save_upload(group_id: uuid_pkg.UUID, original_name: str, data: bytes) -> str:
    """Save ``data`` under ``uploads/<group_id>/<uuid><ext>`` and return the
    relative path string (posix-style, without leading slash).

    ``original_name`` is attacker-controlled; its extension is only kept when
    it is in the passive-content allowlist, otherwise ``.bin`` is used.
    """
    ext = Path(original_name).suffix.lower()
    if ext not in _SAFE_EXTENSIONS:
        ext = ".bin"
    new_name = f"{uuid_pkg.uuid4().hex}{ext}"
    group_dir = UPLOADS_ROOT / str(group_id)
    group_dir.mkdir(parents=True, exist_ok=True)
    (group_dir / new_name).write_bytes(data)
    return (Path(str(group_id)) / new_name).as_posix()
