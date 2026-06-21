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
    # Çıktı (deterministik)
    "response_contains",
    "response_not_contains",
    "response_equals",
    "response_regex",
    # Trajectory / tool (deterministik)
    "tool_called",
    "tool_called_with_args",
    "tool_sequence",
    "tools_used",
    "tool_correctness",
    "no_tool_errors",
    # Operasyonel (deterministik)
    "latency_under",
    "finish_reason_is",
    "steps_under",
    "tokens_under",
    "cost_under",
    # Güvenlik (deterministik)
    "no_pii",
    "not_refused",
}


# LLM-as-judge metrik tipleri (Faz B) — opsiyonel, token harcar
JUDGE_TYPES = {
    "task_completion",      # agent hedefe ulaştı mı?
    "answer_correctness",   # çıktı beklenen cevaba göre doğru mu?
    "rubric",               # özel kriter (G-Eval)
    "step_efficiency",      # gereksiz adım/döngü var mı?
    "argument_correctness", # tool argümanları doğru muydu?
    "reasoning_quality",    # akıl yürütme tutarlı/ilgili mi?
    "safety",               # çıktı güvenli mi? (toksisite/zarar/önyargı yok)
    "output_quality",       # bileşik kalite: doğruluk+bütünlük+netlik+yardımcılık (F4.1)
}


@dataclass
class ParsedAssertion:
    type: str
    value: str | int | float


@dataclass
class ParsedJudge:
    type: str
    threshold: float = 0.7
    expected: str | None = None
    criteria: str | None = None
    name: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"type": self.type, "threshold": self.threshold}
        if self.expected is not None:
            d["expected"] = self.expected
        if self.criteria is not None:
            d["criteria"] = self.criteria
        if self.name is not None:
            d["name"] = self.name
        return d


@dataclass
class ParsedTestCase:
    name: str
    input: str
    assertions: list[ParsedAssertion]
    judges: list[ParsedJudge] = field(default_factory=list)
    repeat: int = 1
    min_pass_rate: float = 1.0
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
    suite_judges = _parse_judges(data.get("judges"), "suite")  # tüm case'lere uygulanır
    suite_repeat = _parse_repeat(data.get("repeat"), "suite", 1)
    suite_min_pass = _parse_min_pass_rate(data.get("min_pass_rate"), "suite", 1.0)

    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) == 0:
        raise ParseError("'cases' en az bir element içeren bir liste olmalı.")

    cases: list[ParsedTestCase] = []
    for i, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, dict):
            raise ParseError(f"cases[{i}]: dict olmalı.")
        cases.append(_parse_case(
            raw_case, i, suite_agent_id, suite_judges, suite_repeat, suite_min_pass,
        ))

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
    suite_judges: list[ParsedJudge] | None = None,
    suite_repeat: int = 1,
    suite_min_pass: float = 1.0,
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

    # Judges: suite-level + case-level (birleştirilir)
    case_judges = _parse_judges(raw.get("judges"), ctx, expected_output)
    judges = list(suite_judges or []) + case_judges

    # Tutarlılık: case-level varsa onu, yoksa suite-level'ı kullan
    repeat = _parse_repeat(raw.get("repeat"), ctx, suite_repeat)
    min_pass_rate = _parse_min_pass_rate(raw.get("min_pass_rate"), ctx, suite_min_pass)

    return ParsedTestCase(
        name=name,
        input=input_text,
        agent_id=agent_id,
        expected_output=expected_output,
        rag_context=rag_context,
        assertions=assertions,
        judges=judges,
        repeat=repeat,
        min_pass_rate=min_pass_rate,
    )


def _parse_repeat(raw: object, ctx: str, default: int) -> int:
    if raw is None:
        return default
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise ParseError(f"{ctx}.repeat: tam sayı olmalı.")
    if not 1 <= n <= 20:
        raise ParseError(f"{ctx}.repeat: 1–20 aralığında olmalı.")
    return n


def _parse_min_pass_rate(raw: object, ctx: str, default: float) -> float:
    if raw is None:
        return default
    try:
        r = float(raw)
    except (TypeError, ValueError):
        raise ParseError(f"{ctx}.min_pass_rate: sayı olmalı.")
    if not 0.0 <= r <= 1.0:
        raise ParseError(f"{ctx}.min_pass_rate: 0.0–1.0 aralığında olmalı.")
    return r


def _parse_judges(
    raw: object,
    ctx: str,
    case_expected: str | None = None,
) -> list[ParsedJudge]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ParseError(f"{ctx}.judges: liste olmalı.")
    judges: list[ParsedJudge] = []
    for j, raw_j in enumerate(raw):
        jctx = f"{ctx}.judges[{j}]"
        if not isinstance(raw_j, dict):
            raise ParseError(f"{jctx}: dict olmalı.")
        j_type = _require_str(raw_j, "type", jctx)
        if j_type not in JUDGE_TYPES:
            raise ParseError(
                f"{jctx}.type '{j_type}' desteklenmiyor. Geçerli: {sorted(JUDGE_TYPES)}"
            )
        threshold = raw_j.get("threshold", 0.7)
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            raise ParseError(f"{jctx}.threshold: sayı olmalı.")
        if not 0.0 <= threshold <= 1.0:
            raise ParseError(f"{jctx}.threshold: 0.0–1.0 aralığında olmalı.")

        expected = raw_j.get("expected")
        if expected is None and j_type == "answer_correctness":
            expected = case_expected  # case.expected_output'a düş
        criteria = raw_j.get("criteria")
        if j_type == "rubric" and not (criteria and str(criteria).strip()):
            raise ParseError(f"{jctx}: 'rubric' için 'criteria' zorunlu.")
        if j_type == "answer_correctness" and not (expected and str(expected).strip()):
            raise ParseError(
                f"{jctx}: 'answer_correctness' için 'expected' (veya case.expected_output) zorunlu."
            )

        judges.append(ParsedJudge(
            type=j_type,
            threshold=threshold,
            expected=str(expected) if expected is not None else None,
            criteria=str(criteria) if criteria is not None else None,
            name=raw_j.get("name"),
        ))
    return judges


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
