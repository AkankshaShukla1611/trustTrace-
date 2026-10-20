import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, PrimaryButton } from '../components/common'

export default function RunNew() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState(searchParams.get('project_id') || '')
  const [integrations, setIntegrations] = useState([])
  const [integrationId, setIntegrationId] = useState('')
  const [datasetVersions, setDatasetVersions] = useState([])
  const [datasetVersionId, setDatasetVersionId] = useState(searchParams.get('dataset_version_id') || '')
  const [label, setLabel] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.listProjects().then(setProjects).catch(setError)
  }, [])

  // React Router reuses this component instance across navigations to the
  // same path with different query params, so the useState initial values
  // above only apply on the very first mount -- re-sync whenever the URL's
  // query params actually change (e.g. navigating here again from a
  // different dataset's "run this version" link).
  useEffect(() => {
    const nextProjectId = searchParams.get('project_id')
    const nextDatasetVersionId = searchParams.get('dataset_version_id')
    if (nextProjectId) setProjectId(nextProjectId)
    if (nextDatasetVersionId) setDatasetVersionId(nextDatasetVersionId)
  }, [searchParams])

  useEffect(() => {
    if (!projectId) {
      setIntegrations([])
      setDatasetVersions([])
      return
    }
    api
      .getProject(projectId)
      .then((p) => setIntegrations(p.integrations))
      .catch(setError)
    api
      .listDatasets(projectId)
      .then(async (datasets) => {
        const allVersions = await Promise.all(datasets.map((d) => api.listDatasetVersions(d.id)))
        setDatasetVersions(
          allVersions.flat().map((v) => ({ ...v, datasetName: datasets.find((d) => d.id === v.dataset_id)?.name }))
        )
      })
      .catch(setError)
  }, [projectId])

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const run = await api.createRun({
        project_id: projectId,
        integration_id: integrationId,
        dataset_version_id: datasetVersionId,
        label: label || null,
      })
      navigate(`/runs/${run.id}`)
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <h2 className="text-xl font-bold text-slate-900">Create a run</h2>
      <ErrorBanner error={error} />
      <Card>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-500">Project</label>
            <select
              required
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            >
              <option value="">select a project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500">Integration</label>
            <select
              required
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={integrationId}
              onChange={(e) => setIntegrationId(e.target.value)}
              disabled={!projectId}
            >
              <option value="">select an integration</option>
              {integrations.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name} ({i.adapter_type})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500">Dataset version</label>
            <select
              required
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={datasetVersionId}
              onChange={(e) => setDatasetVersionId(e.target.value)}
              disabled={!projectId}
            >
              <option value="">select a dataset version</option>
              {datasetVersions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.datasetName} -- v{v.version_number} ({v.test_case_count} cases)
                </option>
              ))}
            </select>
            {projectId && datasetVersions.length === 0 && (
              <p className="mt-1 text-xs text-slate-400">
                No dataset versions yet -- snapshot one from a dataset's page first.
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500">Label (optional)</label>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>

          <PrimaryButton type="submit" disabled={submitting || !projectId || !integrationId || !datasetVersionId}>
            {submitting ? 'Running...' : 'Run now'}
          </PrimaryButton>
        </form>
      </Card>
    </div>
  )
}
