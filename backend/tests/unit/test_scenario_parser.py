"""F6 — senaryo (çok-adımlı) parser birim testleri."""
import pytest

from app.services.test_suite.parser import ParseError, parse_yaml

_AGENT = "11111111-1111-1111-1111-111111111111"


def _suite(cases_yaml: str) -> str:
    return f'name: s\nagent_id: "{_AGENT}"\ncases:\n{cases_yaml}'


def test_scenario_case_parses_steps():
    suite = parse_yaml(_suite(
        "  - name: booking\n"
        "    steps:\n"
        "      - input: \"Paris uçuşu bul\"\n"
        "        assertions:\n"
        "          - type: response_contains\n"
        "            value: \"Paris\"\n"
        "      - input: \"En ucuzunu seç\"\n"
        "        assertions:\n"
        "          - type: response_not_contains\n"
        "            value: \"hata\"\n"
    ))
    case = suite.cases[0]
    assert case.steps is not None
    assert len(case.steps) == 2
    assert case.input == "Paris uçuşu bul"  # temsilci = ilk adım
    assert case.steps[0].assertions[0].type == "response_contains"
    assert case.steps[1].input == "En ucuzunu seç"


def test_single_case_has_no_steps():
    suite = parse_yaml(_suite(
        "  - name: tekil\n"
        "    input: \"merhaba\"\n"
        "    assertions:\n"
        "      - type: response_contains\n"
        "        value: \"x\"\n"
    ))
    assert suite.cases[0].steps is None


def test_step_missing_input_raises():
    with pytest.raises(ParseError):
        parse_yaml(_suite(
            "  - name: bad\n"
            "    steps:\n"
            "      - assertions:\n"
            "          - type: response_contains\n"
            "            value: \"x\"\n"
        ))


def test_step_invalid_assertion_type_raises():
    with pytest.raises(ParseError):
        parse_yaml(_suite(
            "  - name: bad\n"
            "    steps:\n"
            "      - input: \"x\"\n"
            "        assertions:\n"
            "          - type: made_up\n"
            "            value: 1\n"
        ))


def test_empty_steps_list_raises():
    with pytest.raises(ParseError):
        parse_yaml(_suite("  - name: bad\n    steps: []\n"))


def test_step_to_dict_roundtrip():
    suite = parse_yaml(_suite(
        "  - name: s1\n"
        "    steps:\n"
        "      - input: \"hi\"\n"
        "        assertions:\n"
        "          - type: response_contains\n"
        "            value: \"y\"\n"
    ))
    d = suite.cases[0].steps[0].to_dict()
    assert d == {"input": "hi", "assertions": [{"type": "response_contains", "value": "y"}]}
