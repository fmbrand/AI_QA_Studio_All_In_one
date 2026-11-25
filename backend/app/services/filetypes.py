"""Server-side file type detection. The client's filename extension and Content-Type are not trusted
on their own: the bytes must match the declared type."""

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import AppError


@dataclass(frozen=True)
class FileType:
    extension: str
    content_type: str
    family: str  # text | csv | json | pdf | office | image


TYPES: dict[str, FileType] = {
    ".pdf": FileType(".pdf", "application/pdf", "pdf"),
    ".docx": FileType(".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "office"),
    ".xlsx": FileType(".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "office"),
    ".csv": FileType(".csv", "text/csv", "csv"),
    ".txt": FileType(".txt", "text/plain", "text"),
    ".md": FileType(".md", "text/markdown", "text"),
    ".json": FileType(".json", "application/json", "json"),
    ".png": FileType(".png", "image/png", "image"),
    ".jpg": FileType(".jpg", "image/jpeg", "image"),
    ".jpeg": FileType(".jpeg", "image/jpeg", "image"),
    ".webp": FileType(".webp", "image/webp", "image"),
}

TEXT_FAMILIES = {"text", "csv", "json"}


def _unsupported(detail: str) -> AppError:
    return AppError(415, "unsupported_file_type", detail, extra={"allowed_extensions": sorted(TYPES)})


def _is_utf8_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        # A multi-byte character may be cut at the end of the sample.
        return exc.start >= len(head) - 3
    return True


def detect(filename: str, path: Path) -> FileType:
    """Return the file type, or raise 415 when the extension is not allowed or the content disagrees."""
    ext = Path(filename).suffix.lower()
    ftype = TYPES.get(ext)
    if ftype is None:
        raise _unsupported(f"Files of type “{ext or 'unknown'}” are not supported")
    with path.open("rb") as fh:
        head = fh.read(8192)
    mismatch = _unsupported(f"The file content does not match its “{ext}” extension")
    if ftype.family == "pdf" and not head.startswith(b"%PDF-"):
        raise mismatch
    if ftype.extension == ".png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        raise mismatch
    if ftype.content_type == "image/jpeg" and not head.startswith(b"\xff\xd8\xff"):
        raise mismatch
    if ftype.extension == ".webp" and not (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
        raise mismatch
    if ftype.family == "office":
        if not head.startswith(b"PK\x03\x04") or not zipfile.is_zipfile(path):
            raise mismatch
        prefix = "word/" if ext == ".docx" else "xl/"
        with zipfile.ZipFile(path) as zf:
            if not any(n.startswith(prefix) for n in zf.namelist()):
                raise mismatch
    if ftype.family in TEXT_FAMILIES:
        if not _is_utf8_text(head):
            raise _unsupported("Text files must be UTF-8 encoded")
        if ftype.family == "json":
            try:
                json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise AppError(422, "invalid_json", "The JSON file could not be parsed") from exc
    return ftype


def safe_filename(name: str) -> str:
    """Keep only the final path component and strip control characters."""
    base = Path(name.replace("\\", "/")).name
    cleaned = "".join(ch for ch in base if ch.isprintable() and ch not in '<>:"|?*').strip(" .")
    return cleaned[:255] or "upload"
