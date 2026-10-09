#!/usr/bin/env python3
"""Validate the included good and bad CSV fixtures."""

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from csv_validator import load_schema, validate_csv  # noqa: E402


def main():
    examples = Path(__file__).resolve().parent
    schema = load_schema(examples / "schema.json")

    valid_report = validate_csv(examples / "valid-customers.csv", schema)
    print("VALID DATASET")
    print(json.dumps(valid_report, indent=2, sort_keys=True))
    assert valid_report["valid"]

    invalid_report = validate_csv(examples / "invalid-customers.csv", schema)
    print("\nINVALID DATASET")
    print(json.dumps(invalid_report, indent=2, sort_keys=True))
    assert not invalid_report["valid"]
    assert {item["code"] for item in invalid_report["errors"]} >= {
        "regex",
        "min",
        "type",
        "duplicate",
    }
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
