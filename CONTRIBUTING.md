# Contributing

Thank you for improving CSV Data Validator.

1. Open an issue for a bug or substantial feature.
2. Create a focused branch from `main`.
3. Keep source CSV processing read-only.
4. Add tests for every changed validation rule.
5. Run `python -m py_compile csv_validator.py` and
   `python -m unittest discover -v`.
6. Update the README or changelog for user-visible changes.
7. Open a pull request with the problem, solution, and test evidence.

Use generated fixtures in temporary directories. Never commit private or real
customer data, credentials, or personally identifiable information.
