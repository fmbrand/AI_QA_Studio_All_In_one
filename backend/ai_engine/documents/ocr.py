"""Optional Tesseract OCR. When Tesseract is not installed, callers get None and record a warning."""

import shutil
from functools import lru_cache
from pathlib import Path

from PIL import Image

_WINDOWS_PATHS = (
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
)


@lru_cache
def find_tesseract(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit if Path(explicit).exists() or shutil.which(explicit) else None
    found = shutil.which("tesseract")
    if found:
        return found
    return next((str(p) for p in _WINDOWS_PATHS if p.exists()), None)


class OCR:
    def __init__(self, tesseract_cmd: str | None, languages: str = "eng") -> None:
        self.cmd = find_tesseract(tesseract_cmd)
        self.languages = languages

    @property
    def available(self) -> bool:
        return self.cmd is not None

    def read(self, image: Image.Image) -> str | None:
        """Return the recognised text, or None when OCR is unavailable."""
        if self.cmd is None:
            return None
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = self.cmd
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        return pytesseract.image_to_string(image, lang=self.languages)
