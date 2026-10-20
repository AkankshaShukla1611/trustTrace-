export function Card({ title, children, className = '' }) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {title && <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>}
      {children}
    </div>
  )
}

export function StatTile({ label, value, sublabel }) {
  return (
    <Card>
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
      {sublabel && <div className="mt-1 text-xs text-slate-400">{sublabel}</div>}
    </Card>
  )
}

export function Loading({ label = 'Loading...' }) {
  return <p className="text-sm text-slate-500">{label}</p>
}

export function ErrorBanner({ error }) {
  if (!error) return null
  return (
    <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
      {error.message || String(error)}
    </div>
  )
}

export function EmptyState({ label }) {
  return <p className="text-sm italic text-slate-400">{label}</p>
}

export function PrimaryButton({ children, ...props }) {
  return (
    <button
      {...props}
      className={`rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50 ${props.className || ''}`}
    >
      {children}
    </button>
  )
}

export function SecondaryButton({ children, ...props }) {
  return (
    <button
      {...props}
      className={`rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 ${props.className || ''}`}
    >
      {children}
    </button>
  )
}
