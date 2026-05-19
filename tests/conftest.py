"""Pytest configuration shared by all test suites."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `import langchain_rabbitmq` when running tests without installation.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
