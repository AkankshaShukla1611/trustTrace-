const STYLES = {
  passed: 'bg-emerald-100 text-emerald-800',
  pass: 'bg-emerald-100 text-emerald-800',
  connected: 'bg-emerald-100 text-emerald-800',
  ok: 'bg-emerald-100 text-emerald-800',
  active: 'bg-emerald-100 text-emerald-800',

  failed: 'bg-rose-100 text-rose-800',
  fail: 'bg-rose-100 text-rose-800',
  error: 'bg-rose-100 text-rose-800',
  execution_error: 'bg-rose-100 text-rose-800',

  unevaluated: 'bg-slate-200 text-slate-700',
  unavailable: 'bg-slate-200 text-slate-700',
  not_tested: 'bg-slate-200 text-slate-700',
  configured: 'bg-slate-200 text-slate-700',
  archived: 'bg-slate-200 text-slate-500',
  cancelled: 'bg-slate-200 text-slate-700',

  running: 'bg-amber-100 text-amber-800',
  pending: 'bg-amber-100 text-amber-800',

  critical: 'bg-rose-200 text-rose-900',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-sky-100 text-sky-800',
}

export default function StatusBadge({ status }) {
  const key = String(status || '').toLowerCase()
  const style = STYLES[key] || 'bg-slate-200 text-slate-700'
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}>
      {status}
    </span>
  )
}
