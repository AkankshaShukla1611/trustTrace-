import { Fragment, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading } from '../components/common'
import StatusBadge from '../components/StatusBadge'

function ExecutionPanel({ execution }) {
  return (
    <tr>
      <td colSpan={5} className="bg-slate-50 p-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Actual input</h4>
            <pre className="max-h-40 overflow-auto rounded bg-white p-2 text-xs">
              {JSON.stringify(execution.actual_input, null, 2)}
            </pre>
          </div>
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Actual output</h4>
            <pre className="max-h-40 overflow-auto rounded bg-white p-2 text-xs">
              {execution.actual_output ? JSON.stringify(execution.actual_output, null, 2) : '(none -- see error below)'}
            </pre>
          </div>
        </div>

        {execution.error_detail && (
          <div className="mt-3">
            <h4 className="mb-1 text-xs font-semibold uppercase text-rose-600">
              Error ({execution.error_category})
            </h4>
            <p className="text-sm text-rose-700">{execution.error_detail}</p>
          </div>
        )}

        <div className="mt-3">
          <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">
            Trace events {execution.trace_events.length === 0 && '-- none captured (adapter did not provide any)'}
          </h4>
          {execution.trace_events.length > 0 && (
            <ol className="space-y-1">
              {execution.trace_events.map((event, i) => (
                <li key={i} className="rounded bg-white p-2 text-xs">
                  <span className="font-medium">
                    {i + 1}. {event.stage_name}
                  </span>{' '}
                  <StatusBadge status={event.status} />
                  <pre className="mt-1 max-h-24 overflow-auto">{JSON.stringify(event.payload, null, 2)}</pre>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="mt-3">
          <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Evaluator results</h4>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-slate-400">
                <th className="py-1">Evaluator</th>
                <th className="py-1">Status</th>
                <th className="py-1">Score</th>
                <th className="py-1">Reason</th>
              </tr>
            </thead>
            <tbody>
              {execution.evaluator_results.map((r) => (
                <tr key={r.id} className="border-t border-slate-200">
                  <td className="py-1 pr-2 font-medium">{r.evaluator_name}</td>
                  <td className="py-1 pr-2">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="py-1 pr-2">{r.score ?? '--'}</td>
                  <td className="py-1 text-slate-600">
                    {r.reason}
                    {r.limitations && <span className="ml-1 italic text-slate-400">({r.limitations})</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </td>
    </tr>
  )
}

export default function RunDetail() {
  const { runId } = useParams()
  const [run, setRun] = useState(null)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    api.getRun(runId).then(setRun).catch(setError)
  }, [runId])

  if (error) return <ErrorBanner error={error} />
  if (!run) return <Loading />

  return (
    <div className="space-y-6">
      <div>
        <Link to="/runs" className="text-sm text-sky-700 hover:underline">
          &larr; All runs
        </Link>
        <h2 className="text-xl font-bold text-slate-900">{run.label || run.id}</h2>
        <p className="text-sm text-slate-500">
          <StatusBadge status={run.status} /> &middot; started {new Date(run.started_at).toLocaleString()}
          {run.finished_at && ` -- finished ${new Date(run.finished_at).toLocaleString()}`}
        </p>
      </div>

      <Card title={`Executions (${run.executions.length}) -- click a row to view its trace`}>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="py-1">Test case</th>
              <th className="py-1">Status</th>
              <th className="py-1">Duration</th>
              <th className="py-1">Evaluators</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody>
            {run.executions.map((execution) => (
              <Fragment key={execution.id}>
                <tr
                  onClick={() => setExpanded(expanded === execution.id ? null : execution.id)}
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                >
                  <td className="py-2 pr-4 font-mono text-xs">{execution.test_case_id}</td>
                  <td className="py-2 pr-4">
                    <StatusBadge status={execution.status} />
                  </td>
                  <td className="py-2 pr-4 text-slate-500">
                    {execution.duration_ms != null ? `${execution.duration_ms.toFixed(1)} ms` : '--'}
                  </td>
                  <td className="py-2 pr-4 text-slate-500">
                    {execution.evaluator_results.filter((r) => r.status !== 'unavailable').length} applicable /{' '}
                    {execution.evaluator_results.length} total
                  </td>
                  <td className="py-2 text-sky-700">{expanded === execution.id ? 'hide' : 'view'}</td>
                </tr>
                {expanded === execution.id && <ExecutionPanel execution={execution} />}
              </Fragment>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
