"""Convenience entry point for the official 10-class dataset audit."""

from __future__ import annotations

import sys

from audit_12class_dataset import main


if __name__ == "__main__":
    if "--contract" not in sys.argv:
        sys.argv.extend(("--contract", "10"))
    main()
