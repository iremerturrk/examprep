"""Streamlit sayfalarının ortak yardımcıları: Türkçe etiketler ve eksen metni biçimi."""

from examprep.analysis import AnalysisError
from examprep.models import Angle, ArchetypeOrigin, BloomLevel, DocType

BLOOM_TR = {
    BloomLevel.remember: "Hatırlama",
    BloomLevel.understand: "Anlama",
    BloomLevel.apply: "Uygulama",
    BloomLevel.analyze: "Analiz",
    BloomLevel.evaluate: "Değerlendirme",
    BloomLevel.create: "Yaratma",
}
ANGLE_TR = {
    Angle.compute: "Hesaplama",
    Angle.trace: "İzleme",
    Angle.compare: "Karşılaştırma",
    Angle.find_error: "Hata bulma",
    Angle.edge_case: "Kenar durum",
    Angle.explain: "Açıklama",
    Angle.design: "Tasarım",
}
ORIGIN_TR = {
    ArchetypeOrigin.exam: "Sınav",
    ArchetypeOrigin.homework: "Ödev",
    ArchetypeOrigin.web: "Web",
    ArchetypeOrigin.model: "Model",
}
DOC_TR = {DocType.slides: "Slayt", DocType.homework: "Ödev", DocType.exam: "Sınav"}

AXIS_SEP = "|"


def axes_to_text(axes: dict[str, list[str]]) -> str:
    """{"algoritma": ["merge", "quick"]} -> "algoritma: merge | quick" (her eksen bir satır)."""
    return "\n".join(f"{name}: {f' {AXIS_SEP} '.join(values)}" for name, values in axes.items())


def text_to_axes(text: str) -> dict[str, list[str]]:
    axes: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        name, sep, values = line.partition(":")
        if not sep:
            raise AnalysisError(f"Satır 'eksen: değer {AXIS_SEP} değer' biçiminde olmalı: {line}")
        axes[name.strip()] = [v.strip() for v in values.split(AXIS_SEP)]
    return axes
