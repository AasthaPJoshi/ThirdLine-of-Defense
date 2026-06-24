// =============================================================================
// ThirdLine — Shared UI Components
// =============================================================================

import { type ReactNode } from 'react'
import type { RiskColor, Severity } from '../types'

// ── Severity badge ─────────────────────────────────────────────────────────
export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const styles: Record<string, string> = {
    CRITICAL: 'bg-red-500/20 text-red-400 border border-red-500/40',
    HIGH:     'bg-orange-500/20 text-orange-400 border border-orange-500/40',
    MEDIUM:   'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40',
    LOW:      'bg-blue-500/20 text-blue-400 border border-blue-500/40',
  }
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${styles[severity] ?? styles.LOW}`}>
      {severity}
    </span>
  )
}

// ── Risk dot ───────────────────────────────────────────────────────────────
export function RiskDot({ color }: { color: RiskColor }) {
  const styles: Record<RiskColor, string> = {
    red:   'bg-red-500 shadow-red-500/50',
    amber: 'bg-orange-400 shadow-orange-400/50',
    green: 'bg-emerald-500 shadow-emerald-500/50',
    gray:  'bg-gray-500',
  }
  return (
    <span className={`inline-block w-2.5 h-2.5 rounded-full shadow-lg ${styles[color]}`} />
  )
}

// ── Status badge ───────────────────────────────────────────────────────────
export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    PENDING:        'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40',
    PENDING_REVIEW: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40',
    APPROVED:       'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40',
    REJECTED:       'bg-gray-500/20 text-gray-400 border border-gray-500/40',
  }
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${styles[status] ?? styles.PENDING}`}>
      {status.replace('_', ' ')}
    </span>
  )
}

// ── Dimension badge ────────────────────────────────────────────────────────
export function DimBadge({ dim }: { dim: string }) {
  const colors: Record<string, string> = {
    hallucination: 'bg-purple-500/20 text-purple-300 border border-purple-500/30',
    bias:          'bg-pink-500/20 text-pink-300 border border-pink-500/30',
    drift:         'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30',
    robustness:    'bg-red-500/20 text-red-300 border border-red-500/30',
    reliability:   'bg-blue-500/20 text-blue-300 border border-blue-500/30',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${colors[dim] ?? 'bg-gray-600 text-gray-300'}`}>
      {dim}
    </span>
  )
}

// ── Metric card ────────────────────────────────────────────────────────────
export function MetricCard({ label, value, sub, color = 'default' }: {
  label: string; value: string | number; sub?: string; color?: string
}) {
  const colors: Record<string, string> = {
    green:   'text-emerald-400',
    red:     'text-red-400',
    yellow:  'text-yellow-400',
    blue:    'text-blue-400',
    default: 'text-white',
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-bold ${colors[color]}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

// ── Section card ───────────────────────────────────────────────────────────
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl ${className}`}>
      {children}
    </div>
  )
}

// ── Score bar ──────────────────────────────────────────────────────────────
export function ScoreBar({ score, threshold = 0.75 }: { score: number; threshold?: number }) {
  const pct = Math.round(score * 100)
  const pass = score >= threshold
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-800 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all ${pass ? 'bg-emerald-500' : 'bg-red-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono w-8 ${pass ? 'text-emerald-400' : 'text-red-400'}`}>
        {score.toFixed(2)}
      </span>
    </div>
  )
}

// ── Loading spinner ────────────────────────────────────────────────────────
export function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// ── Empty state ────────────────────────────────────────────────────────────
export function Empty({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-500">
      <p className="text-sm">{message}</p>
    </div>
  )
}
