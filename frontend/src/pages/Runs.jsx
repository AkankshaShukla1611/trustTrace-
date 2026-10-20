import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading } from '../components/common'
import StatusBadge from '../components/StatusBadge'

export default function Runs() {
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.listRuns().then(setRuns).catch(setError)
  }, [])

  if (error) return <ErrorBanner error={error} />
  if (!runs) return <Loading />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-900">Runs</h2>
        <Link to="/runs/new" className="text-sm text-sky-700 hover:underline">
          + New run
        </Link>
      </div>
      <Card>
        {runs.length === 0 ? (
          <p className="text-sm italic text-slate-400">No runs yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1">Label</th>
                <th className="py-1">Mode</th>
                <th className="py-1">Status</th>
                <th className="py-1">Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-t border-slate-100">
                  <td className="py-2 pr-4">
                    <Link to={`/runs/${run.id}`} className="font-medium text-sky-700 hover:underline">
                      {run.label || run.id}
                    </Link>
                  </td>
                  <td className="py-2 pr-4 text-slate-500">{run.mode}</td>
                  <td className="py-2 pr-4">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="py-2 text-slate-500">{new Date(run.started_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
