"""LLM adapters (Gemini via LangChain, so the Langfuse callback captures each generation).

Thinking level "low" halves router latency versus the default with the same extraction
quality on our cases, and `include_thoughts` records the model's reasoning in the trace.
"""

from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI

from mira.config import Settings
from mira.state import TurnAnalysis


def chat_model(
    settings: Settings, model: str, name: str, temperature: float = 0.0, thinking_level: str = "low",
) -> ChatGoogleGenerativeAI:
    if not settings.google_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set (see .env.example).")
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.google_api_key,
        temperature=temperature,
        max_retries=2,
        name=name,  # generation name in Langfuse; stable, model-independent
        thinking_config={"thinking_level": thinking_level},
        include_thoughts=True,
    )


def make_analyzer(settings: Settings):
    model = chat_model(settings, settings.mira_model_large, name="classify-turn")
    structured = model.with_structured_output(TurnAnalysis)

    def analyze(messages: list) -> TurnAnalysis:
        return structured.invoke(messages, config={"run_name": "extract-trip-details"})

    return analyze


def make_writer(settings: Settings):
    model = chat_model(settings, settings.mira_model_large, name="write-reply", temperature=0.3)

    def write(messages: list) -> str:
        return model.invoke(messages).text  # .text excludes thinking blocks

    return write
