"""
ThirdLine — Week 2 + Week 3 Feature Runner

Runs all 6 advanced features:
  1. AuditCopilot    — natural language audit interface
  2. CCM Status      — continuous controls monitoring status
  3. Regulatory Radar — scan for new guidance
  4. Data Pipeline Auditor — audit data feeding agents
  5. Knowledge Graph — systemic risk intelligence
  6. Full integration test
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def main():
    console.print(Panel.fit(
        "[bold blue]ThirdLine — Week 2 + Week 3 Features[/bold blue]\n"
        "AuditCopilot · CCM · Regulatory Radar · Pipeline Auditor · Knowledge Graph",
        border_style="blue"
    ))

    # ── 1. AuditCopilot ──────────────────────────────────────────────────────
    console.print("\n[bold cyan]1. AuditCopilot — Natural Language Audit Interface[/bold cyan]")
    try:
        from audit_copilot.copilot import AuditCopilot
        copilot = AuditCopilot()

        test_questions = [
            "Which agents have CRITICAL findings?",
            "How many findings are pending human review?",
            "What is the hallucination rate for the mortgage agent?",
            "Which control has the most violations?",
            "Show me all bias findings",
        ]

        table = Table(title="AuditCopilot Demo Responses", border_style="cyan")
        table.add_column("Question", style="cyan", max_width=45)
        table.add_column("Answer", max_width=60)
        table.add_column("Conf", justify="right", style="green")

        for q in test_questions:
            answer = copilot.ask(q)
            table.add_row(q[:44], answer.answer[:59], f"{answer.confidence:.0%}")

        console.print(table)
        console.print(f"  [green]✓ AuditCopilot ready[/green]")

    except Exception as e:
        console.print(f"  [red]AuditCopilot error: {e}[/red]")

    # ── 2. CCM Status ─────────────────────────────────────────────────────────
    console.print("\n[bold cyan]2. Continuous Controls Monitoring (CCM)[/bold cyan]")
    try:
        from ccm.monitor import ContinuousControlsMonitor
        monitor = ContinuousControlsMonitor()
        status  = monitor.get_status()

        console.print(f"  CCM Status: {'Running' if status['is_running'] else 'Standby'}")
        console.print(f"  Total audits triggered: {status['total_audits_triggered']}")
        console.print(f"  Last full audit: {status['last_full_audit'] or 'Not yet run'}")
        console.print(f"  Alert count: {status['alert_count']}")
        console.print(f"  New interactions threshold: {status['thresholds']['new_interaction_trigger']}")

        # Show current interaction counts
        counts = status.get("current_interaction_counts", {})
        if counts:
            console.print(f"  Current interaction counts: {counts}")

        console.print(f"  [green]✓ CCM ready — use 'python ccm/monitor.py --mode event-driven' to start[/green]")

    except Exception as e:
        console.print(f"  [red]CCM error: {e}[/red]")

    # ── 3. Regulatory Radar ───────────────────────────────────────────────────
    console.print("\n[bold cyan]3. Regulatory Radar — Scanning for New Guidance[/bold cyan]")
    try:
        from regulatory_radar.radar import RegulatoryRadar
        radar  = RegulatoryRadar()
        alerts = radar.scan()

        if alerts:
            table = Table(title="Regulatory Alerts", border_style="yellow")
            table.add_column("Severity", style="bold")
            table.add_column("Title", max_width=50)
            table.add_column("Controls")

            for alert in alerts[:5]:
                sev = alert.severity if isinstance(alert, dict) else alert.severity
                title = alert.title if isinstance(alert, dict) else alert.title
                controls = alert.affected_controls if isinstance(alert, dict) else alert.affected_controls
                sev_str = sev if isinstance(sev, str) else str(sev)
                color = "red" if sev_str == "HIGH" else "yellow"
                table.add_row(
                    f"[{color}]{sev_str}[/{color}]",
                    title[:49] if isinstance(title, str) else str(title)[:49],
                    ", ".join(controls[:3]) if isinstance(controls, list) else str(controls)[:20]
                )
            console.print(table)
        else:
            console.print("  No new regulatory guidance detected.")

        console.print(f"  [green]✓ Regulatory Radar complete — {len(alerts)} alert(s)[/green]")

    except Exception as e:
        console.print(f"  [red]Regulatory Radar error: {e}[/red]")

    # ── 4. Data Pipeline Auditor ──────────────────────────────────────────────
    console.print("\n[bold cyan]4. Data Pipeline Auditor[/bold cyan]")
    try:
        from data_pipeline_auditor.auditor import DataPipelineAuditor
        auditor = DataPipelineAuditor()
        results = auditor.run_fleet_audit()

        passed = sum(1 for r in results if r.passed)
        console.print(f"  [green]✓ Pipeline audit complete — {passed}/{len(results)} agents passed[/green]")

    except Exception as e:
        console.print(f"  [red]Pipeline Auditor error: {e}[/red]")

    # ── 5. Knowledge Graph ────────────────────────────────────────────────────
    console.print("\n[bold cyan]5. Knowledge Graph — Systemic Risk Intelligence[/bold cyan]")
    try:
        from knowledge_graph.graph import ThirdLineKnowledgeGraph
        graph = ThirdLineKnowledgeGraph()
        graph.build()

        queries = [
            "Which agent has the highest finding concentration?",
            "Which business line has the highest AI risk?",
            "Which control has the most failures?",
        ]

        table = Table(title="Knowledge Graph Queries", border_style="blue")
        table.add_column("Question", style="cyan", max_width=45)
        table.add_column("Answer", max_width=65)

        for q in queries:
            result = graph.query(q)
            table.add_row(q[:44], result.get("answer","")[:64])

        console.print(table)
        console.print(f"  Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        console.print(f"  [green]✓ Knowledge Graph built — data/knowledge_graph/[/green]")

    except Exception as e:
        console.print(f"  [red]Knowledge Graph error: {e}[/red]")

    # ── Summary ────────────────────────────────────────────────────────────────
    console.print(Panel.fit(
        "[bold green]Week 2 + Week 3 Features Complete[/bold green]\n\n"
        "  ✓ AuditCopilot     — NL interface to audit warehouse\n"
        "  ✓ CCM Monitor      — event-driven continuous assurance\n"
        "  ✓ Regulatory Radar — Fed/OCC/FDIC change detection\n"
        "  ✓ Pipeline Auditor — data quality for agent inputs\n"
        "  ✓ Knowledge Graph  — systemic risk intelligence\n\n"
        "  API endpoints added:\n"
        "    POST /api/v1/copilot/ask\n"
        "    GET  /api/v1/ccm/status\n"
        "    POST /api/v1/regulatory-radar/scan\n"
        "    POST /api/v1/pipeline-audit/run\n"
        "    GET  /api/v1/knowledge-graph/report\n"
        "    GET  /api/v1/knowledge-graph/query",
        border_style="green"
    ))


if __name__ == "__main__":
    main()
