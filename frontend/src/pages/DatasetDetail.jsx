import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading, PrimaryButton, SecondaryButton } from '../components/common'
import StatusBadge from '../components/StatusBadge'

const SEVERITIES = ['low', 'medium', 'high', 'critical']
const BEHAVIORS = ['exact_fields', 'free_text', 'abstain_expected', 'conflict_flag_expected']

const BLANK_CASE = {
  name: '',
  category: '',
  severity: 'medium',
  behavior_type: 'free_text',
  tags: '',
  input_payload: '{}',
  expected_output: '',
  expected_evidence: '[]',
  evaluator_config: '{}',
}

export default function DatasetDetail() {
  const { datasetId } = useParams()
  const [dataset, setDataset] = useState(null)
  const [cases, setCases] = useState(null)
  const [versions, setVersions] = useState(null)
  const [error, setError] = useState(null)
  const [importResult, setImportResult] = useState(null)

  const [filters, setFilters] = useState({ category: '', severity: '', tag: '', q: '' })
  const [form, setForm] = useState(BLANK_CASE)
  const [formError, setFormError] = useState(null)

  async function load() {
    try {
      const [d, v] = await Promise.all([api.getDataset(datasetId), api.listDatasetVersions(datasetId)])
      setDataset(d)
      setVersions(v)
    } catch (err) {
      setError(err)
    }
  }

  async function loadCases() {
    try {
      setCases(await api.listTestCases(datasetId, filters))
    } catch (err) {
      setError(err)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId])

  useEffect(() => {
    loadCases()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, filters])

  function parseFormPayload() {
    const payload = {
      name: form.name,
      category: form.category,
      severity: form.severity,
      behavior_type: form.behavior_type,
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      input_payload: JSON.parse(form.input_payload || '{}'),
      expected_evidence: JSON.parse(form.expected_evidence || '[]'),
      evaluator_config: JSON.parse(form.evaluator_config || '{}'),
    }
    if (form.expected_output.trim()) payload.expected_output = JSON.parse(form.expected_output)
    return payload
  }

  async function handleCreate(e) {
    e.preventDefault()
    setFormError(null)
    let payload
    try {
      payload = parseFormPayload()
    } catch {
      setFormError('One of the JSON fields (input_payload / expected_output / expected_evidence / evaluator_config) is not valid JSON.')
      return
    }
    try {
      await api.createTestCase(datasetId, payload)
      setForm(BLANK_CASE)
      await loadCases()
    } catch (err) {
      setFormError(err.detail ? JSON.stringify(err.detail) : err.message)
    }
  }

  async function handleArchive(id) {
    setError(null)
    try {
      await api.archiveTestCase(id)
      await loadCases()
    } catch (err) {
      setError(err)
    }
  }

  async function handleImportFile(e) {
    const file = e.target.files[0]
    if (!file) return
    setError(null)
    setImportResult(null)
    try {
      const text = await file.text()
      const testCases = JSON.parse(text)
      const result = await api.importTestCases(datasetId, Array.isArray(testCases) ? testCases : [testCases])
      setImportResult(result)
      await loadCases()
    } catch (err) {
      setError(err instanceof SyntaxError ? new Error('Uploaded file is not valid JSON') : err)
    } finally {
      e.target.value = ''
    }
  }

  async function handleCreateVersion() {
    setError(null)
    try {
      await api.createDatasetVersion(datasetId)
      await load()
    } catch (err) {
      setError(err)
    }
  }

  if (error && !dataset) return <ErrorBanner error={error} />
  if (!dataset) return <Loading />

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/projects/${dataset.project_id}`} className="text-sm text-sky-700 hover:underline">
          &larr; Project
        </Link>
        <h2 className="text-xl font-bold text-slate-900">{dataset.name}</h2>
      </div>

      <ErrorBanner error={error} />

      <Card title="Dataset versions">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm text-slate-500">
            Immutable snapshots of currently-active test cases, for reproducible runs.
          </p>
          <PrimaryButton onClick={handleCreateVersion}>Snapshot new version</PrimaryButton>
        </div>
        {versions === null ? (
          <Loading />
        ) : versions.length === 0 ? (
          <p className="text-sm italic text-slate-400">No versions snapshotted yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1">Version</th>
                <th className="py-1">Test cases</th>
                <th className="py-1">Created</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.id} className="border-t border-slate-100">
                  <td className="py-2">#{v.version_number}</td>
                  <td className="py-2">{v.test_case_count}</td>
                  <td className="py-2 text-slate-500">{new Date(v.created_at).toLocaleString()}</td>
                  <td className="py-2">
                    <Link
                      to={`/runs/new?project_id=${dataset.project_id}&dataset_version_id=${v.id}`}
                      className="text-sky-700 hover:underline"
                    >
                      Run this version
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Import / export test cases">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500">Import JSON file (array of test cases)</label>
            <input type="file" accept="application/json" onChange={handleImportFile} className="text-sm" />
          </div>
          <a href={api.exportTestCasesUrl(datasetId, 'json')} className="text-sm text-sky-700 hover:underline">
            Export JSON
          </a>
          <a href={api.exportTestCasesUrl(datasetId, 'csv')} className="text-sm text-sky-700 hover:underline">
            Export CSV
          </a>
        </div>
        {importResult && (
          <p className="mt-2 text-sm text-slate-600">
            Created {importResult.created.length}, skipped {importResult.skipped_duplicates.length} duplicate(s),{' '}
            {importResult.errors.length} error(s).
            {importResult.errors.length > 0 && (
              <span className="ml-1 text-rose-700">{JSON.stringify(importResult.errors)}</span>
            )}
          </p>
        )}
      </Card>

      <Card title="Test cases">
        <div className="mb-3 flex flex-wrap gap-2">
          <input
            placeholder="search name/description"
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
          />
          <input
            placeholder="category"
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            value={filters.category}
            onChange={(e) => setFilters({ ...filters, category: e.target.value })}
          />
          <select
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            value={filters.severity}
            onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
          >
            <option value="">any severity</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            placeholder="tag"
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            value={filters.tag}
            onChange={(e) => setFilters({ ...filters, tag: e.target.value })}
          />
        </div>

        {cases === null ? (
          <Loading />
        ) : cases.length === 0 ? (
          <p className="text-sm italic text-slate-400">No test cases match.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1">Name</th>
                <th className="py-1">Category</th>
                <th className="py-1">Severity</th>
                <th className="py-1">Behavior</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {cases.map((tc) => (
                <tr key={tc.id} className="border-t border-slate-100">
                  <td className="py-2 pr-4 font-medium">{tc.name}</td>
                  <td className="py-2 pr-4">{tc.category}</td>
                  <td className="py-2 pr-4">
                    <StatusBadge status={tc.severity} />
                  </td>
                  <td className="py-2 pr-4 text-slate-500">{tc.behavior_type}</td>
                  <td className="py-2">
                    <button onClick={() => handleArchive(tc.id)} className="text-xs text-rose-600 hover:underline">
                      Archive
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Create a test case">
        {formError && <p className="mb-3 text-sm text-rose-700">{formError}</p>}
        <form onSubmit={handleCreate} className="space-y-3">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div>
              <label className="block text-xs font-medium text-slate-500">Name</label>
              <input
                required
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">Category</label>
              <input
                required
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">Severity</label>
              <select
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={form.severity}
                onChange={(e) => setForm({ ...form, severity: e.target.value })}
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">Behavior type</label>
              <select
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={form.behavior_type}
                onChange={(e) => setForm({ ...form, behavior_type: e.target.value })}
              >
                {BEHAVIORS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">Tags (comma-separated)</label>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-500">input_payload (JSON)</label>
              <textarea
                className="h-24 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
                value={form.input_payload}
                onChange={(e) => setForm({ ...form, input_payload: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">
                expected_output (JSON, required if behavior_type = exact_fields)
              </label>
              <textarea
                className="h-24 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
                value={form.expected_output}
                onChange={(e) => setForm({ ...form, expected_output: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">expected_evidence (JSON array)</label>
              <textarea
                className="h-20 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
                value={form.expected_evidence}
                onChange={(e) => setForm({ ...form, expected_evidence: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">evaluator_config (JSON)</label>
              <textarea
                className="h-20 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
                value={form.evaluator_config}
                onChange={(e) => setForm({ ...form, evaluator_config: e.target.value })}
              />
            </div>
          </div>
          <SecondaryButton type="submit">Create test case</SecondaryButton>
        </form>
      </Card>
    </div>
  )
}
