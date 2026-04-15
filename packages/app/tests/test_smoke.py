from app.graph import to_dot
from refsite import abbey_road


def test_to_dot_produces_dag() -> None:
    """The Graphviz topology renders the expected clusters, nodes, and edges."""
    dot = to_dot(abbey_road.build())
    assert dot.startswith("digraph G {")
    assert "cluster_B1" in dot
    # Coefficient lives on the feeds edge, not on the virtual node label.
    assert 'label="k=0.7"' in dot  # edge label for share feed
    assert 'label="k=1.0"' in dot  # aggregator edges into POOL
    assert "(virtual, k=" not in dot  # never on the node
    # Key edges present.
    assert '"I1" -> "POOL"' in dot
    assert '"POOL" -> "M0"' in dot
    assert '"M0" -> "M1"' in dot
    assert '"V4" -> "M9"' in dot
    # POOL→M1 no longer exists; it's via M0 now.
    assert '"POOL" -> "M1"' not in dot
    # Building cluster label is just the id.
    assert 'label="B5"' in dot
    # Refs and legend are intentionally absent from the main graph.
    assert "_ref_" not in dot
    assert "cluster_legend" not in dot
    # Zones still render.
    assert "cluster_B1.office" in dot
    assert "cluster_B1.production" in dot
