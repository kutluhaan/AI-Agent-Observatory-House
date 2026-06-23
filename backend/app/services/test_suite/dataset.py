"""
Dataset → test suite — B2 (#5)

CSV veya JSONL dataset'ini ({input, expected} satırları) test suite YAML'ına çevirir.
Her satır bir test case olur: input + (expected varsa) bir assertion.
YAML yazmadan toplu/veri-odaklı test oluşturmayı sağlar.
"""
from __future__ import annotations

import csv
import io
import json

import yaml

# UI seçimi → assertion tipi
_ASSERTION_MAP = {
    "contains": "response_contains",
    "equals": "response_equals",
    "regex": "response_regex",
}


class DatasetError(Exception):
    pass


def parse_dataset(content: str, fmt: str) -> list[dict]:
    """CSV/JSONL içeriğini [{input, expected}] listesine çevirir."""
    fmt = (fmt or "").lower()
    rows: list[dict] = []

    if fmt == "jsonl":
        for i, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"JSONL satır {i} geçersiz JSON: {exc}") from exc
            if not isinstance(obj, dict) or "input" not in obj:
                raise DatasetError(f"JSONL satır {i}: 'input' alanı zorunlu.")
            rows.append({"input": str(obj["input"]), "expected": str(obj.get("expected", "") or "")})
    elif fmt == "csv":
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames or "input" not in reader.fieldnames:
            raise DatasetError("CSV başlık satırında 'input' sütunu olmalı.")
        for r in reader:
            inp = (r.get("input") or "").strip()
            if not inp:
                continue
            rows.append({"input": inp, "expected": str(r.get("expected", "") or "")})
    else:
        raise DatasetError("format 'csv' veya 'jsonl' olmalı.")

    rows = [r for r in rows if r["input"].strip()]
    if not rows:
        raise DatasetError("Dataset boş — en az bir 'input' satırı gerekli.")
    if len(rows) > 500:
        raise DatasetError("Dataset en fazla 500 satır olabilir.")
    return rows


def build_suite_yaml(name: str, agent_id: str, rows: list[dict], assertion: str = "contains") -> str:
    """Satırlardan geçerli bir suite YAML'ı üretir (config_yaml olarak saklanır, sonradan düzenlenebilir)."""
    a_type = _ASSERTION_MAP.get((assertion or "contains").lower(), "response_contains")
    cases: list[dict] = []
    for i, r in enumerate(rows, 1):
        case: dict = {"name": f"row-{i}", "input": r["input"]}
        if r["expected"]:
            case["assertions"] = [{"type": a_type, "value": r["expected"]}]
        cases.append(case)
    suite = {"name": name, "agent_id": str(agent_id), "cases": cases}
    return yaml.safe_dump(suite, allow_unicode=True, sort_keys=False)
