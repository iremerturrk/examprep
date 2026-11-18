"""Arayüz çevirileri: her metin üç dilde, sayfalarda kullanılan her anahtar tanımlı."""

import re
from pathlib import Path

import pytest

from examprep.i18n import LANGS, S, label, t
from examprep.models import (
    Angle,
    ArchetypeOrigin,
    BloomLevel,
    CardKind,
    DocStatus,
    DocType,
    PerceivedDifficulty,
    Tier,
)

ROOT = Path(__file__).resolve().parent.parent
UI_FILES = [ROOT / "app.py", *sorted((ROOT / "pages").glob("*.py"))]


def test_every_string_has_all_languages():
    missing = [(k, lang) for k, v in S.items() for lang in LANGS if not v.get(lang)]
    assert missing == []


def test_placeholders_match_across_languages():
    ph = re.compile(r"\{(\w+)\}")
    bad = [k for k, v in S.items() if len({frozenset(ph.findall(x)) for x in v.values()}) != 1]
    assert bad == []


@pytest.mark.parametrize("enum", [BloomLevel, Angle, ArchetypeOrigin, DocType, DocStatus, Tier, CardKind,
                                  PerceivedDifficulty])
def test_every_enum_value_has_label(enum):
    for member in enum:
        for lang in LANGS:
            assert label(member, lang=lang)


def test_keys_used_in_ui_exist():
    used = set()
    for f in UI_FILES:
        src = f.read_text(encoding="utf-8")
        used |= set(re.findall(r"""\bt\(\s*["']([\w.]+)["']""", src))
        # f-string anahtarları: t(f"tiernote.{...}") → önek kontrolü
        for prefix in re.findall(r"""\bt\(\s*f["']([\w.]+)\{""", src):
            assert any(k.startswith(prefix) for k in S), prefix
    assert used, "hiç anahtar bulunamadı"
    assert sorted(k for k in used if k not in S) == []


def test_no_hardcoded_turkish_ui_strings_left():
    # docstring/yorum dışında Türkçe karakter içeren string literal kalmamalı
    offenders = []
    for f in UI_FILES:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if '"""' in code:
                continue
            if re.search(r"""["'][^"']*[çğıöşüÇĞİÖŞÜ][^"']*["']""", code):
                offenders.append(f"{f.name}:{n}: {line.strip()}")
    assert offenders == []


def test_t_formats_and_falls_back():
    assert t("courses.created", lang="de", name="Info 3", id=1) == "'Info 3' angelegt (ID: 1)."
    assert t("tests.n_questions", lang="en", n=35) == "35 questions"
    assert t("nav.tests", lang="xx") == S["nav.tests"]["tr"]
    assert label(BloomLevel.apply, lang="de") == "Anwenden"
