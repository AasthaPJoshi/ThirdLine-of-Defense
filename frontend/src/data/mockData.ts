import type { Agent, Finding, QueueItem, LedgerEntry, Metrics } from '../types'

export const mockAgents: Agent[] = [
  {
    agent_id: 'agt_001',
    name: 'Loan Underwriting Assistant',
    business_line: 'Consumer Lending',
    materiality_tier: 'Tier 1',
    interaction_count: 4820,
    finding_count: 3,
    highest_severity: 'HIGH',
    risk_color: 'amber',
    dimensions_failed: ['Fair Lending', 'Explainability'],
    last_audited: '2026-07-10T14:32:00Z',
  },
  {
    agent_id: 'agt_002',
    name: 'Fraud Triage Bot',
    business_line: 'Fraud Ops',
    materiality_tier: 'Tier 1',
    interaction_count: 12040,
    finding_count: 1,
    highest_severity: 'CRITICAL',
    risk_color: 'red',
    dimensions_failed: ['Data Privacy'],
    last_audited: '2026-07-11T09:15:00Z',
  },
  {
    agent_id: 'agt_003',
    name: 'Customer Support Copilot',
    business_line: 'Retail Banking',
    materiality_tier: 'Tier 2',
    interaction_count: 30211,
    finding_count: 0,
    highest_severity: null,
    risk_color: 'green',
    dimensions_failed: [],
    last_audited: '2026-07-12T18:00:00Z',
  },
]

export const mockFindings: Finding[] = [
  {
    finding_id: 'fnd_101',
    agent_id: 'agt_001',
    dimension: 'Fair Lending',
    severity: 'HIGH',
    title: 'Disparate impact detected in approval rate variance',
    status: 'PENDING_REVIEW',
    control_id: 'CTRL-014',
    failure_count: 6,
    avg_score: 0.62,
    drafted_at: '2026-07-10T14:35:00Z',
  },
  {
    finding_id: 'fnd_102',
    agent_id: 'agt_002',
    dimension: 'Data Privacy',
    severity: 'CRITICAL',
    title: 'PII exposed in unmasked chat transcript',
    status: 'PENDING',
    control_id: 'CTRL-007',
    failure_count: 2,
    avg_score: 0.41,
    drafted_at: '2026-07-11T09:20:00Z',
  },
]

export const mockQueue: QueueItem[] = [
  {
    queue_id: 'q_501',
    finding_id: 'fnd_101',
    agent_id: 'agt_001',
    severity: 'HIGH',
    title: 'Disparate impact detected in approval rate variance',
    dimension: 'Fair Lending',
    draft_text: 'Automated review flagged a statistically significant variance in approval rates across protected demographic groups. Recommend manual audit of underwriting weights.',
    control_id: 'CTRL-014',
    queued_at: '2026-07-10T14:40:00Z',
    sla_deadline: '2026-07-13T14:40:00Z',
    status: 'PENDING_REVIEW',
    assigned_to: 'Aastha Joshi',
  },
]

export const mockLedger: { entries: LedgerEntry[]; chain_intact: boolean; total_entries: number } = {
  entries: [
    {
      seq: 1,
      finding_id: 'fnd_101',
      agent_id: 'agt_001',
      event_type: 'FINDING_CREATED',
      actor: 'system',
      finding_hash: 'a1b2c3d4e5f6',
      chain_hash: '9f8e7d6c5b4a',
      event_ts: '2026-07-10T14:35:00Z',
    },
    {
      seq: 2,
      finding_id: 'fnd_102',
      agent_id: 'agt_002',
      event_type: 'FINDING_CREATED',
      actor: 'system',
      finding_hash: 'b2c3d4e5f6a1',
      chain_hash: '8e7d6c5b4a9f',
      event_ts: '2026-07-11T09:20:00Z',
    },
  ],
  chain_intact: true,
  total_entries: 2,
}

export const mockMetrics: Metrics = {
  f1: 0.909,
  precision: 0.92,
  recall: 0.90,
  true_positives: 46,
  false_positives: 4,
  false_negatives: 5,
  agents_evaluated: 3,
  agents_detected: 3,
  total_findings: 2,
  total_interactions: 47071,
  findings_by_severity: { CRITICAL: 1, HIGH: 1, MEDIUM: 0, LOW: 0 },
  ledger_intact: true,
  last_run_id: 'run_2026_07_11_demo',
}
