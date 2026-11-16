import pytest
from pydantic import ValidationError

from examprep.analysis import AnalysisError
from examprep.models import Angle, ArchetypeOrigin, BloomLevel, DocType
from examprep.schemas import ArchetypeEdit
from examprep.ui import ANGLE_TR, BLOOM_TR, DOC_TR, ORIGIN_TR, axes_to_text, text_to_axes


def test_axes_roundtrip():
    axes = {"algoritma": ["merge sort", "quicksort"], "girdi": ["sıralı", "ters, tekrarlı"]}
    assert text_to_axes(axes_to_text(axes)) == axes


def test_text_to_axes_ignores_blank_lines_and_trims():
    assert text_to_axes("\n  a :  x |y \n\n") == {"a": ["x", "y"]}


def test_text_to_axes_requires_colon():
    with pytest.raises(AnalysisError, match="biçiminde"):
        text_to_axes("algoritma merge | quick")


def test_single_value_axis_rejected_by_schema():
    with pytest.raises(ValidationError, match="en az 2"):
        ArchetypeEdit(skill="x", angle="trace", variation_axes=text_to_axes("a: tek"))


@pytest.mark.parametrize(
    ("labels", "enum"),
    [(BLOOM_TR, BloomLevel), (ANGLE_TR, Angle), (ORIGIN_TR, ArchetypeOrigin), (DOC_TR, DocType)],
)
def test_every_enum_value_has_label(labels, enum):
    assert set(labels) == set(enum)
