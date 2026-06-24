// =============================================================================
// ThirdLine — Root App with Routing
// =============================================================================

import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { FleetPage, AgentDetailPage } from './pages/FleetPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { FindingsPage, LedgerPage, MetricsPage } from './pages/OtherPages'

function AgentDetailWrapper() {
  const { agentId } = useParams()
  return <AgentDetailPage key={agentId} />
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 p-8 overflow-y-auto">
          <Routes>
            <Route path="/"                    element={<FleetPage />} />
            <Route path="/agents/:agentId"     element={<AgentDetailWrapper />} />
            <Route path="/findings"            element={<FindingsPage />} />
            <Route path="/review"              element={<ReviewQueuePage />} />
            <Route path="/ledger"              element={<LedgerPage />} />
            <Route path="/metrics"             element={<MetricsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
