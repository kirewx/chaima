from __future__ import annotations

import os
import uuid as uuid_pkg
from pathlib import Path

UPLOADS_ROOT = Path(os.environ.get("CHAIMA_UPLOADS_DIR", "uploads"))


def save_upload(group_id: uuid_pkg.UUID, original_name: str, data: bytes) -> str:
    """Save ``data`` under ``uploads/<group_id>/<uuid><ext>`` and return the
    relative path string (posix-style, without leading slash)."""
    ext = Path(original_name).suffix
    new_name = f"{uuid_pkg.uuid4().hex}{ext}"
    group_dir = UPLOADS_ROOT / str(group_id)
    group_dir.mkdir(parents=True, exist_ok=True)
    (group_dir / new_name).write_bytes(data)
    return (Path(str(group_id)) / new_name).as_posix()
