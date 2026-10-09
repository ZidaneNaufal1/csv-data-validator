import json
import tempfile
import unittest
from pathlib import Path

import csv_validator


class CsvValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.schema_path = self.root / "schema.json"
        self.schema_data = {
            "allow_extra_columns": False,
            "columns": {
                "email": {
                    "type": "string",
                    "required": True,
                    "unique": True,
                    "regex": r"[^@]+@[^@]+\.[^@]+",
                },
                "age": {"type": "integer", "required": True, "min": 0, "max": 130},
                "active": {"type": "boolean", "required": True},
                "joined": {"type": "date"},
            },
        }
        self.schema_path.write_text(json.dumps(self.schema_data), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def write_csv(self, content, name="data.csv", encoding="utf-8"):
        path = self.root / name
        path.write_text(content, encoding=encoding)
        return path

    def validate(self, content, encoding="utf-8"):
        path = self.write_csv(content, encoding=encoding)
        schema = csv_validator.load_schema(self.schema_path)
        return csv_validator.validate_csv(path, schema)

    def test_valid_csv_passes(self):
        report = self.validate(
            "email,age,active,joined\na@example.com,21,true,2026-10-09\n"
        )
        self.assertTrue(report["valid"])
        self.assertEqual(report["summary"]["valid_rows"], 1)

    def test_bom_header_is_supported(self):
        report = self.validate(
            "email,age,active,joined\na@example.com,21,yes,\n", encoding="utf-8-sig"
        )
        self.assertTrue(report["valid"])

    def test_required_and_type_errors_are_reported(self):
        report = self.validate("email,age,active,joined\n,old,maybe,not-a-date\n")
        codes = {item["code"] for item in report["errors"]}
        self.assertEqual(codes, {"required", "type"})

    def test_duplicate_unique_value_is_reported(self):
        report = self.validate(
            "email,age,active,joined\na@example.com,20,true,\n"
            "a@example.com,21,false,\n"
        )
        self.assertIn("duplicate", [item["code"] for item in report["errors"]])

    def test_missing_and_extra_columns_are_reported(self):
        report = self.validate("email,age,extra\na@example.com,20,x\n")
        codes = [item["code"] for item in report["errors"]]
        self.assertIn("missing_column", codes)
        self.assertIn("extra_column", codes)

    def test_too_many_fields_are_reported_as_malformed(self):
        report = self.validate(
            "email,age,active,joined\na@example.com,20,true,,unexpected\n"
        )
        self.assertIn("malformed_row", [item["code"] for item in report["errors"]])

    def test_source_file_is_not_modified(self):
        content = "email,age,active,joined\na@example.com,20,true,\n"
        path = self.write_csv(content)
        before = path.read_bytes()
        schema = csv_validator.load_schema(self.schema_path)
        csv_validator.validate_csv(path, schema)
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_schema_is_rejected(self):
        self.schema_path.write_text('{"columns":{"age":{"type":"unknown"}}}', encoding="utf-8")
        with self.assertRaises(csv_validator.ValidationInputError):
            csv_validator.load_schema(self.schema_path)

    def test_cli_writes_json_report_and_returns_one(self):
        path = self.write_csv("email,age,active,joined\nbad,-1,maybe,\n")
        report_path = self.root / "report.json"
        code = csv_validator.main(
            [str(path), "--schema", str(self.schema_path), "--report", str(report_path)]
        )
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(report_path.read_text(encoding="utf-8"))["valid"])


if __name__ == "__main__":
    unittest.main()
