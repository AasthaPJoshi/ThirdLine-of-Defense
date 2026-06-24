// =============================================================================
// ThirdLine — TypeScript Type Definitions
// =============================================================================
// Maps 1:1 to the Pydantic models in api/main.py

export type RiskColor = 'red' | 'amber' | 'green' | 'gray'
export type Severity  = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
export type Status    = 'PENDING' | 'APPROVED' | 'REJECTED' | 'PENDING_REVIEW'

export interface Agent {
  agent_id: string
  name: string
  business_line: string
  materiality_tier: string
  interaction_count: number
  finding_count: number
  highest_severity: Severity | null
  risk_color: RiskColor
  dimensions_failed: string[]
  last_audited: string | null
}

export interface Finding {
  finding_id: string
  agent_id: string
  dimension: string
  severity: Severity
  title: string
  status: Status
  control_id: string | null
  failure_count: number
  avg_score: number
  drafted_at: string
}

export interface QueueItem {
  queue_id: string
  finding_id: string
  agent_id: string
  severity: Severity
  title: string
  dimension: string
  draft_text: string
  control_id: string | null
  queued_at: string
  sla_deadline: string | null
  status: Status
  assigned_to: string | null
}

export interface LedgerEntry {
  seq: number
  finding_id: string
  agent_id: string
  event_type: string
  actor: string
  finding_hash: string
  chain_hash: string
  event_ts: string
}

export interface Metrics {
  f1: number
  precision: number
  recall: number
  true_positives: number
  false_positives: number
  false_negatives: number
  agents_evaluated: number
  agents_detected: number
  total_findings: number
  total_interactions: number
  findings_by_severity: Record<string, number>
  ledger_intact: boolean
  last_run_id: string | null
}
