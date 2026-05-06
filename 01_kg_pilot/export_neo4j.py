"""
Neo4j AuraDB export via Python driver.

Usage:
    from export_neo4j import export_to_neo4j
    export_to_neo4j(nodes, edges, uri="neo4j+s://...", user="neo4j", password="...")

The function wipes all existing data (MATCH (n) DETACH DELETE n) before
importing, so it is idempotent — safe to call multiple times during iteration.

Install the driver if needed:
    pip install neo4j
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict
from typing import Any

from models import Edge


def _sanitize_id(node_id: str) -> str:
    nfkd = unicodedata.normalize("NFKD", node_id)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9_\-]", "_", ascii_str)


def _node_props(node: Any, sanitized_id: str) -> dict:
    d = asdict(node)
    d["nodeId"] = sanitized_id
    d.pop("node_id", None)
    d.pop("node_type", None)
    # Collapse whitespace in text fields
    for key, val in d.items():
        if isinstance(val, str):
            d[key] = re.sub(r"\s+", " ", val).strip()
    return d


def export_to_neo4j(
    nodes: dict,
    edges: list[Edge],
    uri: str,
    user: str,
    password: str,
    batch_size: int = 500,
) -> None:
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise ImportError("neo4j driver not installed. Run: pip install neo4j")

    id_map: dict[str, str] = {nid: _sanitize_id(nid) for nid in nodes}

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print("[Neo4j] Clearing existing data...")
        session.run("MATCH (n) DETACH DELETE n")

        # ── Import nodes ──────────────────────────────────────────
        node_list = list(nodes.values())
        total = 0
        for start in range(0, len(node_list), batch_size):
            batch = node_list[start : start + batch_size]
            rows = [
                {
                    "props": _node_props(n, id_map[n.node_id]),
                    "label": getattr(n, "node_type", "Unknown"),
                }
                for n in batch
            ]
            session.run(
                """
                UNWIND $rows AS row
                CALL apoc.create.node([row.label], row.props) YIELD node
                RETURN count(node)
                """,
                rows=rows,
            )
            total += len(batch)

        print(f"[Neo4j] Imported {total} nodes")

        # ── Unique constraint so MATCH by nodeId is fast ──────────
        for label in {getattr(n, "node_type", "Unknown") for n in nodes.values()}:
            try:
                session.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.nodeId IS UNIQUE"
                )
            except Exception:
                pass  # constraint may already exist or APOC unavailable

        # ── Import edges ──────────────────────────────────────────
        total_edges = 0
        for start in range(0, len(edges), batch_size):
            batch = edges[start : start + batch_size]
            rows = [
                {
                    "src": id_map.get(e.source, _sanitize_id(e.source)),
                    "tgt": id_map.get(e.target, _sanitize_id(e.target)),
                    "rel": e.relation,
                    "weight": round(e.weight, 4),
                }
                for e in batch
            ]
            session.run(
                """
                UNWIND $rows AS row
                MATCH (a {nodeId: row.src})
                MATCH (b {nodeId: row.tgt})
                CALL apoc.create.relationship(a, row.rel, {weight: row.weight}, b) YIELD rel
                RETURN count(rel)
                """,
                rows=rows,
            )
            total_edges += len(batch)

        print(f"[Neo4j] Imported {total_edges} relationships")

    driver.close()
    print(f"[Neo4j] Done. Browse at: {uri.replace('neo4j+s://', 'https://').split('@')[0]}")
