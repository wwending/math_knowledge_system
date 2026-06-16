"""
Manual DeepSeek check script.

This file is intentionally placed outside pytest auto-discovery.
It is not part of the automated test suite.
"""

from __future__ import annotations

from app.services.llm import nlp_service


def main() -> None:
    sample_text = "y y ^ { 2 } = 4 x"
    print("Running manual DeepSeek check...")
    result = nlp_service.analyze(sample_text)
    print("Manual check result:")
    print(result)


if __name__ == "__main__":
    main()
