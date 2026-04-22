import pytest

from chaima.services import import_ as import_service


@pytest.mark.parametrize("input_str,expected", [
    ("250 mL", (250.0, "mL")),
    ("1,5 L", (1.5, "L")),
    ("1.5 L", (1.5, "L")),
    ("5", (5.0, None)),
    ("0.1 µmol", (0.1, "µmol")),
    ("100g", (100.0, "g")),
    ("", (None, None)),
    ("some text", (None, None)),
    ("abc 5 def", (None, None)),
])
def test_split_quantity_unit(input_str, expected):
    assert import_service.split_quantity_unit(input_str) == expected
