from __future__ import annotations

import io

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

ALLOWED_MIMES = frozenset({"image/jpeg", "image/png", "image/webp", "image/heic"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_image_upload(file: UploadFile, data: bytes) -> None:
    """Validate an image upload's MIME, size, and (for non-HEIC) magic bytes.

    Raises ``HTTPException`` with appropriate 4xx status on failure.

    Parameters
    ----------
    file : UploadFile
        The uploaded file (used for ``content_type``).
    data : bytes
        The already-read body, so the caller can reuse it.
    """
    if file.content_type not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_image_format",
        )
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="image_too_large",
        )
    # Pillow doesn't natively decode HEIC; accept-by-MIME for HEIC only.
    if file.content_type == "image/heic":
        return
    try:
        Image.open(io.BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="invalid_image_data",
        ) from None
