"""PDF'den sayfa metni ve görüntüsü çıkarma. Veritabanından bağımsız."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf

RENDER_DPI = 150
# Bu sayıdan az metin içeren ve görüntü barındıran sayfa taranmış kabul edilir.
SCANNED_TEXT_THRESHOLD = 30


class IngestError(Exception):
    pass


@dataclass(frozen=True)
class PageData:
    page_no: int  # 1'den başlar
    text: str
    image_file: Path
    is_scanned: bool

    @property
    def char_count(self) -> int:
        return len(self.text)


def extract_pages(pdf_bytes: bytes, out_dir: Path, dpi: int = RENDER_DPI) -> list[PageData]:
    """Her sayfanın metnini çıkarır ve PNG olarak out_dir altına kaydeder."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # PyMuPDF farklı hata türleri fırlatabiliyor
        raise IngestError(f"PDF açılamadı: {exc}") from exc

    with doc:
        if doc.needs_pass:
            raise IngestError("PDF şifreli, şifresiz bir kopya yükleyin.")
        if doc.page_count == 0:
            raise IngestError("PDF'de sayfa yok.")

        out_dir.mkdir(parents=True, exist_ok=True)
        pages: list[PageData] = []
        for index, page in enumerate(doc):
            page_no = index + 1
            text = page.get_text("text").strip()
            image_file = out_dir / f"page_{page_no:03}.png"
            page.get_pixmap(dpi=dpi).save(image_file)
            is_scanned = len(text) < SCANNED_TEXT_THRESHOLD and bool(page.get_images())
            pages.append(PageData(page_no, text, image_file, is_scanned))
        return pages
