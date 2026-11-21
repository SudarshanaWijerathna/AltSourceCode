"""Unit tests never call real LLMs or send traces."""

import os

os.environ["MIRA_TRACING"] = "false"
os.environ["MIRA_ENVIRONMENT"] = "test"
