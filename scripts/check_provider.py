"""Opt-in live smoke check using a fixed synthetic payload, never uploaded data."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sales_ai.ai import PROVIDERS, _call_llm, _classify_error, verify_api_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=list(PROVIDERS), default="groq")
    args = parser.parse_args(argv)
    key = os.getenv(PROVIDERS[args.provider]["env"], "").strip()
    if not key:
        print(f"Set {PROVIDERS[args.provider]['env']} in the environment before running this opt-in check.")
        return 2
    usable, message = verify_api_key(args.provider, key)
    if not usable:
        print(message)
        return 1
    if message:
        print(message)
    try:
        text = _call_llm(
            args.provider, key,
            "Summarise the provided fictional totals in one sentence; do not add facts.",
            "Synthetic smoke test: revenue=100, cost=60, profit=40, orders=2, currency=INR.",
            max_tokens=100,
        )
        if not text.strip():
            raise RuntimeError("Provider returned no answer.")
    except Exception as exc:
        print(_classify_error(exc, args.provider))
        return 1
    print(f"PASS: {PROVIDERS[args.provider]['label']} returned nonempty text for the synthetic smoke test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
