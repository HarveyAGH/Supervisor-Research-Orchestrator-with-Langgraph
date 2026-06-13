# evals/test_pipeline.py
import pytest
from langchain_core.messages import HumanMessage
from graph import app

THREAD_ID = "eval-test-1"
CONFIG = {"configurable": {"thread_id": THREAD_ID}}

GOLDEN_QUERY = "What is the capital of France and why is it historically significant?"

def run_pipeline(query: str) -> dict:
    """Run the full pipeline and return final state."""
    final_state = None
    for _, step in app.stream(
        {"messages": [HumanMessage(content=query)]},
        config=CONFIG,
        stream_mode="updates",
        subgraphs=True,
    ):
        final_state = step
    return app.get_state(CONFIG).values


def test_pipeline_completes():
    """Pipeline must reach APPROVED without infinite loops."""
    state = run_pipeline(GOLDEN_QUERY)
    assert state["validator_status"] == "APPROVED"


def test_pipeline_produces_output():
    """final_output.md must exist and be non-empty."""
    from pathlib import Path
    output = Path("final_output.md")
    assert output.exists()
    assert len(output.read_text()) > 500


def test_validator_result_is_structured():
    """validator_status must be a valid Literal value, not a raw string."""
    state = run_pipeline(GOLDEN_QUERY)
    assert state["validator_status"] in ("APPROVED", "REVISION_NEEDED")