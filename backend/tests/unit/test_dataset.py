"""B2 (#5) — dataset parser + suite YAML üretimi."""
import pytest
import yaml

from app.services.test_suite.dataset import DatasetError, build_suite_yaml, parse_dataset


def test_parse_csv():
    content = "input,expected\nMerhaba,selam\n2+2,4\n"
    rows = parse_dataset(content, "csv")
    assert len(rows) == 2
    assert rows[0] == {"input": "Merhaba", "expected": "selam"}
    assert rows[1]["expected"] == "4"


def test_parse_jsonl():
    content = '{"input": "soru1", "expected": "cevap1"}\n{"input": "soru2"}\n'
    rows = parse_dataset(content, "jsonl")
    assert len(rows) == 2
    assert rows[1]["expected"] == ""  # expected opsiyonel


def test_csv_requires_input_column():
    with pytest.raises(DatasetError):
        parse_dataset("foo,bar\n1,2\n", "csv")


def test_jsonl_requires_input():
    with pytest.raises(DatasetError):
        parse_dataset('{"expected": "x"}\n', "jsonl")


def test_empty_rejected():
    with pytest.raises(DatasetError):
        parse_dataset("input,expected\n", "csv")


def test_bad_format():
    with pytest.raises(DatasetError):
        parse_dataset("x", "xml")


def test_build_yaml_with_assertions():
    rows = [{"input": "a", "expected": "b"}, {"input": "c", "expected": ""}]
    y = build_suite_yaml("ds-suite", "11111111-1111-1111-1111-111111111111", rows, "contains")
    parsed = yaml.safe_load(y)
    assert parsed["name"] == "ds-suite"
    assert len(parsed["cases"]) == 2
    # 1. satır expected'lı → assertion var
    assert parsed["cases"][0]["assertions"][0]["type"] == "response_contains"
    assert parsed["cases"][0]["assertions"][0]["value"] == "b"
    # 2. satır expected boş → assertion yok
    assert "assertions" not in parsed["cases"][1]


def test_build_yaml_assertion_mapping():
    rows = [{"input": "a", "expected": "b"}]
    y = build_suite_yaml("s", "11111111-1111-1111-1111-111111111111", rows, "regex")
    assert yaml.safe_load(y)["cases"][0]["assertions"][0]["type"] == "response_regex"


def test_build_yaml_is_valid_for_parser():
    """Üretilen YAML mevcut parse_yaml ile uyumlu olmalı."""
    from app.services.test_suite.parser import parse_yaml
    rows = [{"input": "Türkçe soru şçöğü", "expected": "yanıt"}]
    y = build_suite_yaml("s", "11111111-1111-1111-1111-111111111111", rows, "contains")
    suite = parse_yaml(y)
    assert len(suite.cases) == 1
    assert suite.cases[0].input == "Türkçe soru şçöğü"
