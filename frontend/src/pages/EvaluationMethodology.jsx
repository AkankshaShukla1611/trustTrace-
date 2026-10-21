import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading } from '../components/common'

const EXECUTION_STATUSES = [
  ['passed', 'Every applicable evaluator passed. At least one evaluator was applicable.'],
  ['failed', 'At least one applicable evaluator failed (or errored).'],
  ['needs_review', 'No failure, but the optional LLM judge returned an inconclusive verdict -- never counted as a pass; a person should look at it.'],
  ['unevaluated', 'Execution succeeded, but no evaluator had anything applicable to check -- never counted as a pass.'],
  ['execution_error', 'The adapter itself failed or timed out. Distinct from a wrong answer -- evaluation is skipped entirely.'],
  ['cancelled', 'The run was cancelled before this execution completed.'],
]

const EVALUATOR_STATUSES = [
  ['pass', 'The evaluator ran and the output met its criteria.'],
  ['fail', 'The evaluator ran and the output did not meet its criteria.'],
  ['unavailable', 'Nothing applicable to check for this test case (e.g. no labeled evidence, wrong behavior_type for this evaluator). Never counted toward pass or fail.'],
  ['error', 'The evaluator itself hit a configuration/rule problem (e.g. an unparseable date format) -- a defect in the test setup, not a verdict on the output.'],
  ['inconclusive', "The optional LLM judge genuinely couldn't decide. Rolls the whole execution up to needs_review -- never treated as a pass."],
]

export default function EvaluationMethodology() {
  const [evaluators, setEvaluators] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.listEvaluators().then(setEvaluators).catch(setError)
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Evaluation Methodology</h2>
        <p className="text-sm text-slate-500">
          8 of the 9 evaluators below are deterministic -- no LLM call, no API key required, and together they're
          sufficient to run the full local demo. One optional evaluator (<code>llm_judge</code>) uses Claude as a
          semantic grader for free-text correctness; it only runs when a test case opts in <em>and</em> an API key
          is configured, and its verdict is always labeled as a model's opinion, never an unquestionable fact.
          Descriptions below are pulled live from each evaluator's own docstring in the backend, so this page can't
          drift out of sync with what the engine actually runs.
        </p>
      </div>

      <ErrorBanner error={error} />

      <Card title="Coverage vs. accuracy -- kept as separate numbers on purpose">
        <p className="text-sm text-slate-600">
          <strong>Pass rate</strong> is passed / (passed + failed) -- it only looks at cases an evaluator actually
          judged. <strong>Evaluation coverage</strong> is (passed + failed) / total -- how much of the dataset had
          an applicable evaluator at all. A high pass rate on low coverage is a thin signal, not a strong one; the
          dashboard and reports always show both, never blend them into one score.
        </p>
      </Card>

      <Card title={`Evaluators (${evaluators?.length ?? '...'})`}>
        {!evaluators ? (
          <Loading />
        ) : (
          <div className="space-y-4">
            {evaluators.map((ev) => (
              <div key={ev.name} className="border-b border-slate-100 pb-4 last:border-0">
                <div className="flex items-baseline gap-2">
                  <h4 className="font-mono text-sm font-semibold text-slate-900">{ev.name}</h4>
                  <span className="text-xs text-slate-400">v{ev.version}</span>
                  {!ev.deterministic && (
                    <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">
                      optional &middot; model-judged
                    </span>
                  )}
                </div>
                <p className="mt-1 whitespace-pre-line text-sm text-slate-600">{ev.description}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="Execution statuses">
        <table className="w-full text-sm">
          <tbody>
            {EXECUTION_STATUSES.map(([status, meaning]) => (
              <tr key={status} className="border-t border-slate-100">
                <td className="py-2 pr-4 align-top font-mono text-xs font-semibold text-slate-700">{status}</td>
                <td className="py-2 text-slate-600">{meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Evaluator statuses">
        <table className="w-full text-sm">
          <tbody>
            {EVALUATOR_STATUSES.map(([status, meaning]) => (
              <tr key={status} className="border-t border-slate-100">
                <td className="py-2 pr-4 align-top font-mono text-xs font-semibold text-slate-700">{status}</td>
                <td className="py-2 text-slate-600">{meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="What TrustTrace does not claim">
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>The LLM judge is opt-in per test case and requires an API key -- it never runs, and never silently affects a result, unless both are explicitly set.</li>
          <li>An inconclusive judge verdict is never counted as a pass -- it flags the execution <code>needs_review</code> for a person to look at.</li>
          <li>Citation "support" checks are lexical overlap, not semantic entailment -- a citation can overlap in wording without actually supporting the claim, and vice versa.</li>
          <li>A `file`-adapter run evaluates supplied output/evidence only; it cannot independently verify the target application's live execution.</li>
          <li>Passing a test case proves the configured checks were satisfied -- it is not a guarantee the application is correct in every respect.</li>
        </ul>
      </Card>
    </div>
  )
}
