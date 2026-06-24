// =============================================================================
// ThirdLine — Sidebar Navigation
// =============================================================================

import { NavLink } from 'react-router-dom'
import { LayoutDashboard, ShieldAlert, ClipboardCheck, BookLock, BarChart3 } from 'lucide-react'

const links = [
  { to: '/',        icon: LayoutDashboard, label: 'Fleet Overview' },
  { to: '/findings',icon: ShieldAlert,     label: 'Findings'       },
  { to: '/review',  icon: ClipboardCheck,  label: 'Review Queue'   },
  { to: '/ledger',  icon: BookLock,        label: 'Audit Ledger'   },
  { to: '/metrics', icon: BarChart3,       label: 'Metrics'        },
]

export function Sidebar() {
  return (
    <aside className="w-56 min-h-screen bg-gray-950 border-r border-gray-800 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-800">
        <h1 className="text-lg font-bold text-white tracking-tight">ThirdLine</h1>
        <p className="text-xs text-gray-500 mt-0.5">AI Audit & Governance</p>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600/20 text-blue-400 font-medium'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-gray-800">
        <p className="text-xs text-gray-600">v{import.meta.env.VITE_APP_VERSION ?? '1.0.0'}</p>
      </div>
    </aside>
  )
}
