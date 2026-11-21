"""Unit tests never call real LLMs, send traces, or touch the real database / published pages."""

import os
import tempfile

os.environ["MIRA_TRACING"] = "false"
os.environ["MIRA_ENVIRONMENT"] = "test"
os.environ["MIRA_DB_URL"] = "sqlite:///:memory:"
os.environ["MIRA_PUBLISHED_DIR"] = tempfile.mkdtemp(prefix="mira-published-")
