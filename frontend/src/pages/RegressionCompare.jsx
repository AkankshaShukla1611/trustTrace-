import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Card, ErrorBanner, PrimaryButton } from '../components/common'

function CountRow({ label, items, tone = 'slate' }) {
  const toneClass = { slate: 'text-slate-700', rose: 'text-rose-700', emerald: 'text-emerald-700' }[tone]
  return (
    <div className="flex items-start justify-between border-b border-slate-100 py-2 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`text-sm font-semibold ${toneClass}`}>{items.length}</span>
    </div>
  )
}

export default function RegressionCompare() {
  const [runs, setRuns] = useState([])
  const [baselineId, setBaselineId] = useState('')
  const [candidateId, setCandidateId] = useState('')
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.listRuns().then(setRuns).catch(setError)
  }, [])

  async function handleCompare(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSummary(null)
    try {
      setSummary(await api.compareRuns(baselineId, candidateId))
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-slate-900">Regression Comparison</h2>
      <ErrorBanner error={error} />

      <Card>
        <form onSubmit={handleCompare} className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-500">Baseline run</label>
            <select
              required
              className="w-64 rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
            >
              <option value="">select baseline</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label || r.id}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">Candidate run</label>
            <select
              required
              className="w-64 rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={candidateId}
              onChange={(e) => setCandidateId(e.target.value)}
            >
              <option value="">select candidate</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label || r.id}
                </option>
              ))}
            </select>
          </div>
          <PrimaryButton type="submit" disabled={loading || !baselineId || !candidateId}>
            {loading ? 'Comparing...' : 'Compare'}
          </PrimaryButton>
        </form>
      </Card>

      {summary && (
        <>
          <Card title="Summary">
            <CountRow label="New failures" items={summary.new_failures} tone="rose" />
            <CountRow label="Critical failures" items={summary.critical_failures} tone="rose" />
            <CountRow label="Resolved failures" items={summary.resolved_failures} tone="emerald" />
            <CountRow label="Newly passed" items={summary.newly_passed} tone="emerald" />
            <CountRow label="Unchanged failures" items={summary.unchanged_failures} />
            <CountRow label="Non-comparable (dataset changed)" items={summary.non_comparable} />
            <p className="mt-3 text-xs text-slate-400">
              Integration config {summary.config_changed ? 'changed' : 'did not change'} between the two runs.
            </p>
          </Card>

          {Object.keys(summary.category_changes || {}).length > 0 && (
            <Card title="Category-level changes">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="py-1">Category</th>
                    <th className="py-1">Improved</th>
                    <th className="py-1">Regressed</th>
                    <th className="py-1">Unchanged</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(summary.category_changes).map(([category, counts]) => (
                    <tr key={category} className="border-t border-slate-100">
                      <td className="py-2 pr-4 font-medium">{category}</td>
                      <td className="py-2 pr-4 text-emerald-700">{counts.improved}</td>
                      <td className="py-2 pr-4 text-rose-700">{counts.regressed}</td>
                      <td className="py-2 text-slate-500">{counts.unchanged}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
