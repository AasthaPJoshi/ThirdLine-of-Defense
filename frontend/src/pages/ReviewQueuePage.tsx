// =============================================================================
// ThirdLine — Human Review Queue Page
// =============================================================================
// The HITL interface. Auditors review AI-drafted findings and approve/reject.
// No finding becomes final without human action on this page.

import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../hooks/api'
import type { QueueItem } from '../types'
import { SeverityBadge, StatusBadge, DimBadge, Spinner, Empty } from '../components/ui'

export function ReviewQueuePage() {
  const [items, setItems]       = useState<QueueItem[]>([])
  const [loading, setLoading]   = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [reviewer, setReviewer] = useState('auditor')
  const [comment, setComment]   = useState('')
  const [acting, setActing]     = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    api.getQueue().then(setItems).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleApprove = async (queueId: string) => {
    setActing(queueId)
    try {
      await api.approveItem(queueId, reviewer, comment)
      setComment('')
      load()
    } catch (e) {
      alert(`Error: ${e}`)
    } finally { setActing(null) }
  }

  const handleReject = async (queueId: string) => {
    if (!comment.trim()) { alert('Please add a comment when rejecting a finding.'); return }
    setActing(queueId)
    try {
      await api.rejectItem(queueId, reviewer, comment)
      setComment('')
      load()
    } catch (e) {
      alert(`Error: ${e}`)
    } finally { setActing(null) }
  }

  if (loading) return <Spinner />

  const pending   = items.filter(i => i.status === 'PENDING')
  const actioned  = items.filter(i => i.status !== 'PENDING')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Human Review Queue</h2>
          <p className="text-sm text-gray-400 mt-1">
            {pending.length} finding{pending.length !== 1 ? 's' : ''} awaiting your review
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">Reviewer:</label>
          <input
            value={reviewer}
            onChange={e => setReviewer(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 w-32"
            placeholder="your-name"
          />
        </div>
      </div>

      {/* Pending items */}
      {pending.length === 0 ? (
        <Empty message="No pending items — all findings have been reviewed." />
      ) : (
        <div className="space-y-3">
          {pending.map(item => (
            <div key={item.queue_id}
              className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              {/* Summary row */}
              <div className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <SeverityBadge severity={item.severity} />
                  <DimBadge dim={item.dimension} />
                  <span className="text-sm text-gray-200 font-medium">{item.title}</span>
                </div>
                <button
                  onClick={() => setExpanded(expanded === item.queue_id ? null : item.queue_id)}
                  className="text-gray-500 hover:text-gray-300"
                >
                  {expanded === item.queue_id ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
                </button>
              </div>

              {/* Expanded: workpaper + actions */}
              {expanded === item.queue_id && (
                <div className="border-t border-gray-800 p-4 space-y-4">
                  {/* Workpaper text */}
                  <div className="bg-gray-950 rounded-lg p-4 max-h-72 overflow-y-auto">
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
                      {item.draft_text}
                    </pre>
                  </div>

                  {/* Meta */}
                  <div className="flex gap-6 text-xs text-gray-500">
                    <span>Control: <span className="text-gray-300">{item.control_id ?? 'N/A'}</span></span>
                    <span>Queued: <span className="text-gray-300">{new Date(item.queued_at).toLocaleString()}</span></span>
                    {item.sla_deadline && (
                      <span>SLA: <span className="text-yellow-400">{new Date(item.sla_deadline).toLocaleString()}</span></span>
                    )}
                  </div>

                  {/* Comment */}
                  <textarea
                    value={comment}
                    onChange={e => setComment(e.target.value)}
                    placeholder="Add a reviewer comment (required for rejection)..."
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg p-3
                               text-sm text-gray-200 placeholder-gray-600 resize-none h-20
                               focus:outline-none focus:border-blue-500"
                  />

                  {/* Action buttons */}
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleApprove(item.queue_id)}
                      disabled={acting === item.queue_id}
                      className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500
                                 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
                    >
                      <CheckCircle size={15}/>
                      {acting === item.queue_id ? 'Processing...' : 'Approve Finding'}
                    </button>
                    <button
                      onClick={() => handleReject(item.queue_id)}
                      disabled={acting === item.queue_id}
                      className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600
                                 disabled:opacity-50 rounded-lg text-sm font-medium text-gray-200 transition-colors"
                    >
                      <XCircle size={15}/>
                      Reject
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Actioned items */}
      {actioned.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-3">Actioned</h3>
          <div className="space-y-2">
            {actioned.map(item => (
              <div key={item.queue_id}
                className="flex items-center justify-between bg-gray-900/50 border border-gray-800/50
                           rounded-xl px-4 py-3 opacity-60">
                <div className="flex items-center gap-3">
                  <SeverityBadge severity={item.severity} />
                  <span className="text-sm text-gray-400">{item.title}</span>
                </div>
                <StatusBadge status={item.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
