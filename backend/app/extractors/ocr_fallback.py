from __future__ import annotations

from io import BytesIO

from PIL import Image

try:
    import pytesseract
except Exception:  # pragma: no cover - optional at runtime
    pytesseract = None


class OcrFallback:
    def __init__(self, min_chars: int = 120) -> None:
        self._min_chars = min_chars

    @property
    def enabled(self) -> bool:
        return pytesseract is not None

    def should_run(self, text: str) -> bool:
        return len((text or "").strip()) < self._min_chars

    def extract_from_png_bytes(self, image_bytes: bytes) -> str:
        if not self.enabled:
            return ""

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                return (pytesseract.image_to_string(image) or "").strip()
        except Exception:
            return ""
