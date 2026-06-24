// =============================================================================
// ThirdLine — Fleet Overview Page
// =============================================================================
// Shows all 5 agents in a heat-map grid with risk status, tier, and findings.

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../hooks/api'
import type { Agent } from '../types'
import { RiskDot, SeverityBadge, DimBadge, Spinner, MetricCard } from '../components/ui'

export function FleetPage() {
  const [agents, setAgents]   = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.getAgents()
      .then(setAgents)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />

  const criticalCount = agents.filter(a => a.highest_severity === 'CRITICAL').length
  const highCount     = agents.filter(a => a.highest_severity === 'HIGH').length
  const cleanCount    = agents.filter(a => a.finding_count === 0).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-white">Fleet Overview</h2>
        <p className="text-sm text-gray-400 mt-1">
          AI agent fleet — risk status at a glance
        </p>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Total Agents"   value={agents.length} />
        <MetricCard label="Critical Risk"  value={criticalCount} color={criticalCount > 0 ? 'red' : 'green'} />
        <MetricCard label="High Risk"      value={highCount}     color={highCount > 0 ? 'yellow' : 'green'} />
        <MetricCard label="Clean"          value={cleanCount}    color="green" />
      </div>

      {/* Agent grid */}
      <div className="grid grid-cols-1 gap-3">
        {agents.map(agent => (
          <button
            key={agent.agent_id}
            onClick={() => navigate(`/agents/${agent.agent_id}`)}
            className="w-full text-left bg-gray-900 border border-gray-800 rounded-xl p-5
                       hover:border-gray-600 hover:bg-gray-800/60 transition-all group"
          >
            <div className="flex items-start justify-between">
              {/* Left: agent info */}
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  <RiskDot color={agent.risk_color as any} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">{agent.name}</span>
                    <span className="text-xs text-gray-500 border border-gray-700 px-1.5 py-0.5 rounded">
                      {agent.materiality_tier}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{agent.business_line}</p>

                  {/* Failed dimensions */}
                  {agent.dimensions_failed.length > 0 && (
                    <div className="flex gap-1.5 mt-2">
                      {agent.dimensions_failed.map(d => <DimBadge key={d} dim={d} />)}
                    </div>
                  )}
                </div>
              </div>

              {/* Right: finding count + severity */}
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-xs text-gray-500">Interactions</p>
                  <p className="text-sm font-mono text-gray-300">{agent.interaction_count}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-500">Findings</p>
                  <p className="text-sm font-mono text-gray-300">{agent.finding_count}</p>
                </div>
                {agent.highest_severity ? (
                  <SeverityBadge severity={agent.highest_severity} />
                ) : (
                  <span className="text-xs text-emerald-400 font-medium">CLEAN</span>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Agent detail page ──────────────────────────────────────────────────────
export function AgentDetailPage() {
  const agentId = window.location.pathname.split('/').pop() ?? ''
  const [detail, setDetail] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    if (agentId) {
      api.getAgent(agentId)
        .then(setDetail)
        .finally(() => setLoading(false))
    }
  }, [agentId])

  if (loading) return <Spinner />
  if (!detail)  return <div className="text-red-400">Agent not found</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-gray-300 text-sm">← Back</button>
        <div>
          <h2 className="text-xl font-semibold text-white">{detail.name}</h2>
          <p className="text-xs text-gray-500">{detail.business_line} · {detail.materiality_tier} tier</p>
        </div>
      </div>

      {/* Dimension scorecards */}
      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-3">Evaluation Scorecards</h3>
        <div className="grid grid-cols-3 gap-3">
          {Object.entries(detail.dimension_scores ?? {}).map(([dim, data]: [string, any]) => (
            <div key={dim} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="flex justify-between items-start mb-3">
                <DimBadge dim={dim} />
                <span className={`text-xs font-semibold ${data.failures > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                  {data.failures > 0 ? `${data.failures} FAIL` : 'PASS'}
                </span>
              </div>
              <div className="space-y-1.5 mt-2">
                <div className="flex justify-between text-xs text-gray-500">
                  <span>Avg score</span><span className="text-gray-300 font-mono">{data.avg_score}</span>
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>Pass rate</span><span className="text-gray-300 font-mono">{(data.pass_rate * 100).toFixed(0)}%</span>
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>Evaluated</span><span className="text-gray-300 font-mono">{data.total}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Findings */}
      {detail.findings?.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-3">Findings</h3>
          <div className="space-y-2">
            {detail.findings.map((f: any) => (
              <div key={f.finding_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex gap-2 items-center">
                      <SeverityBadge severity={f.severity} />
                      <DimBadge dim={f.dimension} />
                    </div>
                    <p className="text-sm text-gray-200 mt-2">{f.title}</p>
                    <p className="text-xs text-gray-500 mt-1">{f.description?.slice(0, 200)}...</p>
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <p className="text-xs text-gray-500">{f.control_id}</p>
                    <p className="text-xs text-red-400 font-mono">{f.failure_count} failures</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
