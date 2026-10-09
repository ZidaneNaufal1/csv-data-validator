#!/usr/bin/env python3
"""Validate CSV files against a small, explicit JSON schema."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple


SUPPORTED_TYPES = {"string", "integer", "number", "boolean", "date"}
TRUE_VALUES = {"true", "1", "yes", "y"}
FALSE_VALUES = {"false", "0", "no", "n"}


class ValidationInputError(Exception):
    """Raised when the CSV or schema cannot be processed safely."""


def load_schema(path: Path) -> Dict[str, Any]:
    try:
        with path.expanduser().open("r", encoding="utf-8") as source:
            schema = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationInputError(f"Unable to read schema {path}: {exc}") from exc

    if not isinstance(schema, dict) or not isinstance(schema.get("columns"), dict):
        raise ValidationInputError("Schema must contain a 'columns' JSON object")
    if not schema["columns"]:
        raise ValidationInputError("Schema must define at least one column")
    if not isinstance(schema.get("allow_extra_columns", False), bool):
        raise ValidationInputError("allow_extra_columns must be true or false")

    compiled_patterns: Dict[str, Pattern[str]] = {}
    for column, rules in schema["columns"].items():
        if not isinstance(column, str) or not column:
            raise ValidationInputError("Schema column names must be non-empty strings")
        if not isinstance(rules, dict):
            raise ValidationInputError(f"Rules for {column!r} must be a JSON object")
        data_type = rules.get("type", "string")
        if data_type not in SUPPORTED_TYPES:
            raise ValidationInputError(f"Unsupported type for {column}: {data_type!r}")
        for flag in ("required", "unique"):
            if flag in rules and not isinstance(rules[flag], bool):
                raise ValidationInputError(f"{flag} for {column} must be true or false")
        if "enum" in rules and not isinstance(rules["enum"], list):
            raise ValidationInputError(f"enum for {column} must be an array")
        if "regex" in rules:
            if not isinstance(rules["regex"], str):
                raise ValidationInputError(f"regex for {column} must be a string")
            try:
                compiled_patterns[column] = re.compile(rules["regex"])
            except re.error as exc:
                raise ValidationInputError(f"Invalid regex for {column}: {exc}") from exc

    schema["_compiled_patterns"] = compiled_patterns
    return schema


def _error(row: int, column: Optional[str], code: str, message: str, value: Any = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "row": row,
        "column": column,
        "code": code,
        "message": message,
    }
    if value is not None:
        result["value"] = value
    return result


def _convert(value: str, data_type: str) -> Tuple[bool, Any]:
    try:
        if data_type == "string":
            return True, value
        if data_type == "integer":
            if not re.fullmatch(r"[+-]?\d+", value.strip()):
                return False, None
            return True, int(value)
        if data_type == "number":
            return True, float(value)
        if data_type == "boolean":
            normalized = value.strip().lower()
            if normalized in TRUE_VALUES:
                return True, True
            if normalized in FALSE_VALUES:
                return True, False
            return False, None
        if data_type == "date":
            return True, date.fromisoformat(value.strip())
    except (ValueError, OverflowError):
        return False, None
    return False, None


def validate_csv(csv_path: Path, schema: Dict[str, Any]) -> Dict[str, Any]:
    csv_path = csv_path.expanduser().resolve()
    if not csv_path.is_file():
        raise ValidationInputError(f"CSV file does not exist: {csv_path}")

    rules_by_column = schema["columns"]
    patterns = schema.get("_compiled_patterns", {})
    errors: List[Dict[str, Any]] = []
    invalid_data_rows = set()
    total_rows = 0
    seen: Dict[str, Dict[str, int]] = {
        column: {} for column, rules in rules_by_column.items() if rules.get("unique")
    }

    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            headers = reader.fieldnames
            if headers is None:
                raise ValidationInputError("CSV file has no header row")
            if any(header is None or header == "" for header in headers):
                errors.append(_error(1, None, "empty_header", "Header names cannot be empty"))
            duplicates = sorted({header for header in headers if headers.count(header) > 1})
            for header in duplicates:
                errors.append(_error(1, header, "duplicate_header", "Header appears more than once"))

            header_set = set(headers)
            for column in rules_by_column:
                if column not in header_set:
                    errors.append(_error(1, column, "missing_column", "Required schema column is absent"))
            if not schema.get("allow_extra_columns", False):
                for column in sorted(header_set - set(rules_by_column)):
                    errors.append(_error(1, column, "extra_column", "Column is not allowed by the schema"))

            for row_number, row in enumerate(reader, start=2):
                total_rows += 1
                before = len(errors)
                if None in row:
                    errors.append(
                        _error(row_number, None, "malformed_row", "Row has more fields than the header")
                    )

                for column, rules in rules_by_column.items():
                    raw = row.get(column)
                    value = "" if raw is None else raw
                    blank = value.strip() == ""
                    if blank:
                        if rules.get("required", False):
                            errors.append(
                                _error(row_number, column, "required", "Value is required", value)
                            )
                        continue

                    data_type = rules.get("type", "string")
                    valid_type, converted = _convert(value, data_type)
                    if not valid_type:
                        errors.append(
                            _error(
                                row_number,
                                column,
                                "type",
                                f"Expected {data_type}",
                                value,
                            )
                        )
                        continue

                    if "enum" in rules and value not in rules["enum"]:
                        errors.append(
                            _error(row_number, column, "enum", "Value is not in the allowed list", value)
                        )
                    if column in patterns and patterns[column].fullmatch(value) is None:
                        errors.append(
                            _error(row_number, column, "regex", "Value does not match the required pattern", value)
                        )
                    if data_type in {"integer", "number"}:
                        if "min" in rules and converted < rules["min"]:
                            errors.append(_error(row_number, column, "min", f"Value must be at least {rules['min']}", value))
                        if "max" in rules and converted > rules["max"]:
                            errors.append(_error(row_number, column, "max", f"Value must be at most {rules['max']}", value))
                    if data_type == "string":
                        if "min_length" in rules and len(value) < rules["min_length"]:
                            errors.append(_error(row_number, column, "min_length", f"Value must contain at least {rules['min_length']} characters", value))
                        if "max_length" in rules and len(value) > rules["max_length"]:
                            errors.append(_error(row_number, column, "max_length", f"Value must contain at most {rules['max_length']} characters", value))

                    if rules.get("unique"):
                        first_row = seen[column].get(value)
                        if first_row is not None:
                            errors.append(
                                _error(row_number, column, "duplicate", f"Value first appeared on row {first_row}", value)
                            )
                        else:
                            seen[column][value] = row_number

                if len(errors) > before:
                    invalid_data_rows.add(row_number)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValidationInputError(f"Unable to parse CSV {csv_path}: {exc}") from exc

    return {
        "valid": not errors,
        "source": str(csv_path),
        "summary": {
            "total_rows": total_rows,
            "valid_rows": total_rows - len(invalid_data_rows),
            "invalid_rows": len(invalid_data_rows),
            "errors": len(errors),
        },
        "errors": errors,
    }


def write_report(path: Path, report: Dict[str, Any]) -> None:
    try:
        with path.expanduser().open("w", encoding="utf-8") as destination:
            json.dump(report, destination, indent=2, sort_keys=True)
            destination.write("\n")
    except OSError as exc:
        raise ValidationInputError(f"Unable to write report {path}: {exc}") from exc


def _print_summary(report: Dict[str, Any]) -> None:
    print(f"Validation status: {'VALID' if report['valid'] else 'INVALID'}")
    summary = report["summary"]
    print(f"  Data rows: {summary['total_rows']}")
    print(f"  Valid rows: {summary['valid_rows']}")
    print(f"  Invalid rows: {summary['invalid_rows']}")
    print(f"  Errors: {summary['errors']}")
    for item in report["errors"]:
        location = f"row {item['row']}"
        if item["column"]:
            location += f", column {item['column']}"
        print(f"  - {location}: [{item['code']}] {item['message']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate CSV data without modifying the source file."
    )
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="Write a JSON validation report")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        schema = load_schema(args.schema)
        report = validate_csv(args.csv_file, schema)
        if args.report:
            write_report(args.report, report)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            _print_summary(report)
        return 0 if report["valid"] else 1
    except ValidationInputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
