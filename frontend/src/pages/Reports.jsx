import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading } from '../components/common'
import StatusBadge from '../components/StatusBadge'

export default function Reports() {
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState(null)
  const [expandedId, setExpandedId] = useState(null)
  const [reportText, setReportText] = useState(null)
  const [loadingReport, setLoadingReport] = useState(false)

  useEffect(() => {
    api.listRuns().then(setRuns).catch(setError)
  }, [])

  async function handlePreview(runId) {
    if (expandedId === runId) {
      setExpandedId(null)
      setReportText(null)
      return
    }
    setExpandedId(runId)
    setReportText(null)
    setLoadingReport(true)
    setError(null)
    try {
      setReportText(await api.getReport(runId, 'markdown'))
    } catch (err) {
      setError(err)
    } finally {
      setLoadingReport(false)
    }
  }

  if (error && !runs) return <ErrorBanner error={error} />
  if (!runs) return <Loading />

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Reports</h2>
        <p className="text-sm text-slate-500">
          Every report below is generated on demand from a run's real persisted data (<code>GET /runs/&#123;id&#125;/report</code>)
          -- nothing here is cached or pre-written.
        </p>
      </div>

      <ErrorBanner error={error} />

      <Card>
        {runs.length === 0 ? (
          <p className="text-sm italic text-slate-400">No runs yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1">Run</th>
                <th className="py-1">Status</th>
                <th className="py-1">Started</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <Fragment key={run.id}>
                  <tr className="border-t border-slate-100">
                    <td className="py-2 pr-4">
                      <Link to={`/runs/${run.id}`} className="font-medium text-sky-700 hover:underline">
                        {run.label || run.id}
                      </Link>
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="py-2 pr-4 text-slate-500">{new Date(run.started_at).toLocaleString()}</td>
                    <td className="py-2 space-x-3">
                      <button onClick={() => handlePreview(run.id)} className="text-xs text-sky-700 hover:underline">
                        {expandedId === run.id ? 'hide preview' : 'preview'}
                      </button>
                      <a href={api.reportUrl(run.id, 'markdown')} className="text-xs text-sky-700 hover:underline">
                        download .md
                      </a>
                      <a href={api.reportUrl(run.id, 'json')} className="text-xs text-sky-700 hover:underline">
                        download .json
                      </a>
                    </td>
                  </tr>
                  {expandedId === run.id && (
                    <tr>
                      <td colSpan={4} className="bg-slate-50 p-4">
                        {loadingReport ? (
                          <Loading label="Generating report..." />
                        ) : (
                          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded bg-white p-4 text-xs text-slate-700">
                            {reportText}
                          </pre>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
