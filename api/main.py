"""
=============================================================================
ThirdLine — FastAPI Backend
=============================================================================

FILE: api/main.py

WHAT THIS FILE DOES:
    Production-grade REST API for ThirdLine. Exposes all data from the
    audit pipeline to the React dashboard and external consumers.

    ENDPOINTS:
    ┌─────────────────────────────────┬────────────────────────────────────┐
    │ Endpoint                        │ Purpose                            │
    ├─────────────────────────────────┼────────────────────────────────────┤
    │ GET  /health                    │ Health check                       │
    │ GET  /api/v1/agents             │ Fleet inventory with risk status   │
    │ GET  /api/v1/agents/{id}        │ Single agent detail + scorecard    │
    │ GET  /api/v1/findings           │ All findings (filterable)          │
    │ GET  /api/v1/review-queue       │ HITL queue — pending items         │
    │ POST /api/v1/review-queue/{id}/approve  │ Human approves finding    │
    │ POST /api/v1/review-queue/{id}/reject   │ Human rejects finding     │
    │ GET  /api/v1/ledger             │ Audit ledger + chain verification  │
    │ GET  /api/v1/metrics            │ F1, precision, recall, summary     │
    └─────────────────────────────────┴────────────────────────────────────┘

    DESIGN DECISIONS:
    - No database required for LOCAL_MODE — reads from data/ JSON files
    - CORS enabled for React dev server (localhost:5173)
    - Pydantic response models for type safety
    - Every approval/rejection updates the ledger atomically
    - Human reviewer identity tracked in every action

HOW TO RUN:
    uvicorn api.main:app --reload --port 8000
    OR: python scripts/run_api.py

INPUT:  data/findings/, data/evaluations/, data/interactions/
OUTPUT: JSON responses consumed by React dashboard
=============================================================================
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from config.settings import settings

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ThirdLine API",
    description="Agentic AI Audit & Governance Platform — REST API",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # CRA fallback
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic response models ──────────────────────────────────────────────────
class AgentSummary(BaseModel):
    agent_id: str
    name: str
    business_line: str
    materiality_tier: str
    interaction_count: int
    finding_count: int
    highest_severity: Optional[str]
    risk_color: str          # "red" | "amber" | "green" | "gray"
    dimensions_failed: list[str]
    last_audited: Optional[str]


class FindingSummary(BaseModel):
    finding_id: str
    agent_id: str
    dimension: str
    severity: str
    title: str
    status: str
    control_id: Optional[str]
    failure_count: int
    avg_score: float
    drafted_at: str


class QueueItem(BaseModel):
    queue_id: str
    finding_id: str
    agent_id: str
    severity: str
    title: str
    dimension: str
    draft_text: str
    control_id: Optional[str]
    queued_at: str
    sla_deadline: Optional[str]
    status: str
    assigned_to: Optional[str]


class ReviewAction(BaseModel):
    reviewer: str = "auditor"
    comment: str = ""


class LedgerEntry(BaseModel):
    seq: int
    finding_id: str
    agent_id: str
    event_type: str
    actor: str
    finding_hash: str
    chain_hash: str
    event_ts: str


class MetricsResponse(BaseModel):
    f1: float
    precision: float
    recall: float
    true_positives: int
    false_positives: int
    false_negatives: int
    agents_evaluated: int
    agents_detected: int
    total_findings: int
    total_interactions: int
    findings_by_severity: dict[str, int]
    ledger_intact: bool
    last_run_id: Optional[str]


# ── Data access helpers ────────────────────────────────────────────────────────
def _load_run_data() -> dict[str, Any]:
    """Load the most recent audit run JSON."""
    findings_dir = settings.data_dir / "findings"
    run_files = sorted(findings_dir.glob("run_*.json"))
    if not run_files:
        return {"findings": [], "review_queue": [], "run_id": None}
    latest = run_files[-1]
    return json.loads(latest.read_text())


def _load_queue() -> list[dict]:
    """Load all items from the review queue directory."""
    queue_dir = settings.data_dir / "findings" / "review_queue"
    items = []
    if queue_dir.exists():
        for f in sorted(queue_dir.glob("*.json")):
            items.append(json.loads(f.read_text()))
    return items


def _load_ledger() -> list[dict]:
    """Load the audit ledger."""
    ledger_path = settings.data_dir / "findings" / "audit_ledger.json"
    if not ledger_path.exists():
        return []
    return json.loads(ledger_path.read_text())


def _save_ledger(entries: list[dict]) -> None:
    ledger_path = settings.data_dir / "findings" / "audit_ledger.json"
    ledger_path.write_text(json.dumps(entries, indent=2, default=str))


def _verify_ledger(entries: list[dict]) -> bool:
    """Verify hash chain integrity. Returns True if intact."""
    for i, entry in enumerate(entries):
        genesis_hash = hashlib.sha256(b"GENESIS").hexdigest()
        prev = entries[i - 1]["chain_hash"] if i > 0 else genesis_hash
        expected = hashlib.sha256(
            (prev + entry["finding_hash"]).encode()
        ).hexdigest()
        if entry["chain_hash"] != expected:
            return False
    return True


def _append_ledger(finding_id: str, agent_id: str, event_type: str, actor: str) -> dict:
    """Append an event to the audit ledger and return the entry."""
    entries = _load_ledger()
    seq = len(entries)

    content = json.dumps(
        {"finding_id": finding_id, "event_type": event_type,
         "actor": actor, "ts": datetime.now(timezone.utc).isoformat()},
        sort_keys=True
    )
    finding_hash = hashlib.sha256(content.encode()).hexdigest()
    genesis_hash = hashlib.sha256(b"GENESIS").hexdigest()
    prev_hash = entries[-1]["chain_hash"] if entries else genesis_hash
    chain_hash = hashlib.sha256((prev_hash + finding_hash).encode()).hexdigest()

    entry = {
        "seq": seq,
        "finding_id": finding_id,
        "agent_id": agent_id,
        "event_type": event_type,
        "actor": actor,
        "finding_hash": finding_hash,
        "prev_hash": prev_hash,
        "chain_hash": chain_hash,
        "event_ts": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    _save_ledger(entries)
    return entry


def _get_risk_color(findings: list[dict]) -> str:
    if not findings:
        return "green"
    severities = [f.get("severity", "") for f in findings]
    if "CRITICAL" in severities:
        return "red"
    if "HIGH" in severities:
        return "amber"
    if "MEDIUM" in severities:
        return "amber"
    return "green"


def _load_meta_eval() -> dict:
    meta_path = settings.data_dir / "evaluations" / "meta_eval_results.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return {"f1": 0.0, "precision": 0.0, "recall": 0.0,
            "tp": 0, "fp": 0, "fn": 0,
            "agents_evaluated": 0, "agents_detected": 0}


# ── Fleet inventory (static definition matches orchestrator) ──────────────────
FLEET_REGISTRY = [
    {"agent_id": "agt-mortgage-faq-001",     "name": "mortgage-faq-agent",     "business_line": "Consumer Lending",              "materiality_tier": "HIGH"},
    {"agent_id": "agt-kyc-summary-001",      "name": "kyc-summary-agent",      "business_line": "Compliance",                    "materiality_tier": "HIGH"},
    {"agent_id": "agt-lending-decision-001", "name": "lending-decision-agent", "business_line": "Consumer Lending",              "materiality_tier": "HIGH"},
    {"agent_id": "agt-fx-posttrade-001",     "name": "fx-posttrade-agent",     "business_line": "Corporate & Investment Banking", "materiality_tier": "MEDIUM"},
    {"agent_id": "agt-compliance-qa-001",    "name": "compliance-qa-agent",    "business_line": "Compliance",                    "materiality_tier": "HIGH"},
]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check — used by CI and load balancer."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.APP_ENV,
    }


@app.get("/api/v1/agents", response_model=list[AgentSummary])
def get_agents():
    """
    Return full fleet inventory with risk status for each agent.
    Drives the fleet heat-map on the dashboard.
    """
    run = _load_run_data()
    findings = run.get("findings", [])

    # Group findings by agent
    findings_by_agent: dict[str, list[dict]] = {}
    for f in findings:
        findings_by_agent.setdefault(f["agent_id"], []).append(f)

    summaries = []
    for agent in FLEET_REGISTRY:
        aid = agent["agent_id"]
        agent_findings = findings_by_agent.get(aid, [])

        # Count interactions
        interaction_dir = settings.data_dir / "interactions" / aid
        interaction_count = len(list(interaction_dir.glob("*.json"))) if interaction_dir.exists() else 0

        severities = [f.get("severity") for f in agent_findings]
        highest = None
        for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if s in severities:
                highest = s
                break

        summaries.append(AgentSummary(
            agent_id=aid,
            name=agent["name"],
            business_line=agent["business_line"],
            materiality_tier=agent["materiality_tier"],
            interaction_count=interaction_count,
            finding_count=len(agent_findings),
            highest_severity=highest,
            risk_color=_get_risk_color(agent_findings),
            dimensions_failed=[f["dimension"] for f in agent_findings],
            last_audited=run.get("completed_at"),
        ))

    return summaries


@app.get("/api/v1/agents/{agent_id}")
def get_agent_detail(agent_id: str):
    """
    Return detailed scorecard for a single agent.
    Includes per-dimension scores and all findings.
    """
    agent_info = next((a for a in FLEET_REGISTRY if a["agent_id"] == agent_id), None)
    if not agent_info:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    run = _load_run_data()
    findings = [f for f in run.get("findings", []) if f["agent_id"] == agent_id]

    # Load per-dimension eval results
    eval_dir = settings.data_dir / "evaluations" / agent_id
    dimension_scores = {}
    if eval_dir.exists():
        for dim_file in eval_dir.glob("*_results.json"):
            dim = dim_file.stem.replace("_results", "")
            results = json.loads(dim_file.read_text())
            if results:
                scores = [r.get("score", 0) for r in results]
                passed = sum(1 for r in results if r.get("passed", True))
                dimension_scores[dim] = {
                    "avg_score": round(sum(scores) / len(scores), 3),
                    "min_score": round(min(scores), 3),
                    "pass_rate": round(passed / len(results), 3),
                    "total": len(results),
                    "failures": len(results) - passed,
                }

    return {
        **agent_info,
        "findings": findings,
        "dimension_scores": dimension_scores,
        "finding_count": len(findings),
        "risk_color": _get_risk_color(findings),
    }


@app.get("/api/v1/findings", response_model=list[FindingSummary])
def get_findings(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    dimension: Optional[str] = Query(None, description="Filter by dimension"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Return all audit findings with optional filters.
    Drives the findings list on the dashboard.
    """
    run = _load_run_data()
    findings = run.get("findings", [])

    if severity:
        findings = [f for f in findings if f.get("severity") == severity.upper()]
    if dimension:
        findings = [f for f in findings if f.get("dimension") == dimension.lower()]
    if status:
        findings = [f for f in findings if f.get("status") == status.upper()]

    return [
        FindingSummary(
            finding_id=f["finding_id"],
            agent_id=f["agent_id"],
            dimension=f["dimension"],
            severity=f["severity"],
            title=f["title"],
            status=f.get("status", "PENDING_REVIEW"),
            control_id=f.get("control_id"),
            failure_count=f.get("failure_count", 0),
            avg_score=f.get("avg_score", 0.0),
            drafted_at=f.get("drafted_at", ""),
        )
        for f in findings
    ]


@app.get("/api/v1/review-queue", response_model=list[QueueItem])
def get_review_queue(status: Optional[str] = Query(None)):
    """
    Return the human review queue.
    Drives the HITL review panel on the dashboard.
    """
    items = _load_queue()
    if status:
        items = [i for i in items if i.get("status") == status.upper()]
    # Sort: CRITICAL first, then by queued_at
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    items.sort(key=lambda x: (severity_order.get(x.get("severity", "LOW"), 9), x.get("queued_at", "")))
    return [QueueItem(**i) for i in items]


@app.post("/api/v1/review-queue/{queue_id}/approve")
def approve_finding(queue_id: str, action: ReviewAction):
    """
    Human auditor approves a finding.
    Updates queue status, appends FINDING_APPROVED to ledger.
    This is the HITL gate — no finding is finalised without this call.
    """
    queue_dir = settings.data_dir / "findings" / "review_queue"
    queue_file = queue_dir / f"{queue_id}.json"

    if not queue_file.exists():
        raise HTTPException(status_code=404, detail=f"Queue item {queue_id} not found")

    item = json.loads(queue_file.read_text())
    if item["status"] != "PENDING":
        raise HTTPException(
            status_code=409,
            detail=f"Item already actioned with status: {item['status']}"
        )

    now = datetime.now(timezone.utc).isoformat()
    item["status"] = "APPROVED"
    item["actioned_at"] = now
    item["actioned_by"] = action.reviewer
    item["reviewer_comment"] = action.comment
    queue_file.write_text(json.dumps(item, indent=2, default=str))

    # Append to audit ledger
    ledger_entry = _append_ledger(
        finding_id=item["finding_id"],
        agent_id=item["agent_id"],
        event_type="FINDING_APPROVED",
        actor=action.reviewer,
    )

    return {
        "status": "approved",
        "queue_id": queue_id,
        "finding_id": item["finding_id"],
        "approved_by": action.reviewer,
        "approved_at": now,
        "ledger_seq": ledger_entry["seq"],
        "ledger_hash": ledger_entry["chain_hash"],
        "message": "Finding approved and recorded in audit ledger.",
    }


@app.post("/api/v1/review-queue/{queue_id}/reject")
def reject_finding(queue_id: str, action: ReviewAction):
    """
    Human auditor rejects a finding (e.g. false positive).
    Updates queue status, appends FINDING_REJECTED to ledger.
    """
    queue_dir = settings.data_dir / "findings" / "review_queue"
    queue_file = queue_dir / f"{queue_id}.json"

    if not queue_file.exists():
        raise HTTPException(status_code=404, detail=f"Queue item {queue_id} not found")

    item = json.loads(queue_file.read_text())
    if item["status"] != "PENDING":
        raise HTTPException(
            status_code=409,
            detail=f"Item already actioned with status: {item['status']}"
        )

    now = datetime.now(timezone.utc).isoformat()
    item["status"] = "REJECTED"
    item["actioned_at"] = now
    item["actioned_by"] = action.reviewer
    item["reviewer_comment"] = action.comment
    queue_file.write_text(json.dumps(item, indent=2, default=str))

    ledger_entry = _append_ledger(
        finding_id=item["finding_id"],
        agent_id=item["agent_id"],
        event_type="FINDING_REJECTED",
        actor=action.reviewer,
    )

    return {
        "status": "rejected",
        "queue_id": queue_id,
        "finding_id": item["finding_id"],
        "rejected_by": action.reviewer,
        "rejected_at": now,
        "ledger_seq": ledger_entry["seq"],
        "ledger_hash": ledger_entry["chain_hash"],
        "message": "Finding rejected and recorded in audit ledger.",
    }


@app.get("/api/v1/ledger")
def get_ledger():
    """
    Return the full audit ledger with chain integrity status.
    Drives the ledger view on the dashboard.
    """
    entries = _load_ledger()
    is_valid = _verify_ledger(entries)
    return {
        "entries": entries,
        "total_entries": len(entries),
        "chain_intact": is_valid,
        "integrity_status": "INTACT" if is_valid else "BROKEN",
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/metrics", response_model=MetricsResponse)
def get_metrics():
    """
    Return ThirdLine's detection performance metrics.
    Drives the metrics panel on the dashboard.
    These are the numbers that go in the resume.
    """
    meta = _load_meta_eval()
    run = _load_run_data()
    findings = run.get("findings", [])
    ledger = _load_ledger()

    severity_counts: dict[str, int] = {}
    for f in findings:
        s = f.get("severity", "UNKNOWN")
        severity_counts[s] = severity_counts.get(s, 0) + 1

    # Count total interactions across all agents
    total_interactions = 0
    interactions_root = settings.data_dir / "interactions"
    if interactions_root.exists():
        for agent_dir in interactions_root.iterdir():
            if agent_dir.is_dir():
                total_interactions += len(list(agent_dir.glob("*.json")))

    return MetricsResponse(
        f1=meta.get("f1", 0.0),
        precision=meta.get("precision", 0.0),
        recall=meta.get("recall", 0.0),
        true_positives=meta.get("tp", 0),
        false_positives=meta.get("fp", 0),
        false_negatives=meta.get("fn", 0),
        agents_evaluated=meta.get("agents_evaluated", 0),
        agents_detected=meta.get("agents_detected", 0),
        total_findings=len(findings),
        total_interactions=total_interactions,
        findings_by_severity=severity_counts,
        ledger_intact=_verify_ledger(ledger),
        last_run_id=run.get("run_id"),
    )
