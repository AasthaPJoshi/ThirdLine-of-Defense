// =============================================================================
// ThirdLine — API Client
// =============================================================================
// Single module for all HTTP calls to the FastAPI backend.
// Falls back to static mock data when VITE_USE_MOCK_DATA=true (used for the
// live Vercel demo, which has no backend deployed). Clone locally and run
// the backend to see live data.
import type { Agent, Finding, QueueItem, LedgerEntry, Metrics } from '../types'
import {
  mockAgents,
  mockFindings,
  mockQueue,
  mockLedger,
  mockMetrics,
} from '../data/mockData'

const BASE = '/api/v1'
const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true'

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
  getAgents: () =>
    USE_MOCK ? Promise.resolve(mockAgents) : get<Agent[]>('/agents'),

  getAgent: (id: string) =>
    USE_MOCK
      ? Promise.resolve(mockAgents.find(a => a.agent_id === id) as Agent)
      : get<Agent>(`/agents/${id}`),

  getFindings: () =>
    USE_MOCK ? Promise.resolve(mockFindings) : get<Finding[]>('/findings'),

  getQueue: () =>
    USE_MOCK ? Promise.resolve(mockQueue) : get<QueueItem[]>('/review-queue'),

  getLedger: () =>
    USE_MOCK
      ? Promise.resolve(mockLedger)
      : get<{ entries: LedgerEntry[]; chain_intact: boolean; total_entries: number }>('/ledger'),

  getMetrics: () =>
    USE_MOCK ? Promise.resolve(mockMetrics) : get<Metrics>('/metrics'),

  approveItem: (id: string, reviewer: string, comment: string) =>
    USE_MOCK
      ? Promise.resolve({ status: 'APPROVED', reviewer, comment, note: 'Demo mode: not persisted' })
      : post(`/review-queue/${id}/approve`, { reviewer, comment }),

  rejectItem: (id: string, reviewer: string, comment: string) =>
    USE_MOCK
      ? Promise.resolve({ status: 'REJECTED', reviewer, comment, note: 'Demo mode: not persisted' })
      : post(`/review-queue/${id}/reject`, { reviewer, comment }),
}
