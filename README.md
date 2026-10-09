# CSV Data Validator

[![Tests](https://github.com/ZidaneNaufal1/csv-data-validator/actions/workflows/tests.yml/badge.svg)](https://github.com/ZidaneNaufal1/csv-data-validator/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A dependency-free Python CLI that validates CSV files against a readable JSON
schema and produces precise row-level error reports without changing source
data.

## Why This Exists

CSV imports often fail late because columns, types, required values, or unique
identifiers are wrong. This tool finds those problems before the data reaches a
database, spreadsheet workflow, or application.

## Features

- Required and allowed column validation
- `string`, `integer`, `number`, `boolean`, and ISO date types
- Minimum, maximum, string length, regex, enum, and uniqueness rules
- UTF-8 BOM support
- Detection of duplicate headers and malformed rows
- Human-readable output and structured JSON reports
- Stable exit codes for scripts and CI
- Read-only processing of the source CSV

## Requirements

- Python 3.9 or newer
- No third-party packages

## Quick Start

```bash
git clone https://github.com/ZidaneNaufal1/csv-data-validator.git
cd csv-data-validator
python csv_validator.py customers.csv --schema example-schema.json
```

Write and print a JSON report:

```bash
python csv_validator.py customers.csv \
  --schema example-schema.json \
  --report validation-report.json \
  --json
```

## Schema Format

```json
{
  "allow_extra_columns": false,
  "columns": {
    "email": {
      "type": "string",
      "required": true,
      "unique": true,
      "regex": "[^@]+@[^@]+\\.[^@]+"
    },
    "age": {"type": "integer", "min": 0, "max": 130},
    "active": {"type": "boolean"},
    "joined": {"type": "date"}
  }
}
```

Boolean values accept `true`, `false`, `1`, `0`, `yes`, `no`, `y`, and `n`.
Dates use ISO format such as `2026-10-09`.

## Exit Codes

| Code | Meaning |
|---:|---|
| `0` | CSV is valid |
| `1` | Validation errors were found |
| `2` | CSV, schema, or report could not be processed |

## Safety and Limitations

The validator never rewrites the source CSV. Validation is performed in one
pass, but unique values are retained in memory. Very large unique datasets may
therefore require substantial memory. This version supports comma-delimited
UTF-8 data and does not infer schemas automatically.

## Tests

```bash
python -m unittest discover -v
```

The suite covers valid data, BOM input, required values, types, duplicates,
missing and extra columns, malformed rows, source immutability, invalid schemas,
reports, and exit codes. CI runs on Python 3.9, 3.11, and 3.13.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Release history is recorded in
[CHANGELOG.md](CHANGELOG.md).

## License

MIT License. See [LICENSE](LICENSE).
