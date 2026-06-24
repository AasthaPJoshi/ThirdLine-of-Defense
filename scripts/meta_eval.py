"""
=============================================================================
ThirdLine — Meta-Evaluation Script (v2 — fixed agent ID matching)
=============================================================================

FILE: scripts/meta_eval.py

WHAT THIS FILE DOES:
    Computes ThirdLine's own detection performance against the known
    ground truth labels in ground_truth.json.

    FIX in v2: Ground truth keys use agent names ("mortgage-faq-agent")
    but findings use full agent_ids ("agt-mortgage-faq-001"). This version
    normalises both to the full agent_id before comparison.

    Metrics computed:
      - True Positive  (TP): finding raised AND defect was injected for that agent
      - False Positive (FP): finding raised for a dimension with NO injected defect
      - False Negative (FN): defect injected BUT ThirdLine raised no finding
      - Precision, Recall, F1

HOW TO RUN:
    python scripts/meta_eval.py

INPUT:  agents_under_audit/data/ground_truth.json
        data/findings/run_*.json
OUTPUT: data/evaluations/meta_eval_results.json
=============================================================================
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from config.settings import settings
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def load_ground_truth() -> dict:
    gt_path = Path("agents_under_audit/data/ground_truth.json")
    return json.loads(gt_path.read_text())


def load_findings() -> list[dict]:
    findings = []
    findings_dir = settings.data_dir / "findings"
    for f in sorted(findings_dir.glob("run_*.json")):
        data = json.loads(f.read_text())
        findings.extend(data.get("findings", []))
    return findings


def compute_metrics(gt: dict, findings: list[dict]) -> dict:
    """
    Compute per-agent detection metrics.

    Ground truth is keyed by agent name (e.g. "mortgage-faq-agent").
    Each entry has an agent_id field (e.g. "agt-mortgage-faq-001").
    Findings use the full agent_id.

    We build a lookup: full_agent_id → expected_defect_dimension.
    """
    # Build: full_agent_id → primary_defect
    agents_with_defects: dict[str, str] = {}
    for key, data in gt["agents"].items():
        agent_id = data["agent_id"]                # "agt-mortgage-faq-001"
        defect   = data["primary_defect"]          # "hallucination"
        agents_with_defects[agent_id] = defect

    # Build: full_agent_id → list of dimensions where findings were raised
    agents_with_findings: dict[str, list[str]] = {}
    for f in findings:
        aid = f["agent_id"]
        dim = f["dimension"]
        agents_with_findings.setdefault(aid, []).append(dim)

    # Score each agent
    per_agent = []
    for agent_id, expected_defect in agents_with_defects.items():
        found_dims = agents_with_findings.get(agent_id, [])
        detected   = expected_defect in found_dims

        per_agent.append({
            "agent_id":        agent_id,
            "expected_defect": expected_defect,
            "finding_dimensions": found_dims,
            "detected":        detected,
            "tp": 1 if detected else 0,
            "fn": 0 if detected else 1,
        })

    # False positives: findings for dimensions that are NOT the injected defect
    fp_count = 0
    for agent_id, found_dims in agents_with_findings.items():
        expected = agents_with_defects.get(agent_id, "")
        for dim in found_dims:
            if dim != expected:
                fp_count += 1

    tp = sum(r["tp"] for r in per_agent)
    fn = sum(r["fn"] for r in per_agent)
    fp = fp_count

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "per_agent":        per_agent,
        "tp": tp, "fp": fp, "fn": fn,
        "precision":        round(precision, 4),
        "recall":           round(recall,    4),
        "f1":               round(f1,        4),
        "agents_evaluated": len(per_agent),
        "agents_detected":  tp,
    }


def main():
    console.print("\n[bold blue]ThirdLine — Meta-Evaluation[/bold blue]\n")

    gt       = load_ground_truth()
    findings = load_findings()

    if not findings:
        console.print("[red]No findings found. Run scripts/run_audit.py first.[/red]")
        return

    metrics = compute_metrics(gt, findings)

    # Per-agent table
    table = Table(title="Per-Agent Detection Results", border_style="blue")
    table.add_column("Agent",            style="cyan")
    table.add_column("Expected Defect",  style="yellow")
    table.add_column("Dimensions Found")
    table.add_column("Detected?",        justify="center")

    for r in metrics["per_agent"]:
        detected = r["detected"]
        table.add_row(
            r["agent_id"].replace("agt-", "").replace("-001", ""),
            r["expected_defect"],
            ", ".join(r["finding_dimensions"]) or "none",
            "[green]✓ TP[/green]" if detected else "[red]✗ FN[/red]",
        )
    console.print(table)

    # False positive detail
    if metrics["fp"] > 0:
        console.print(
            f"\n[yellow]Note: {metrics['fp']} false positive finding(s) — "
            f"dimensions flagged beyond the primary injected defect. "
            f"(e.g. compliance-qa fired on both robustness + reliability)[/yellow]"
        )

    # Aggregate panel
    f1_color = "green" if metrics["f1"] >= 0.8 else "yellow" if metrics["f1"] >= 0.5 else "red"
    console.print(Panel.fit(
        f"[bold]ThirdLine Detection Performance[/bold]\n\n"
        f"  True Positives:   {metrics['tp']}\n"
        f"  False Positives:  {metrics['fp']}\n"
        f"  False Negatives:  {metrics['fn']}\n\n"
        f"  [bold {f1_color}]Precision: {metrics['precision']:.1%}[/bold {f1_color}]\n"
        f"  [bold {f1_color}]Recall:    {metrics['recall']:.1%}[/bold {f1_color}]\n"
        f"  [bold {f1_color}]F1 Score:  {metrics['f1']:.3f}[/bold {f1_color}]\n\n"
        f"  Agents evaluated: {metrics['agents_evaluated']}\n"
        f"  Defects detected: {metrics['agents_detected']} / {metrics['agents_evaluated']}",
        border_style=f1_color,
    ))

    # Save
    out_path = settings.data_dir / "evaluations" / "meta_eval_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metrics, indent=2, default=str))
    console.print(f"\n[dim]Saved → {out_path}[/dim]")
    console.print("\n[bold]These numbers go in your resume bullet and README.[/bold]")


if __name__ == "__main__":
    main()
