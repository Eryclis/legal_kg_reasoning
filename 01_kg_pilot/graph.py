from collections import Counter
from dataclasses import asdict

import networkx as nx

from models import Edge


def build_networkx_graph(nodes: dict, edges: list[Edge]) -> nx.DiGraph:
    G = nx.DiGraph()

    for node_id, node in nodes.items():
        d = asdict(node)
        label = (
            d.get("title")
            or d.get("thesis_text")
            or d.get("sub_ref")
            or d.get("citation_raw")
            or node_id
        )
        G.add_node(
            node_id,
            type=d.get("node_type", ""),
            label=label[:80],
            weight=d.get("authority_weight", 1.0),
        )

    for edge in edges:
        if edge.target not in G:
            G.add_node(edge.target, type="UnresolvedCitation", label=edge.target, weight=0.0)
        safe_meta = {k: v for k, v in edge.metadata.items() if isinstance(v, (str, int, float, bool))}
        G.add_edge(edge.source, edge.target, relation=edge.relation, weight=edge.weight, **safe_meta)

    return G


def print_graph_summary(G: nx.DiGraph, norma_id: str) -> None:
    print(f"\n{'='*62}")
    print(f"  Graph Summary — {norma_id}")
    print(f"{'='*62}")
    print(f"  Nodes : {G.number_of_nodes()}")
    print(f"  Edges : {G.number_of_edges()}")

    node_types = Counter(d.get("type", "Unknown") for _, d in G.nodes(data=True))
    print("\n  Node type distribution:")
    for ntype, count in node_types.most_common():
        print(f"    {ntype:<38} {count:>4d}")

    edge_types = Counter(d.get("relation", "Unknown") for _, _, d in G.edges(data=True))
    print("\n  Edge type distribution:")
    for etype, count in edge_types.most_common():
        print(f"    {etype:<38} {count:>4d}")

    print("\n  Top-5 nodes by in-degree:")
    top5 = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)[:5]
    for node_id, deg in top5:
        label = G.nodes[node_id].get("label", node_id)
        print(f"    [{deg:>3d}]  {label}")

    print(f"{'='*62}\n")
