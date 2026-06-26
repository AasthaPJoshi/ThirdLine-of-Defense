"""
=============================================================================
ThirdLine — Data Pipeline Auditor
=============================================================================

FILE: data_pipeline_auditor/auditor.py

WHAT THIS DOES:
    Extends ThirdLine upstream — auditing the DATA that feeds AI agents,
    not just the agent outputs themselves.

    A biased agent often has a biased data pipeline upstream.
    A hallucinating agent often has stale or incomplete context.
    A drifting agent often has schema drift in its input data.

    ThirdLine now catches both the symptom (agent output failure)
    AND the root cause (data pipeline failure).

    AUDIT DIMENSIONS:
    1. Data Freshness      — is the context data current?
    2. Schema Drift        — have input field types/distributions changed?
    3. PII in Pipeline     — is PII appearing in data before it should be redacted?
    4. Completeness        — are required fields missing?
    5. Referential Integrity — do foreign keys resolve correctly?
    6. Statistical Anomaly — are value distributions normal?

    WHAT GETS AUDITED:
    - Interaction input payloads (prompt + context)
    - Retrieved context (RAG pipeline outputs)
    - Agent response metadata (tool calls, latency, token counts)

HOW TO RUN:
    python data_pipeline_auditor/auditor.py
    OR: POST /api/v1/pipeline-audit/run

OUTPUT:
    data/pipeline_audits/pipeline_audit_{timestamp}.json
=============================================================================
"""

from __future__ import annotations

import json
import re
import statistics
import uuid
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
class PipelineCheckResult:
    """Result of a single data pipeline check."""
    check_id:   str
    check_name: str
    dimension:  str
    agent_id:   str
    passed:     bool
    severity:   str        # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    score:      float      # 0.0–1.0
    details:    str
    evidence:   list[dict] = field(default_factory=list)


@dataclass
class PipelineAuditResult:
    """Complete data pipeline audit result for one agent."""
    audit_id:   str
    agent_id:   str
    timestamp:  str
    checks:     list[PipelineCheckResult]
    passed:     bool
    risk_level: str
    summary:    str

    def to_dict(self) -> dict:
        return {
            "audit_id":  self.audit_id,
            "agent_id":  self.agent_id,
            "timestamp": self.timestamp,
            "passed":    self.passed,
            "risk_level":self.risk_level,
            "summary":   self.summary,
            "checks":    [
                {"check_name":c.check_name,"dimension":c.dimension,
                 "passed":c.passed,"severity":c.severity,"score":c.score,"details":c.details}
                for c in self.checks
            ],
            "findings_count": sum(1 for c in self.checks if not c.passed),
        }


class DataPipelineAuditor:
    """
    Audits the data pipelines feeding ThirdLine's monitored agents.

    Runs 6 dimensions of data quality checks against the interaction
    payloads stored by the synthetic agent fleet.
    """

    # Expected schema for interaction records
    REQUIRED_FIELDS = [
        "interaction_id","agent_id","session_id","interaction_index",
        "interaction_ts","prompt_redacted","output_redacted",
        "input_tokens","output_tokens","latency_ms","is_injected_defect",
    ]

    # PII patterns (should not appear in data after redaction)
    PII_PATTERNS = {
        "ssn":         re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d[ -]?){15,16}\b"),
        "email":       re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    }

    def __init__(self):
        self._output_dir = settings.data_dir / "pipeline_audits"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run_fleet_audit(self) -> list[PipelineAuditResult]:
        """Run pipeline audit across all agents."""
        from rich.console import Console
        from rich.table import Table
        console = Console()
        console.print("\n[bold blue]ThirdLine — Data Pipeline Auditor[/bold blue]\n")

        results = []
        interactions_dir = settings.data_dir / "interactions"
        if not interactions_dir.exists():
            console.print("[yellow]No interaction data found. Run scripts/run_fleet.py first.[/yellow]")
            return []

        for agent_dir in sorted(interactions_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            agent_id = agent_dir.name
            console.print(f"  Auditing pipeline for [cyan]{agent_id}[/cyan]...")
            result = self.audit_agent_pipeline(agent_id)
            results.append(result)

        # Print summary table
        table = Table(title="Data Pipeline Audit Results", border_style="blue")
        table.add_column("Agent",    style="cyan")
        table.add_column("Checks",   justify="right")
        table.add_column("Passed",   justify="right", style="green")
        table.add_column("Failed",   justify="right", style="red")
        table.add_column("Risk",     justify="center")

        for r in results:
            passed = sum(1 for c in r.checks if c.passed)
            failed = len(r.checks) - passed
            color  = {"LOW":"green","MEDIUM":"yellow","HIGH":"red","CRITICAL":"bright_red"}.get(r.risk_level,"white")
            table.add_row(
                r.agent_id.replace("agt-","").replace("-001",""),
                str(len(r.checks)), str(passed), str(failed),
                f"[{color}]{r.risk_level}[/{color}]"
            )
        console.print(table)

        # Save combined report
        report_path = self._output_dir / f"pipeline_audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps([r.to_dict() for r in results], indent=2, default=str))
        console.print(f"\n  Report saved: {report_path}")
        return results

    def audit_agent_pipeline(self, agent_id: str) -> PipelineAuditResult:
        """Run all 6 pipeline checks for one agent."""
        interactions = self._load_interactions(agent_id)
        checks: list[PipelineCheckResult] = []

        if not interactions:
            return PipelineAuditResult(
                audit_id  = str(uuid.uuid4()),
                agent_id  = agent_id,
                timestamp = datetime.now(timezone.utc).isoformat(),
                checks    = [],
                passed    = False,
                risk_level= "HIGH",
                summary   = "No interactions found for this agent.",
            )

        # Run all 6 checks
        checks.append(self._check_completeness(agent_id, interactions))
        checks.append(self._check_freshness(agent_id, interactions))
        checks.append(self._check_schema_drift(agent_id, interactions))
        checks.append(self._check_pii_in_pipeline(agent_id, interactions))
        checks.append(self._check_statistical_anomaly(agent_id, interactions))
        checks.append(self._check_referential_integrity(agent_id, interactions))

        failed  = [c for c in checks if not c.passed]
        passed  = len(failed) == 0

        # Determine overall risk level
        if any(c.severity == "CRITICAL" for c in failed):
            risk_level = "CRITICAL"
        elif any(c.severity == "HIGH" for c in failed):
            risk_level = "HIGH"
        elif failed:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        summary = (
            f"Pipeline audit for {agent_id}: {len(checks)-len(failed)}/{len(checks)} checks passed. "
            + (f"Issues: {', '.join(c.check_name for c in failed)}." if failed else "All checks passed.")
        )

        result = PipelineAuditResult(
            audit_id   = str(uuid.uuid4()),
            agent_id   = agent_id,
            timestamp  = datetime.now(timezone.utc).isoformat(),
            checks     = checks,
            passed     = passed,
            risk_level = risk_level,
            summary    = summary,
        )

        # Save individual result
        out_path = self._output_dir / f"{agent_id}_pipeline.json"
        out_path.write_text(json.dumps(result.to_dict(), indent=2, default=str))

        return result

    # ── Check 1: Completeness ──────────────────────────────────────────────────
    def _check_completeness(self, agent_id: str, interactions: list[dict]) -> PipelineCheckResult:
        """Verify all required fields are present in every interaction."""
        missing_fields: dict[str, int] = {}
        for interaction in interactions:
            for field_name in self.REQUIRED_FIELDS:
                if field_name not in interaction or interaction[field_name] is None:
                    missing_fields[field_name] = missing_fields.get(field_name, 0) + 1

        total_checks = len(interactions) * len(self.REQUIRED_FIELDS)
        total_missing = sum(missing_fields.values())
        score = 1.0 - (total_missing / total_checks) if total_checks > 0 else 1.0
        passed = score >= 0.99   # < 1% missing fields

        return PipelineCheckResult(
            check_id  = str(uuid.uuid4()),
            check_name= "Field Completeness",
            dimension = "completeness",
            agent_id  = agent_id,
            passed    = passed,
            severity  = "HIGH" if not passed else "LOW",
            score     = round(score, 4),
            details   = (
                f"All {len(self.REQUIRED_FIELDS)} required fields present in all {len(interactions)} interactions."
                if passed else
                f"Missing fields detected: {missing_fields}. {total_missing} missing values across {len(interactions)} interactions."
            ),
        )

    # ── Check 2: Freshness ─────────────────────────────────────────────────────
    def _check_freshness(self, agent_id: str, interactions: list[dict]) -> PipelineCheckResult:
        """Check that interaction data is reasonably recent."""
        timestamps = []
        for i in interactions:
            ts_str = i.get("interaction_ts","")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z","+00:00"))
                    timestamps.append(ts)
                except Exception:
                    pass

        if not timestamps:
            return PipelineCheckResult(
                check_id="",check_name="Data Freshness",dimension="freshness",
                agent_id=agent_id,passed=False,severity="MEDIUM",score=0.0,
                details="No valid timestamps found in interaction data."
            )

        now = datetime.now(timezone.utc)
        most_recent = max(timestamps)
        # Make timestamps timezone-aware if needed
        if most_recent.tzinfo is None:
            most_recent = most_recent.replace(tzinfo=timezone.utc)
        age_hours = (now - most_recent).total_seconds() / 3600
        passed = age_hours < 72   # data should be < 72 hours old
        score  = max(0.0, 1.0 - age_hours / 168)   # decays over 1 week

        return PipelineCheckResult(
            check_id  = str(uuid.uuid4()),
            check_name= "Data Freshness",
            dimension = "freshness",
            agent_id  = agent_id,
            passed    = passed,
            severity  = "MEDIUM" if not passed else "LOW",
            score     = round(score, 4),
            details   = f"Most recent interaction: {age_hours:.1f} hours ago. {'Within freshness threshold.' if passed else 'Data may be stale — consider re-running fleet.'}"
        )

    # ── Check 3: Schema Drift ──────────────────────────────────────────────────
    def _check_schema_drift(self, agent_id: str, interactions: list[dict]) -> PipelineCheckResult:
        """Detect schema drift — field types or presence changing over time."""
        if len(interactions) < 10:
            return PipelineCheckResult(
                check_id="",check_name="Schema Drift",dimension="schema",
                agent_id=agent_id,passed=True,severity="LOW",score=1.0,
                details="Insufficient data for schema drift detection (< 10 interactions)."
            )

        # Split into early / late windows
        early = interactions[:len(interactions)//3]
        late  = interactions[-len(interactions)//3:]

        # Check that same fields present in both windows
        early_keys = set()
        for i in early:
            early_keys.update(i.keys())
        late_keys  = set()
        for i in late:
            late_keys.update(i.keys())

        added   = late_keys - early_keys
        removed = early_keys - late_keys

        # Check output token distribution drift
        early_tokens = [i.get("output_tokens",0) for i in early]
        late_tokens  = [i.get("output_tokens",0) for i in late]

        mean_early = statistics.mean(early_tokens) if early_tokens else 0
        mean_late  = statistics.mean(late_tokens)  if late_tokens  else 0
        token_drift = abs(mean_late - mean_early) / (mean_early + 1)

        schema_stable = not added and not removed
        token_stable  = token_drift < 0.5
        passed = schema_stable and token_stable
        score  = (1.0 if schema_stable else 0.5) * (1.0 if token_stable else 0.7)

        return PipelineCheckResult(
            check_id  = str(uuid.uuid4()),
            check_name= "Schema Drift",
            dimension = "schema",
            agent_id  = agent_id,
            passed    = passed,
            severity  = "MEDIUM" if not passed else "LOW",
            score     = round(score, 4),
            details   = (
                f"Schema stable. Token distribution drift: {token_drift:.1%} "
                f"(early avg: {mean_early:.0f}, late avg: {mean_late:.0f} tokens)."
                if passed else
                f"Schema changes detected. Added fields: {added}. Removed: {removed}. "
                f"Token drift: {token_drift:.1%}."
            )
        )

    # ── Check 4: PII in Pipeline ───────────────────────────────────────────────
    def _check_pii_in_pipeline(self, agent_id: str, interactions: list[dict]) -> PipelineCheckResult:
        """Detect PII that should have been redacted but appears in data."""
        pii_found: list[dict] = []

        for i in interactions:
            # Check prompt_redacted — PII should be gone after scrubbing
            text_to_check = i.get("prompt_redacted","") + " " + i.get("output_redacted","")
            for pii_type, pattern in self.PII_PATTERNS.items():
                if pattern.search(text_to_check):
                    pii_found.append({
                        "interaction_id": i.get("interaction_id","")[:18],
                        "pii_type": pii_type,
                        "field": "redacted_fields",
                    })

        passed = len(pii_found) == 0
        score  = 1.0 if passed else max(0.0, 1.0 - len(pii_found) * 0.1)

        return PipelineCheckResult(
            check_id  = str(uuid.uuid4()),
            check_name= "PII in Pipeline",
            dimension = "privacy",
            agent_id  = agent_id,
            passed    = passed,
            severity  = "CRITICAL" if not passed else "LOW",
            score     = round(score, 4),
            details   = (
                "No PII detected in pipeline data. Redaction working correctly."
                if passed else
                f"CRITICAL: PII detected in {len(pii_found)} interaction(s) after redaction. "
                f"Types found: {set(p['pii_type'] for p in pii_found)}. Immediate remediation required."
            ),
            evidence  = pii_found[:3],
        )

    # ── Check 5: Statistical Anomaly ───────────────────────────────────────────
    def _check_statistical_anomaly(self, agent_id: str, interactions: list[dict]) -> PipelineCheckResult:
        """Detect anomalous patterns in interaction statistics."""
        latencies     = [i.get("latency_ms", 0) for i in interactions if i.get("latency_ms")]
        token_counts  = [i.get("total_tokens", 0) for i in interactions if i.get("total_tokens")]

        anomalies = []

        if latencies and len(latencies) > 5:
            mean_lat = statistics.mean(latencies)
            stdev_lat = statistics.stdev(latencies) if len(latencies) > 1 else 0
            # Flag interactions with latency > mean + 3σ
            outliers = [l for l in latencies if l > mean_lat + 3 * stdev_lat and stdev_lat > 0]
            if outliers:
                anomalies.append(f"Latency outliers: {len(outliers)} interactions > 3σ (mean {mean_lat:.0f}ms)")

        # Check for zero-latency interactions (may indicate mock/cached responses)
        zero_latency = sum(1 for l in latencies if l == 0)
        if zero_latency > len(latencies) * 0.5:
            anomalies.append(f"{zero_latency}/{len(latencies)} interactions have zero latency — possible mock data")

        passed = len(anomalies) == 0
        score  = 1.0 if passed else 0.75   # soft failure — informational

        return PipelineCheckResult(
            check_id  = str(uuid.uuid4()),
            check_name= "Statistical Anomaly",
            dimension = "statistics",
            agent_id  = agent_id,
            passed    = passed,
            severity  = "LOW" if not passed else "LOW",
            score     = round(score, 4),
            details   = (
                f"No statistical anomalies. Mean latency: {statistics.mean(latencies):.0f}ms."
                if (passed and latencies) else
                f"Anomalies detected: {'; '.join(anomalies)}"
                if anomalies else "Insufficient latency data."
            )
        )

    # ── Check 6: Referential Integrity ─────────────────────────────────────────
    def _check_referential_integrity(self, agent_id: str, interactions: list[dict]) -> PipelineCheckResult:
        """Verify that interaction IDs are unique and agent_id is consistent."""
        ids = [i.get("interaction_id") for i in interactions]
        unique_ids   = len(set(ids))
        duplicate_ids= len(ids) - unique_ids

        # Check agent_id consistency
        agent_ids_found = set(i.get("agent_id","") for i in interactions)
        consistent = len(agent_ids_found) == 1 and agent_id in agent_ids_found

        # Check index is sequential
        indices = sorted([i.get("interaction_index",0) for i in interactions])
        expected = list(range(len(indices)))
        sequential = indices == expected

        passed = duplicate_ids == 0 and consistent
        score  = 1.0 if passed else 0.5

        return PipelineCheckResult(
            check_id  = str(uuid.uuid4()),
            check_name= "Referential Integrity",
            dimension = "integrity",
            agent_id  = agent_id,
            passed    = passed,
            severity  = "HIGH" if not passed else "LOW",
            score     = round(score, 4),
            details   = (
                f"Referential integrity OK. {unique_ids} unique interaction IDs. Sequential index: {sequential}."
                if passed else
                f"Integrity issues: {duplicate_ids} duplicate IDs. Agent ID consistent: {consistent}. "
                f"IDs found: {agent_ids_found}."
            )
        )

    def _load_interactions(self, agent_id: str) -> list[dict]:
        agent_dir = settings.data_dir / "interactions" / agent_id
        if not agent_dir.exists():
            return []
        interactions = []
        for f in agent_dir.glob("*.json"):
            try:
                interactions.append(json.loads(f.read_text()))
            except Exception:
                pass
        return sorted(interactions, key=lambda x: x.get("interaction_index",0))


if __name__ == "__main__":
    auditor = DataPipelineAuditor()
    auditor.run_fleet_audit()
