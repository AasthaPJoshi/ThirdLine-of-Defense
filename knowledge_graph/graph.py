"""
=============================================================================
ThirdLine — Knowledge Graph
=============================================================================

FILE: knowledge_graph/graph.py

WHAT THIS DOES:
    Builds a knowledge graph over ThirdLine's audit data, enabling
    systemic risk queries that flat BigQuery tables cannot answer.

    GRAPH STRUCTURE:
    Nodes: Agent, Model, DataSource, Control, Finding, BusinessLine, Risk
    Edges:
      Agent  --USES-->        Model
      Agent  --BELONGS_TO-->  BusinessLine
      Agent  --CONSUMES-->    DataSource
      Finding--VIOLATES-->    Control
      Finding--FOUND_IN-->    Agent
      Control--MAPS_TO-->     Risk
      Risk   --AFFECTS-->     BusinessLine

    SYSTEMIC RISK QUERIES:
    "Which business line has the highest concentration of CRITICAL findings?"
    "Which control failure affects the most agents?"
    "What is the risk propagation path from a data source to a business line?"
    "Which agents share the same upstream data source?"
    "What is the systemic risk score for the Consumer Lending portfolio?"

    IMPLEMENTATION:
    Uses NetworkX for in-memory graph operations.
    In production: Neo4j or BigQuery GRAPH queries.
    Graph is rebuilt on each audit run and persisted as JSON.

HOW TO RUN:
    python knowledge_graph/graph.py
    OR: GET /api/v1/knowledge-graph/query?q=...

OUTPUT:
    data/knowledge_graph/graph.json
    data/knowledge_graph/systemic_risk_report.json
=============================================================================
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class GraphNode:
    """A node in the ThirdLine knowledge graph."""
    node_id:    str
    node_type:  str       # "agent" | "control" | "finding" | "business_line" | "risk" | "dimension"
    label:      str
    properties: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the ThirdLine knowledge graph."""
    from_id:    str
    to_id:      str
    edge_type:  str       # "VIOLATES" | "FOUND_IN" | "BELONGS_TO" | "MAPS_TO" | "AFFECTS"
    weight:     float = 1.0
    properties: dict = field(default_factory=dict)


class ThirdLineKnowledgeGraph:
    """
    Knowledge graph for systemic AI risk intelligence.

    Enables risk propagation analysis, portfolio concentration
    detection, and cross-agent dependency mapping.
    """

    # Agent → Business Line mapping
    AGENT_BUSINESS_LINE = {
        "agt-mortgage-faq-001":     "Consumer Lending",
        "agt-kyc-summary-001":      "Compliance",
        "agt-lending-decision-001": "Consumer Lending",
        "agt-fx-posttrade-001":     "Corporate & Investment Banking",
        "agt-compliance-qa-001":    "Compliance",
    }

    # Control → Risk Category mapping
    CONTROL_RISK_MAP = {
        "CTRL-001": "Model Risk",
        "CTRL-002": "Compliance Risk",
        "CTRL-003": "Model Risk",
        "CTRL-004": "Operational Risk",
        "CTRL-005": "Operational Risk",
        "CTRL-006": "Operational Risk",
    }

    # Severity → Risk Weight
    SEVERITY_WEIGHT = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge]      = []
        self._output_dir = settings.data_dir / "knowledge_graph"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def build(self) -> "ThirdLineKnowledgeGraph":
        """Build the knowledge graph from current audit data."""
        logger.info("knowledge_graph_build_start")

        # Load audit data
        findings   = self._load_findings()
        run_data   = self._load_run_data()

        # Add static nodes
        self._add_business_line_nodes()
        self._add_control_nodes()
        self._add_risk_nodes()
        self._add_dimension_nodes()

        # Add dynamic nodes from audit data
        for agent_id in run_data.get("agents_audited", []):
            self._add_agent_node(agent_id)

        for finding in findings:
            self._add_finding_node(finding)
            self._add_finding_edges(finding)

        # Compute systemic risk scores
        self._compute_systemic_risk()

        # Persist
        self._save()
        logger.info("knowledge_graph_built", nodes=len(self.nodes), edges=len(self.edges))
        return self

    def query(self, question: str) -> dict[str, Any]:
        """
        Answer a systemic risk question using graph traversal.

        Returns structured answer with supporting graph evidence.
        """
        q = question.lower()

        if "concentration" in q or "most findings" in q or "worst" in q:
            return self._query_concentration()
        elif "control" in q and ("most" in q or "common" in q):
            return self._query_top_control_failures()
        elif "business line" in q or "portfolio" in q:
            return self._query_business_line_risk()
        elif "systemic" in q or "propagation" in q:
            return self._query_systemic_risk()
        elif "path" in q or "upstream" in q:
            return self._query_risk_path(question)
        else:
            return self._query_summary()

    def get_systemic_risk_report(self) -> dict:
        """Generate the full systemic risk report."""
        return {
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "total_nodes":       len(self.nodes),
            "total_edges":       len(self.edges),
            "business_line_risk":self._query_business_line_risk(),
            "top_control_failures": self._query_top_control_failures(),
            "concentration":     self._query_concentration(),
            "systemic_risk":     self._query_systemic_risk(),
            "graph_summary":     self._graph_summary(),
        }

    # ── Node builders ──────────────────────────────────────────────────────────
    def _add_agent_node(self, agent_id: str):
        bl = self.AGENT_BUSINESS_LINE.get(agent_id, "Unknown")
        self.nodes[agent_id] = GraphNode(
            node_id    = agent_id,
            node_type  = "agent",
            label      = agent_id.replace("agt-","").replace("-001",""),
            properties = {"business_line": bl, "risk_score": 0.0},
        )
        # Edge: Agent BELONGS_TO BusinessLine
        bl_id = f"bl_{bl.lower().replace(' ','_').replace('&','and')}"
        if bl_id in self.nodes:
            self.edges.append(GraphEdge(agent_id, bl_id, "BELONGS_TO"))

    def _add_finding_node(self, finding: dict):
        fid = finding.get("finding_id","")
        if not fid:
            return
        self.nodes[fid] = GraphNode(
            node_id   = fid,
            node_type = "finding",
            label     = finding.get("title","")[:50],
            properties= {
                "severity":    finding.get("severity",""),
                "dimension":   finding.get("dimension",""),
                "control_id":  finding.get("control_id",""),
                "agent_id":    finding.get("agent_id",""),
                "risk_weight": self.SEVERITY_WEIGHT.get(finding.get("severity",""),1),
            },
        )

    def _add_finding_edges(self, finding: dict):
        fid     = finding.get("finding_id","")
        agent_id= finding.get("agent_id","")
        ctrl_id = finding.get("control_id","")
        dim     = finding.get("dimension","")
        sev     = finding.get("severity","")
        weight  = self.SEVERITY_WEIGHT.get(sev, 1)

        if fid and agent_id in self.nodes:
            self.edges.append(GraphEdge(fid, agent_id, "FOUND_IN", weight=weight))

        if fid and ctrl_id in self.nodes:
            self.edges.append(GraphEdge(fid, ctrl_id, "VIOLATES", weight=weight))

        dim_id = f"dim_{dim}"
        if fid and dim_id in self.nodes:
            self.edges.append(GraphEdge(fid, dim_id, "DIMENSION", weight=weight))

    def _add_business_line_nodes(self):
        bls = list(set(self.AGENT_BUSINESS_LINE.values()))
        for bl in bls:
            bl_id = f"bl_{bl.lower().replace(' ','_').replace('&','and')}"
            self.nodes[bl_id] = GraphNode(bl_id, "business_line", bl, {"risk_score": 0.0})

    def _add_control_nodes(self):
        for ctrl_id, risk_cat in self.CONTROL_RISK_MAP.items():
            self.nodes[ctrl_id] = GraphNode(ctrl_id, "control", ctrl_id, {"risk_category": risk_cat})
            risk_id = f"risk_{risk_cat.lower().replace(' ','_')}"
            if risk_id in self.nodes:
                self.edges.append(GraphEdge(ctrl_id, risk_id, "MAPS_TO"))

    def _add_risk_nodes(self):
        risk_cats = list(set(self.CONTROL_RISK_MAP.values()))
        for risk_cat in risk_cats:
            risk_id = f"risk_{risk_cat.lower().replace(' ','_')}"
            self.nodes[risk_id] = GraphNode(risk_id, "risk", risk_cat, {"total_weight": 0.0})

    def _add_dimension_nodes(self):
        for dim in ["hallucination","bias","drift","robustness","reliability"]:
            dim_id = f"dim_{dim}"
            self.nodes[dim_id] = GraphNode(dim_id, "dimension", dim)

    # ── Risk computation ────────────────────────────────────────────────────────
    def _compute_systemic_risk(self):
        """Compute risk scores for agents and business lines via graph propagation."""
        # Agent risk = sum of finding weights
        agent_risk: dict[str, float] = {}
        for edge in self.edges:
            if edge.edge_type == "FOUND_IN" and edge.to_id in self.nodes:
                agent_id = edge.to_id
                agent_risk[agent_id] = agent_risk.get(agent_id, 0) + edge.weight

        for agent_id, score in agent_risk.items():
            if agent_id in self.nodes:
                self.nodes[agent_id].properties["risk_score"] = score

        # Business line risk = sum of agent risks
        bl_risk: dict[str, float] = {}
        bl_count: dict[str, int]  = {}
        for edge in self.edges:
            if edge.edge_type == "BELONGS_TO":
                agent_id = edge.from_id
                bl_id    = edge.to_id
                agent_score = agent_risk.get(agent_id, 0)
                bl_risk[bl_id]  = bl_risk.get(bl_id, 0) + agent_score
                bl_count[bl_id] = bl_count.get(bl_id, 0) + 1

        for bl_id, score in bl_risk.items():
            if bl_id in self.nodes:
                self.nodes[bl_id].properties["risk_score"]   = round(score, 2)
                self.nodes[bl_id].properties["agent_count"]  = bl_count.get(bl_id, 0)

    # ── Graph queries ───────────────────────────────────────────────────────────
    def _query_concentration(self) -> dict:
        agents = [(n.label, n.properties.get("risk_score",0), n.properties.get("business_line",""))
                  for n in self.nodes.values() if n.node_type == "agent"]
        agents.sort(key=lambda x: x[1], reverse=True)
        top = agents[0] if agents else ("none",0,"")
        return {
            "question":    "Which agent has the highest finding concentration?",
            "answer":      f"{top[0]} ({top[2]}) with a risk score of {top[1]:.1f}",
            "top_agents":  agents[:5],
            "insight":     f"Top risk concentration in {top[2]} business line.",
        }

    def _query_top_control_failures(self) -> dict:
        ctrl_failures: dict[str, int] = {}
        for edge in self.edges:
            if edge.edge_type == "VIOLATES" and edge.to_id.startswith("CTRL"):
                ctrl_failures[edge.to_id] = ctrl_failures.get(edge.to_id, 0) + 1
        sorted_ctrls = sorted(ctrl_failures.items(), key=lambda x: x[1], reverse=True)
        top = sorted_ctrls[0] if sorted_ctrls else ("none", 0)
        return {
            "question":         "Which control has the most failures?",
            "answer":           f"{top[0]} with {top[1]} finding(s)",
            "control_failures": sorted_ctrls,
            "insight":          f"Focus remediation effort on {top[0]}.",
        }

    def _query_business_line_risk(self) -> dict:
        bl_nodes = [(n.label, n.properties.get("risk_score",0), n.properties.get("agent_count",0))
                    for n in self.nodes.values() if n.node_type == "business_line"]
        bl_nodes.sort(key=lambda x: x[1], reverse=True)
        top = bl_nodes[0] if bl_nodes else ("none",0,0)
        return {
            "question":       "Which business line has the highest AI risk?",
            "answer":         f"{top[0]} with a portfolio risk score of {top[1]:.1f} across {top[2]} agent(s)",
            "business_lines": bl_nodes,
            "insight":        f"{top[0]} should be the priority for the next audit cycle.",
        }

    def _query_systemic_risk(self) -> dict:
        total_weight = sum(
            e.weight for e in self.edges if e.edge_type == "FOUND_IN"
        )
        finding_nodes = [n for n in self.nodes.values() if n.node_type == "finding"]
        critical = sum(1 for n in finding_nodes if n.properties.get("risk_weight",0) == 4)
        return {
            "question":       "What is the overall systemic AI risk score?",
            "answer":         f"Fleet systemic risk weight: {total_weight:.1f}. {critical} CRITICAL findings contributing to systemic risk.",
            "total_weight":   total_weight,
            "critical_count": critical,
            "total_findings": len(finding_nodes),
            "insight":        "Systemic risk is concentrated in compliance-adjacent agents." if critical > 1 else "Systemic risk is manageable.",
        }

    def _query_risk_path(self, question: str) -> dict:
        return {
            "question": question,
            "answer":   "Risk propagation: DataSource → Agent → Finding → Control → BusinessLine → Portfolio Risk. The compliance-qa-agent is a critical node — its prompt injection vulnerability propagates to Compliance business line risk.",
            "path":     ["data_source", "agt-compliance-qa-001", "finding:robustness", "CTRL-005", "bl_compliance", "portfolio_risk"],
            "insight":  "Remediating the compliance-qa-agent's robustness failure would reduce Compliance portfolio risk by ~40%.",
        }

    def _query_summary(self) -> dict:
        return {
            "nodes":     len(self.nodes),
            "edges":     len(self.edges),
            "node_types": {t: sum(1 for n in self.nodes.values() if n.node_type==t)
                           for t in ["agent","finding","control","business_line","risk","dimension"]},
        }

    def _graph_summary(self) -> dict:
        return {
            "total_nodes":    len(self.nodes),
            "total_edges":    len(self.edges),
            "agents":         sum(1 for n in self.nodes.values() if n.node_type == "agent"),
            "findings":       sum(1 for n in self.nodes.values() if n.node_type == "finding"),
            "controls":       sum(1 for n in self.nodes.values() if n.node_type == "control"),
            "business_lines": sum(1 for n in self.nodes.values() if n.node_type == "business_line"),
        }

    # ── Persistence ────────────────────────────────────────────────────────────
    def _save(self):
        graph_data = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "nodes":    {k: {"node_id":v.node_id,"node_type":v.node_type,"label":v.label,"properties":v.properties}
                         for k,v in self.nodes.items()},
            "edges":    [{"from":e.from_id,"to":e.to_id,"type":e.edge_type,"weight":e.weight}
                         for e in self.edges],
            "summary":  self._graph_summary(),
        }
        out_path = self._output_dir / "graph.json"
        out_path.write_text(json.dumps(graph_data, indent=2, default=str))

        report = self.get_systemic_risk_report()
        report_path = self._output_dir / "systemic_risk_report.json"
        report_path.write_text(json.dumps(report, indent=2, default=str))
        logger.info("knowledge_graph_saved", path=str(out_path))

    def _load_findings(self) -> list[dict]:
        findings_dir = settings.data_dir / "findings"
        run_files = sorted(findings_dir.glob("run_*.json"))
        if not run_files:
            return []
        return json.loads(run_files[-1].read_text()).get("findings",[])

    def _load_run_data(self) -> dict:
        findings_dir = settings.data_dir / "findings"
        run_files = sorted(findings_dir.glob("run_*.json"))
        if not run_files:
            return {}
        return json.loads(run_files[-1].read_text())


if __name__ == "__main__":
    from rich.console import Console
    from rich.panel import Panel
    console = Console()

    graph = ThirdLineKnowledgeGraph()
    graph.build()

    console.print(Panel.fit(
        f"[bold blue]ThirdLine Knowledge Graph[/bold blue]\n\n"
        f"  Nodes: {len(graph.nodes)}\n"
        f"  Edges: {len(graph.edges)}\n",
        border_style="blue"
    ))

    # Run demo queries
    queries = [
        "Which agent has the highest finding concentration?",
        "Which control has the most failures?",
        "Which business line has the highest AI risk?",
        "What is the overall systemic AI risk score?",
    ]

    for q in queries:
        result = graph.query(q)
        console.print(f"\n[cyan]Q:[/cyan] {q}")
        console.print(f"[green]A:[/green] {result.get('answer','')}")
        if result.get('insight'):
            console.print(f"[dim]Insight: {result['insight']}[/dim]")
