import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading, StatTile } from '../components/common'
import StatusBadge from '../components/StatusBadge'

export default function Dashboard() {
  const [projects, setProjects] = useState(null)
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [projectList, runList] = await Promise.all([api.listProjects(), api.listRuns()])
        if (cancelled) return
        setProjects(projectList)
        // Dashboard-level stats need execution detail, which the list
        // endpoint omits on purpose (it's heavy) -- fetch each run's
        // full detail. Fine at demo scale; would need pagination/
        // server-side aggregation before this scales to many runs.
        const fullRuns = await Promise.all(runList.map((r) => api.getRun(r.id)))
        if (cancelled) return
        setRuns(fullRuns)
      } catch (err) {
        if (!cancelled) setError(err)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  if (error) return <ErrorBanner error={error} />
  if (!projects || !runs) return <Loading label="Loading dashboard..." />

  const executions = runs.flatMap((r) => r.executions.map((e) => ({ ...e, runLabel: r.label || r.id, runId: r.id })))
  const counts = {
    passed: executions.filter((e) => e.status === 'passed').length,
    failed: executions.filter((e) => e.status === 'failed').length,
    unevaluated: executions.filter((e) => e.status === 'unevaluated').length,
    execution_error: executions.filter((e) => e.status === 'execution_error').length,
    needs_review: executions.filter((e) => e.status === 'needs_review').length,
  }
  const total = executions.length
  const evaluated = counts.passed + counts.failed
  const passRate = evaluated > 0 ? ((counts.passed / evaluated) * 100).toFixed(0) : null
  const coverage = total > 0 ? ((evaluated / total) * 100).toFixed(0) : null

  const criticalFailures = executions
    .flatMap((e) => (e.evaluator_results || []).map((r) => ({ ...r, execution: e })))
    .filter((r) => r.status === 'fail' && r.severity === 'critical')

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Dashboard</h2>
        <p className="text-sm text-slate-500">
          Real data from {projects.length} project(s) and {runs.length} run(s). No hardcoded metrics.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Total test executions" value={total} />
        <StatTile
          label="Pass rate (of evaluated)"
          value={passRate !== null ? `${passRate}%` : 'n/a'}
          sublabel={`${counts.passed} passed / ${evaluated} evaluated -- excludes unevaluated cases`}
        />
        <StatTile
          label="Evaluation coverage"
          value={coverage !== null ? `${coverage}%` : 'n/a'}
          sublabel={`${evaluated} evaluated / ${total} total -- coverage, not accuracy`}
        />
        <StatTile label="Execution errors" value={counts.execution_error} sublabel="distinct from a wrong answer" />
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatTile label="Passed" value={counts.passed} />
        <StatTile label="Failed" value={counts.failed} />
        <StatTile label="Needs review" value={counts.needs_review} sublabel="inconclusive LLM judge verdict" />
        <StatTile label="Unevaluated" value={counts.unevaluated} sublabel="no applicable evaluator ran" />
        <StatTile label="Execution errors" value={counts.execution_error} />
      </div>

      <Card title={`Critical failures (${criticalFailures.length})`}>
        {criticalFailures.length === 0 ? (
          <p className="text-sm italic text-slate-400">None found across the runs above.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1">Evaluator</th>
                <th className="py-1">Reason</th>
                <th className="py-1">Run</th>
              </tr>
            </thead>
            <tbody>
              {criticalFailures.map((f, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="py-2 pr-4 font-medium">{f.evaluator_name}</td>
                  <td className="py-2 pr-4 text-slate-600">{f.reason}</td>
                  <td className="py-2">
                    <Link to={`/runs/${f.execution.runId}`} className="text-sky-700 hover:underline">
                      {f.runLabel}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Runs">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="py-1">Label</th>
              <th className="py-1">Status</th>
              <th className="py-1">Executions</th>
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
                <td className="py-2 pr-4">
                  <StatusBadge status={run.status} />
                </td>
                <td className="py-2 pr-4">{run.executions.length}</td>
                <td className="py-2 text-slate-500">{new Date(run.started_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
