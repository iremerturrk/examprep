"""Streamlit sayfalarının ortak yardımcıları: varyasyon ekseni metin biçimi. Etiketler: examprep.i18n."""

from examprep.analysis import AnalysisError
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
