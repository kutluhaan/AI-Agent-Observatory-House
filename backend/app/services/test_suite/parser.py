"""
YAML Test Suite Parser — M11

YAML formatı:

  name: echo-suite                   # zorunlu
  description: "..."                 # opsiyonel
  agent_id: "uuid"                   # varsayılan agent (case düzeyinde geçersiz kılınabilir)
  cases:
    - name: basic-echo               # zorunlu
      input: "Merhaba"               # zorunlu
      agent_id: "other-uuid"         # opsiyonel — suite-level'ı geçersiz kılar
      expected_output: "merhaba"     # opsiyonel — response_contains için shorthand
      rag_context:                   # opsiyonel — RAG eval için altın context
        - "chunk 1"
        - "chunk 2"
      assertions:
        - type: response_contains
          value: "merhaba"
        - type: tool_called
          value: "echo"
        - type: latency_under
          value: 5000
        - type: finish_reason_is
          value: "stop"
        - type: steps_under
          value: 3

Desteklenen assertion tipleri:
  response_contains   — çıktı bu metni içeriyor mu (case-insensitive)
  tool_called         — verilen tool en az bir kez çağrıldı mı
  latency_under       — ms cinsinden süre
  finish_reason_is    — "stop" | "tool_calls" | ...
  steps_under         — kaç adımda tamamlandı
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import yaml


SUPPORTED_ASSERTION_TYPES = {
    "response_contains",
    "tool_called",
    "latency_under",
    "finish_reason_is",
    "steps_under",
}


@dataclass
class ParsedAssertion:
    type: str
    value: str | int | float


@dataclass
class ParsedTestCase:
    name: str
    input: str
    assertions: list[ParsedAssertion]
    agent_id: uuid.UUID | None = None
    expected_output: str | None = None
    rag_context: list[str] | None = None


@dataclass
class ParsedTestSuite:
    name: str
    cases: list[ParsedTestCase]
    description: str | None = None
    agent_id: uuid.UUID | None = None  # suite-level default


class ParseError(Exception):
    """YAML yapısı veya içerik geçersiz."""


def parse_yaml(raw_yaml: str) -> ParsedTestSuite:
    """
    YAML string'ini ParsedTestSuite'e dönüştürür.

    Raises:
        ParseError: Zorunlu alan eksik, tip hatalı veya assertion tipi bilinmiyor.
    """
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise ParseError(f"YAML parse hatası: {exc}") from exc

    if not isinstance(data, dict):
        raise ParseError("YAML root bir mapping (dict) olmalı.")

    name = _require_str(data, "name")
    description = data.get("description")
    if description is not None and not isinstance(description, str):
        raise ParseError("'description' string olmalı.")

    suite_agent_id = _parse_agent_id(data.get("agent_id"), context="suite")

    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) == 0:
        raise ParseError("'cases' en az bir element içeren bir liste olmalı.")

    cases: list[ParsedTestCase] = []
    for i, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, dict):
            raise ParseError(f"cases[{i}]: dict olmalı.")
        cases.append(_parse_case(raw_case, i, suite_agent_id))

    return ParsedTestSuite(
        name=name,
        description=description,
        agent_id=suite_agent_id,
        cases=cases,
    )


def _parse_case(
    raw: dict,
    index: int,
    suite_agent_id: uuid.UUID | None,
) -> ParsedTestCase:
    ctx = f"cases[{index}]"
    name = _require_str(raw, "name", ctx)
    input_text = _require_str(raw, "input", ctx)

    agent_id = _parse_agent_id(raw.get("agent_id"), context=f"{ctx}.agent_id")
    if agent_id is None:
        agent_id = suite_agent_id

    expected_output = raw.get("expected_output")
    if expected_output is not None and not isinstance(expected_output, str):
        raise ParseError(f"{ctx}.expected_output: string olmalı.")

    rag_context = raw.get("rag_context")
    if rag_context is not None:
        if not isinstance(rag_context, list) or not all(isinstance(c, str) for c in rag_context):
            raise ParseError(f"{ctx}.rag_context: string listesi olmalı.")

    raw_assertions = raw.get("assertions", [])
    if not isinstance(raw_assertions, list):
        raise ParseError(f"{ctx}.assertions: liste olmalı.")

    assertions: list[ParsedAssertion] = []

    # expected_output shorthand → response_contains
    if expected_output:
        assertions.append(ParsedAssertion(type="response_contains", value=expected_output))

    for j, raw_a in enumerate(raw_assertions):
        actx = f"{ctx}.assertions[{j}]"
        if not isinstance(raw_a, dict):
            raise ParseError(f"{actx}: dict olmalı.")
        a_type = _require_str(raw_a, "type", actx)
        if a_type not in SUPPORTED_ASSERTION_TYPES:
            raise ParseError(
                f"{actx}.type '{a_type}' desteklenmiyor. "
                f"Geçerli tipler: {sorted(SUPPORTED_ASSERTION_TYPES)}"
            )
        if "value" not in raw_a:
            raise ParseError(f"{actx}: 'value' zorunlu.")
        assertions.append(ParsedAssertion(type=a_type, value=raw_a["value"]))

    return ParsedTestCase(
        name=name,
        input=input_text,
        agent_id=agent_id,
        expected_output=expected_output,
        rag_context=rag_context,
        assertions=assertions,
    )


def _require_str(data: dict, key: str, ctx: str = "root") -> str:
    val = data.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ParseError(f"{ctx}.{key}: zorunlu, boş olmayan string olmalı.")
    return val


def _parse_agent_id(raw: object, context: str) -> uuid.UUID | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ParseError(f"{context}: UUID string olmalı.")
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ParseError(f"{context}: '{raw}' geçerli bir UUID değil.")
