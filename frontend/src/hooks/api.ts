// =============================================================================
// ThirdLine — API Client
// =============================================================================
// Single module for all HTTP calls to the FastAPI backend.
// Using fetch directly (no axios dependency) for simplicity.

import type { Agent, Finding, QueueItem, LedgerEntry, Metrics } from '../types'

const BASE = '/api/v1'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json()
}

async function post<T>(path: string, body: object): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json()
}

export const api = {
  getAgents:    ()                                      => get<Agent[]>('/agents'),
  getAgent:     (id: string)                            => get<Agent>(`/agents/${id}`),
  getFindings:  ()                                      => get<Finding[]>('/findings'),
  getQueue:     ()                                      => get<QueueItem[]>('/review-queue'),
  getLedger:    ()                                      => get<{ entries: LedgerEntry[]; chain_intact: boolean; total_entries: number }>('/ledger'),
  getMetrics:   ()                                      => get<Metrics>('/metrics'),
  approveItem:  (id: string, reviewer: string, comment: string) =>
                  post(`/review-queue/${id}/approve`, { reviewer, comment }),
  rejectItem:   (id: string, reviewer: string, comment: string) =>
                  post(`/review-queue/${id}/reject`, { reviewer, comment }),
}
