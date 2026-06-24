// =============================================================================
// ThirdLine — Findings, Ledger, and Metrics Pages
// =============================================================================

import { useEffect, useState } from 'react'
import { ShieldCheck, ShieldX } from 'lucide-react'
import { api } from '../hooks/api'
import type { Finding, LedgerEntry, Metrics } from '../types'
import {
  SeverityBadge, StatusBadge, DimBadge, Spinner, Empty, MetricCard, ScoreBar
} from '../components/ui'

// ── Findings Page ──────────────────────────────────────────────────────────
export function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    api.getFindings().then(setFindings).finally(() => setLoading(false))
  }, [])

  if (loading)            return <Spinner />
  if (!findings.length)   return <Empty message="No findings yet. Run the audit pipeline first." />

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">All Findings</h2>
        <p className="text-sm text-gray-400 mt-1">{findings.length} findings from the last audit run</p>
      </div>

      <div className="space-y-3">
        {findings.map(f => (
          <div key={f.finding_id}
            className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2 flex-1">
                <div className="flex flex-wrap gap-2 items-center">
                  <SeverityBadge severity={f.severity} />
                  <DimBadge dim={f.dimension} />
                  <StatusBadge status={f.status} />
                  {f.control_id && (
                    <span className="text-xs text-gray-500 font-mono">{f.control_id}</span>
                  )}
                </div>
                <p className="text-sm text-white font-medium">{f.title}</p>
                <div className="flex gap-6 text-xs text-gray-500">
                  <span>{f.failure_count} interaction{f.failure_count !== 1 ? 's' : ''} failed</span>
                  <span>Avg score: <span className="font-mono text-gray-300">{f.avg_score.toFixed(3)}</span></span>
                  <span>Drafted: {new Date(f.drafted_at).toLocaleString()}</span>
                </div>
                <ScoreBar score={f.avg_score} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Audit Ledger Page ──────────────────────────────────────────────────────
export function LedgerPage() {
  const [data,    setData]    = useState<{ entries: LedgerEntry[]; chain_intact: boolean; total_entries: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getLedger().then(setData).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (!data)   return <Empty message="Ledger not available." />

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Audit Ledger</h2>
          <p className="text-sm text-gray-400 mt-1">
            Tamper-evident, hash-chained record of all audit events
          </p>
        </div>
        <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border ${
          data.chain_intact
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            : 'bg-red-500/10 border-red-500/30 text-red-400'
        }`}>
          {data.chain_intact
            ? <><ShieldCheck size={16}/> <span className="text-sm font-semibold">CHAIN INTACT</span></>
            : <><ShieldX size={16}/>    <span className="text-sm font-semibold">CHAIN BROKEN</span></>
          }
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <MetricCard label="Total Entries"  value={data.total_entries} />
        <MetricCard label="Chain Status"   value={data.chain_intact ? 'INTACT' : 'BROKEN'}
                    color={data.chain_intact ? 'green' : 'red'} />
      </div>

      {data.entries.length === 0 ? (
        <Empty message="No ledger entries yet. Approve a finding to create the first entry." />
      ) : (
        <div className="space-y-2">
          {[...data.entries].reverse().map(entry => (
            <div key={entry.seq}
              className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-gray-500">#{entry.seq}</span>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                      entry.event_type === 'FINDING_APPROVED'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : entry.event_type === 'FINDING_REJECTED'
                        ? 'bg-gray-500/20 text-gray-400'
                        : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      {entry.event_type.replace('FINDING_', '')}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    Agent: <span className="text-gray-300">{entry.agent_id.replace('agt-','').replace('-001','')}</span>
                    &nbsp;·&nbsp;
                    Actor: <span className="text-gray-300">{entry.actor}</span>
                  </p>
                  <p className="text-xs text-gray-600 font-mono">
                    {new Date(entry.event_ts).toLocaleString()}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-xs text-gray-600 font-mono">chain</p>
                  <p className="text-xs font-mono text-gray-500">
                    {entry.chain_hash.slice(0, 20)}...
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Metrics Page ───────────────────────────────────────────────────────────
export function MetricsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getMetrics().then(setMetrics).finally(() => setLoading(false))
  }, [])

  if (loading)  return <Spinner />
  if (!metrics) return <Empty message="Metrics not available. Run the audit and meta-eval first." />

  const f1Color = metrics.f1 >= 0.8 ? 'green' : metrics.f1 >= 0.5 ? 'yellow' : 'red'

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Detection Metrics</h2>
        <p className="text-sm text-gray-400 mt-1">
          ThirdLine's own performance against known ground truth labels
        </p>
      </div>

      {/* Core metrics */}
      <div className="grid grid-cols-3 gap-4">
        <MetricCard
          label="F1 Score"
          value={metrics.f1.toFixed(3)}
          sub="Harmonic mean of precision & recall"
          color={f1Color}
        />
        <MetricCard
          label="Precision"
          value={`${(metrics.precision * 100).toFixed(1)}%`}
          sub={`${metrics.true_positives} TP, ${metrics.false_positives} FP`}
          color={f1Color}
        />
        <MetricCard
          label="Recall"
          value={`${(metrics.recall * 100).toFixed(1)}%`}
          sub={`${metrics.agents_detected} / ${metrics.agents_evaluated} defects caught`}
          color={f1Color}
        />
      </div>

      {/* Secondary stats */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Total Interactions" value={metrics.total_interactions} />
        <MetricCard label="Total Findings"     value={metrics.total_findings} />
        <MetricCard label="Ledger Intact"      value={metrics.ledger_intact ? 'YES' : 'NO'}
                    color={metrics.ledger_intact ? 'green' : 'red'} />
        <MetricCard label="Agents Evaluated"   value={metrics.agents_evaluated} />
      </div>

      {/* Findings by severity */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-400 mb-4">Findings by Severity</h3>
        <div className="space-y-3">
          {['CRITICAL','HIGH','MEDIUM','LOW'].map(sev => {
            const count = metrics.findings_by_severity[sev] ?? 0
            const max   = Math.max(...Object.values(metrics.findings_by_severity), 1)
            const pct   = (count / max) * 100
            const color: Record<string, string> = {
              CRITICAL: 'bg-red-500', HIGH: 'bg-orange-400',
              MEDIUM: 'bg-yellow-400', LOW: 'bg-blue-400',
            }
            return (
              <div key={sev} className="flex items-center gap-3">
                <span className="text-xs text-gray-500 w-16">{sev}</span>
                <div className="flex-1 bg-gray-800 rounded-full h-2">
                  <div className={`h-2 rounded-full ${color[sev]}`} style={{ width: `${pct}%` }} />
                </div>
                <span className="text-xs font-mono text-gray-300 w-4">{count}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Resume callout */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
        <p className="text-sm text-blue-300 font-medium">Resume bullet</p>
        <p className="text-xs text-blue-200/80 mt-1 leading-relaxed">
          "ThirdLine achieved F1={metrics.f1.toFixed(3)} (Precision {(metrics.precision*100).toFixed(1)}%,
          Recall {(metrics.recall*100).toFixed(1)}%) detecting {metrics.agents_detected}/{metrics.agents_evaluated} injected
          AI agent defects across hallucination, bias, drift, robustness, and reliability dimensions
          on {metrics.total_interactions} synthetic interactions, with a {metrics.ledger_intact ? 'verified-intact' : ''} tamper-evident audit ledger."
        </p>
      </div>
    </div>
  )
}
