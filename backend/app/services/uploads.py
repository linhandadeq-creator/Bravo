"""Safe upload helpers with hard size limits.

Streamed uploads (tumour/normal VCFs, project files) are written straight to
disk and may be large — bounded by ``MAX_UPLOAD_BYTES`` (default 3 GiB, sized
for whole-genome tumour/normal VCFs). Text uploads read fully into memory (HLA
typing, expression tables) are bounded by the smaller
``MAX_TEXT_UPLOAD_BYTES`` (default 64 MiB) so a large text file cannot exhaust
memory. Reads are aborted as soon as the limit is exceeded.
"""
from __future__ import annotations

from app.core.config import settings

CHUNK = 1 << 20  # 1 MiB


class UploadTooLargeError(RuntimeError):
    """Raised when an uploaded file exceeds the configured maximum size."""


def limit_bytes() -> int:
    """Streamed-upload limit (VCFs / project files written to disk)."""
    return int(getattr(settings, "MAX_UPLOAD_BYTES", 0) or 0)


def text_limit_bytes() -> int:
    """In-memory-upload limit (HLA / expression text)."""
    return int(getattr(settings, "MAX_TEXT_UPLOAD_BYTES", 0) or 0)


def read_bytes_limited(fileobj) -> bytes:
    """Read an upload into memory, aborting as soon as the limit is exceeded."""
    limit = text_limit_bytes()
    buffer = bytearray()
    while True:
        chunk = fileobj.read(CHUNK)
        if not chunk:
            break
        buffer.extend(chunk)
        if limit and len(buffer) > limit:
            raise UploadTooLargeError(
                f"Uploaded file exceeds the maximum size of {limit} bytes."
            )
    return bytes(buffer)


def read_text_limited(fileobj) -> str:
    return read_bytes_limited(fileobj).decode("utf-8", "replace")


def copy_limited(fileobj, destination) -> int:
    """Stream an upload to ``destination`` path, enforcing the size limit."""
    limit = limit_bytes()
    total = 0
    with open(destination, "wb") as handle:
        while True:
            chunk = fileobj.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if limit and total > limit:
                handle.close()
                try:
                    destination.unlink()
                except OSError:
                    pass
                raise UploadTooLargeError(
                    f"Uploaded file exceeds the maximum size of {limit} bytes."
                )
            handle.write(chunk)
    return total
