from langgraph.graph import StateGraph, END

from graph.state import ReconciliationState
from graph.nodes import (
    file_ingestion,
    db_query,
    reconciliation,
    report_generation,
    dispatcher,
)


def build_graph():
    """Assemble and compile the reconciliation pipeline graph."""
    g = StateGraph(ReconciliationState)

    g.add_node("file_ingestion", file_ingestion.run)
    g.add_node("db_query", db_query.run)
    g.add_node("reconciliation", reconciliation.run)
    g.add_node("report_generation", report_generation.run)
    g.add_node("dispatcher", dispatcher.run)

    g.set_entry_point("file_ingestion")
    g.add_edge("file_ingestion", "db_query")
    g.add_edge("db_query", "reconciliation")
    g.add_edge("reconciliation", "report_generation")
    g.add_edge("report_generation", "dispatcher")
    g.add_edge("dispatcher", END)

    return g.compile()
