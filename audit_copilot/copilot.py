"""
=============================================================================
ThirdLine — AuditCopilot
=============================================================================

FILE: audit_copilot/copilot.py

WHAT THIS DOES:
    Natural language interface to the ThirdLine audit warehouse.
    An auditor types a plain-English question. AuditCopilot:

    1. Uses GPT-4o-mini to translate the question into a structured query
       against ThirdLine's local data (findings, evaluations, interactions)
    2. Executes the query against the JSON data store
    3. Uses GPT-4o-mini to explain the results in plain English with citations
    4. Returns a structured AuditAnswer with question, query, results, explanation

    EXAMPLE QUESTIONS:
    "Which agents showed bias issues in the last audit run?"
    "How many CRITICAL findings are pending human review?"
    "What is the hallucination rate for the mortgage agent?"
    "Show me all findings mapped to CTRL-001"
    "Which agent has the most failures overall?"
    "Are there any prompt injection vulnerabilities?"

    DESIGN:
    - Works in LOCAL_MODE with JSON files (no BigQuery needed)
    - Falls back to structured search if LLM is not available
    - Every answer includes citations (finding IDs, interaction IDs)
    - Conversation history maintained for follow-up questions

HOW TO RUN:
    python audit_copilot/copilot.py
    OR: POST /api/v1/copilot/ask {"question": "..."}

INPUT:  Natural language question (str)
OUTPUT: AuditAnswer with explanation, citations, confidence
=============================================================================
"""

from __future__ import annotations

import json
import re
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
class AuditAnswer:
    """Structured response from AuditCopilot."""
    question:     str
    answer:       str
    confidence:   float          # 0.0–1.0
    citations:    list[str]      # finding_ids, agent_ids referenced
    data:         list[dict]     # raw data rows returned
    query_type:   str            # "finding" | "agent" | "metric" | "control"
    timestamp:    str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "question":   self.question,
            "answer":     self.answer,
            "confidence": self.confidence,
            "citations":  self.citations,
            "data":       self.data[:5],   # cap for API response
            "query_type": self.query_type,
            "timestamp":  self.timestamp,
        }


class AuditDataStore:
    """
    In-memory data store loaded from ThirdLine's local JSON files.
    In production this queries BigQuery directly.
    """

    def __init__(self):
        self._findings:     list[dict] = []
        self._queue:        list[dict] = []
        self._evaluations:  dict[str, list[dict]] = {}  # agent_id → eval results
        self._interactions: dict[str, list[dict]] = {}  # agent_id → interactions
        self._ledger:       list[dict] = []
        self._load()

    def _load(self):
        """Load all data from local JSON files."""
        findings_dir = settings.data_dir / "findings"

        # Load findings from latest run
        run_files = sorted(findings_dir.glob("run_*.json"))
        if run_files:
            run = json.loads(run_files[-1].read_text())
            self._findings = run.get("findings", [])

        # Load review queue
        queue_dir = findings_dir / "review_queue"
        if queue_dir.exists():
            for f in queue_dir.glob("*.json"):
                self._queue.append(json.loads(f.read_text()))

        # Load evaluations
        eval_dir = settings.data_dir / "evaluations"
        if eval_dir.exists():
            for agent_dir in eval_dir.iterdir():
                if agent_dir.is_dir():
                    self._evaluations[agent_dir.name] = []
                    for dim_file in agent_dir.glob("*_results.json"):
                        results = json.loads(dim_file.read_text())
                        for r in results:
                            r["_dimension_file"] = dim_file.stem.replace("_results","")
                        self._evaluations[agent_dir.name].extend(results)

        # Load ledger
        ledger_path = findings_dir / "audit_ledger.json"
        if ledger_path.exists():
            self._ledger = json.loads(ledger_path.read_text())

        logger.info("audit_datastore_loaded",
            findings=len(self._findings),
            queue_items=len(self._queue),
            agents_with_evals=len(self._evaluations),
            ledger_entries=len(self._ledger),
        )

    def search_findings(self, **filters) -> list[dict]:
        """Filter findings by any combination of fields."""
        results = self._findings
        for key, val in filters.items():
            if val is not None:
                results = [f for f in results if str(f.get(key,'')).lower() == str(val).lower()]
        return results

    def get_agent_summary(self, agent_id: str | None = None) -> list[dict]:
        """Summarise findings per agent."""
        agents = {}
        for f in self._findings:
            aid = f.get("agent_id","")
            if agent_id and aid != agent_id:
                continue
            if aid not in agents:
                agents[aid] = {"agent_id":aid,"findings":0,"critical":0,"high":0,"medium":0,"dimensions":[]}
            agents[aid]["findings"] += 1
            sev = f.get("severity","")
            if sev == "CRITICAL": agents[aid]["critical"] += 1
            elif sev == "HIGH":   agents[aid]["high"] += 1
            elif sev == "MEDIUM": agents[aid]["medium"] += 1
            dim = f.get("dimension")
            if dim and dim not in agents[aid]["dimensions"]:
                agents[aid]["dimensions"].append(dim)
        return list(agents.values())

    def get_dimension_stats(self, dimension: str | None = None) -> list[dict]:
        """Get evaluation stats per dimension."""
        stats: dict[str, dict] = {}
        for agent_id, results in self._evaluations.items():
            for r in results:
                dim = r.get("_dimension_file", r.get("dimension",""))
                if dimension and dim != dimension:
                    continue
                key = f"{agent_id}::{dim}"
                if key not in stats:
                    stats[key] = {"agent_id":agent_id,"dimension":dim,"total":0,"failures":0,"avg_score":0.0,"scores":[]}
                stats[key]["total"] += 1
                if not r.get("passed", True):
                    stats[key]["failures"] += 1
                stats[key]["scores"].append(r.get("score",0))
        # Compute averages
        for s in stats.values():
            if s["scores"]:
                s["avg_score"] = round(sum(s["scores"])/len(s["scores"]),3)
            del s["scores"]
        return list(stats.values())

    def pending_review_count(self) -> int:
        return sum(1 for q in self._queue if q.get("status") == "PENDING")

    def get_control_summary(self) -> list[dict]:
        """Summarise findings by control ID."""
        controls: dict[str, dict] = {}
        for f in self._findings:
            ctrl = f.get("control_id","UNKNOWN")
            if ctrl not in controls:
                controls[ctrl] = {"control_id":ctrl,"count":0,"severities":[],"agents":[]}
            controls[ctrl]["count"] += 1
            sev = f.get("severity")
            if sev: controls[ctrl]["severities"].append(sev)
            aid = f.get("agent_id","")
            if aid and aid not in controls[ctrl]["agents"]:
                controls[ctrl]["agents"].append(aid)
        return list(controls.values())


class AuditCopilot:
    """
    Natural language interface to the ThirdLine audit warehouse.

    Translates plain-English audit questions into structured queries,
    executes them against the data store, and explains results clearly.
    """

    def __init__(self):
        self._store = AuditDataStore()
        self._llm   = self._init_llm()
        self._history: list[dict] = []   # conversation history

    def _init_llm(self):
        """Initialise GPT-4o-mini for NL understanding and answer generation."""
        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if openai_key and openai_key not in ("","your-openai-api-key"):
            try:
                from openai import OpenAI
                return OpenAI(api_key=openai_key)
            except Exception as e:
                logger.warning("copilot_llm_init_failed", error=str(e))
        return None

    def ask(self, question: str) -> AuditAnswer:
        """
        Answer a natural language audit question.

        Args:
            question: Plain-English audit question

        Returns:
            AuditAnswer with explanation, data, and citations
        """
        logger.info("copilot_question", question=question[:100])

        # Step 1: Classify the question
        query_type, filters = self._classify_question(question)

        # Step 2: Execute the query
        data, citations = self._execute_query(query_type, filters, question)

        # Step 3: Generate the answer
        answer, confidence = self._generate_answer(question, query_type, data)

        result = AuditAnswer(
            question=question,
            answer=answer,
            confidence=confidence,
            citations=citations,
            data=data,
            query_type=query_type,
        )

        # Add to conversation history
        self._history.append({"q": question, "a": answer, "type": query_type})
        if len(self._history) > 10:
            self._history.pop(0)

        logger.info("copilot_answer", query_type=query_type, data_rows=len(data), confidence=confidence)
        return result

    def _classify_question(self, question: str) -> tuple[str, dict]:
        """
        Classify the question type and extract filters.
        Uses keyword matching as primary, LLM as enhancement.
        """
        q_lower = question.lower()
        filters: dict[str, Any] = {}

        # Severity filter
        for sev in ["critical","high","medium","low"]:
            if sev in q_lower:
                filters["severity"] = sev.upper()
                break

        # Agent filter
        agent_map = {
            "mortgage": "agt-mortgage-faq-001",
            "kyc":      "agt-kyc-summary-001",
            "lending":  "agt-lending-decision-001",
            "fx":       "agt-fx-posttrade-001",
            "compliance":"agt-compliance-qa-001",
        }
        for key, agent_id in agent_map.items():
            if key in q_lower:
                filters["agent_id"] = agent_id
                break

        # Dimension filter
        for dim in ["hallucination","bias","drift","robustness","reliability"]:
            if dim in q_lower:
                filters["dimension"] = dim
                break

        # Control filter
        ctrl_match = re.search(r"CTRL-0*(\d+)", question, re.IGNORECASE)
        if ctrl_match:
            filters["control_id"] = f"CTRL-{ctrl_match.group(1).zfill(3)}"

        # Question type classification
        if any(w in q_lower for w in ["pending","review","queue","waiting","approve"]):
            return "queue", filters
        if any(w in q_lower for w in ["ledger","approved","rejected","chain","hash"]):
            return "ledger", filters
        if any(w in q_lower for w in ["metric","f1","precision","recall","performance","score"]):
            return "metric", filters
        if any(w in q_lower for w in ["control","ctrl","regulatory","sr 26"]):
            return "control", filters
        if any(w in q_lower for w in ["agent","which agent","what agent","worst"]):
            return "agent", filters
        if any(w in q_lower for w in ["dimension","hallucination","bias","drift","robustness","reliability","rate"]):
            return "dimension", filters

        return "finding", filters

    def _execute_query(self, query_type: str, filters: dict, question: str) -> tuple[list[dict], list[str]]:
        """Execute the structured query and return (data, citations)."""
        data: list[dict] = []
        citations: list[str] = []

        if query_type == "finding":
            data = self._store.search_findings(**{k:v for k,v in filters.items() if k in ["severity","agent_id","dimension","control_id","status"]})
            citations = [d.get("finding_id","")[:18] for d in data[:5]]

        elif query_type == "agent":
            data = self._store.get_agent_summary(filters.get("agent_id"))
            # Sort by most findings
            data.sort(key=lambda x: x["findings"], reverse=True)
            citations = [d["agent_id"] for d in data[:3]]

        elif query_type == "dimension":
            data = self._store.get_dimension_stats(filters.get("dimension"))
            data.sort(key=lambda x: x["failures"], reverse=True)
            citations = [f"{d['agent_id']}::{d['dimension']}" for d in data[:3]]

        elif query_type == "queue":
            pending = [q for q in self._store._queue if q.get("status") == "PENDING"]
            if "severity" in filters:
                pending = [q for q in pending if q.get("severity") == filters["severity"]]
            data = pending
            citations = [d.get("finding_id","")[:18] for d in data[:5]]

        elif query_type == "control":
            data = self._store.get_control_summary()
            if "control_id" in filters:
                data = [d for d in data if d["control_id"] == filters["control_id"]]
            citations = [d["control_id"] for d in data[:5]]

        elif query_type == "ledger":
            data = self._store._ledger[-10:]   # last 10 entries
            citations = [d.get("finding_id","")[:18] for d in data[:5]]

        elif query_type == "metric":
            meta_path = settings.data_dir / "evaluations" / "meta_eval_results.json"
            if meta_path.exists():
                data = [json.loads(meta_path.read_text())]
            citations = ["meta_eval_results"]

        return data, [c for c in citations if c]

    def _generate_answer(self, question: str, query_type: str, data: list[dict]) -> tuple[str, float]:
        """Generate a plain-English answer from the query results."""
        if not data:
            return f"No data found matching your question: '{question}'. Try rephrasing or check if the audit pipeline has been run.", 0.5

        # Use LLM if available
        if self._llm:
            return self._llm_answer(question, query_type, data)

        # Deterministic fallback
        return self._deterministic_answer(question, query_type, data), 0.75

    def _llm_answer(self, question: str, query_type: str, data: list[dict]) -> tuple[str, float]:
        """Use GPT-4o-mini to generate a natural language answer."""
        data_summary = json.dumps(data[:5], indent=2, default=str)[:2000]

        # Build conversation context
        history_str = ""
        if self._history:
            history_str = "\n".join([f"Q: {h['q']}\nA: {h['a'][:100]}..." for h in self._history[-3:]])

        prompt = f"""You are AuditCopilot, an expert AI assistant for an internal audit team at a financial institution.
The auditor has asked: "{question}"

Here is the relevant data from the ThirdLine audit warehouse:
{data_summary}

{f"Recent conversation context:{chr(10)}{history_str}" if history_str else ""}

Answer the auditor's question directly and concisely in 2-3 sentences.
- Be specific — use actual numbers, agent names, finding IDs from the data
- Use professional audit language
- If there are critical issues, highlight them
- Do not make up data not present in the results above
- Format: plain prose, no bullet points, no markdown"""

        try:
            response = self._llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":"You are an expert AI auditor assistant. Answer concisely and professionally."},
                    {"role":"user","content":prompt}
                ],
                temperature=0.1,
                max_tokens=200,
            )
            answer = response.choices[0].message.content.strip()
            return answer, 0.90
        except Exception as e:
            logger.warning("copilot_llm_answer_failed", error=str(e))
            return self._deterministic_answer(question, query_type, data), 0.65

    def _deterministic_answer(self, question: str, query_type: str, data: list[dict]) -> str:
        """Rule-based fallback answer generator."""
        if query_type == "finding":
            sev_counts: dict[str, int] = {}
            for f in data:
                s = f.get("severity","UNKNOWN")
                sev_counts[s] = sev_counts.get(s,0) + 1
            critical = sev_counts.get("CRITICAL",0)
            high = sev_counts.get("HIGH",0)
            return (
                f"Found {len(data)} finding(s) matching your criteria. "
                f"{critical} CRITICAL, {high} HIGH severity. "
                f"Most recent: '{data[0].get('title','')}' on agent {data[0].get('agent_id','').replace('agt-','').replace('-001','')}."
            )
        elif query_type == "agent":
            worst = data[0] if data else {}
            return (
                f"The highest-risk agent is {worst.get('agent_id','').replace('agt-','').replace('-001','')} "
                f"with {worst.get('findings',0)} findings. "
                f"Dimensions affected: {', '.join(worst.get('dimensions',[]))}."
            )
        elif query_type == "queue":
            return f"There are {len(data)} finding(s) pending human review in the HITL queue."
        elif query_type == "metric":
            m = data[0] if data else {}
            return f"ThirdLine's current detection performance: F1={m.get('f1',0):.3f}, Precision={m.get('precision',0):.1%}, Recall={m.get('recall',0):.1%}."
        elif query_type == "dimension":
            worst = data[0] if data else {}
            return (
                f"The {worst.get('dimension','')} dimension has the most failures: "
                f"{worst.get('failures',0)} of {worst.get('total',0)} evaluations failed "
                f"on agent {worst.get('agent_id','').replace('agt-','').replace('-001','')}."
            )
        return f"Found {len(data)} result(s) for your query."


# ── Interactive REPL ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    copilot = AuditCopilot()

    console.print(Panel.fit(
        "[bold blue]AuditCopilot[/bold blue] — Natural Language Audit Interface\n"
        "[dim]Ask questions about your audit findings, agents, metrics, and controls.[/dim]\n\n"
        "Examples:\n"
        "  • Which agents have CRITICAL findings?\n"
        "  • How many findings are pending review?\n"
        "  • What is the hallucination rate for the mortgage agent?\n"
        "  • Show me all findings mapped to CTRL-001\n"
        "  • Which agent has the worst bias score?\n\n"
        "[dim]Type 'exit' to quit.[/dim]",
        border_style="blue"
    ))

    while True:
        try:
            question = input("\n[Auditor] ").strip()
            if question.lower() in ("exit","quit","q"):
                break
            if not question:
                continue

            answer = copilot.ask(question)

            console.print(f"\n[bold green][AuditCopilot][/bold green] {answer.answer}")
            console.print(f"[dim]Confidence: {answer.confidence:.0%} · Type: {answer.query_type} · {len(answer.data)} row(s) · Citations: {', '.join(answer.citations[:3])}[/dim]")

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
