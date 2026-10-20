import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading, PrimaryButton, SecondaryButton } from '../components/common'
import StatusBadge from '../components/StatusBadge'

const ADAPTER_TYPES = ['mock', 'http', 'python', 'file']

export default function ProjectDetail() {
  const { projectId } = useParams()
  const [project, setProject] = useState(null)
  const [datasets, setDatasets] = useState(null)
  const [packs, setPacks] = useState(null)
  const [error, setError] = useState(null)

  const [integrationName, setIntegrationName] = useState('')
  const [adapterType, setAdapterType] = useState('mock')
  const [configText, setConfigText] = useState('{}')

  const [datasetName, setDatasetName] = useState('')
  const [packId, setPackId] = useState('')
  const [newPackSlug, setNewPackSlug] = useState('')
  const [newPackName, setNewPackName] = useState('')

  async function load() {
    try {
      const [p, d, packList] = await Promise.all([
        api.getProject(projectId),
        api.listDatasets(projectId),
        api.listEvaluationPacks(),
      ])
      setProject(p)
      setDatasets(d)
      setPacks(packList)
      if (packList.length > 0 && !packId) setPackId(packList[0].id)
    } catch (err) {
      setError(err)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  async function handleCreateIntegration(e) {
    e.preventDefault()
    setError(null)
    let config
    try {
      config = JSON.parse(configText)
    } catch {
      setError(new Error('Config must be valid JSON'))
      return
    }
    try {
      await api.createIntegration(projectId, { name: integrationName, adapter_type: adapterType, config })
      setIntegrationName('')
      setConfigText('{}')
      await load()
    } catch (err) {
      setError(err)
    }
  }

  async function handleValidate(integrationId) {
    setError(null)
    try {
      await api.validateIntegration(integrationId)
      await load()
    } catch (err) {
      setError(err)
    }
  }

  async function handleCreatePack(e) {
    e.preventDefault()
    if (!newPackSlug.trim() || !newPackName.trim()) return
    setError(null)
    try {
      const pack = await api.createEvaluationPack({ slug: newPackSlug, name: newPackName })
      setNewPackSlug('')
      setNewPackName('')
      await load()
      setPackId(pack.id)
    } catch (err) {
      setError(err)
    }
  }

  async function handleCreateDataset(e) {
    e.preventDefault()
    if (!datasetName.trim() || !packId) return
    setError(null)
    try {
      await api.createDataset(projectId, { name: datasetName, evaluation_pack_id: packId })
      setDatasetName('')
      await load()
    } catch (err) {
      setError(err)
    }
  }

  if (error) return <ErrorBanner error={error} />
  if (!project) return <Loading />

  return (
    <div className="space-y-6">
      <div>
        <Link to="/projects" className="text-sm text-sky-700 hover:underline">
          &larr; All projects
        </Link>
        <h2 className="text-xl font-bold text-slate-900">{project.name}</h2>
        {project.description && <p className="text-sm text-slate-500">{project.description}</p>}
      </div>

      <ErrorBanner error={error} />

      <Card title="Integrations">
        {project.integrations.length === 0 && (
          <p className="mb-3 text-sm italic text-slate-400">No integrations yet.</p>
        )}
        <div className="mb-4 space-y-2">
          {project.integrations.map((integration) => (
            <div
              key={integration.id}
              className="flex items-center justify-between rounded-md border border-slate-200 p-3"
            >
              <div>
                <div className="font-medium text-slate-900">{integration.name}</div>
                <div className="text-xs text-slate-500">
                  adapter: {integration.adapter_type} &middot; capabilities:{' '}
                  {Object.entries(integration.capabilities || {})
                    .filter(([, v]) => v)
                    .map(([k]) => k)
                    .join(', ') || 'none declared'}
                </div>
                {integration.last_validation_message && (
                  <div className="text-xs text-slate-400">{integration.last_validation_message}</div>
                )}
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={integration.status} />
                <SecondaryButton onClick={() => handleValidate(integration.id)}>Validate</SecondaryButton>
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={handleCreateIntegration} className="flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
          <div>
            <label className="block text-xs font-medium text-slate-500">Name</label>
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={integrationName}
              onChange={(e) => setIntegrationName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">Adapter type</label>
            <select
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={adapterType}
              onChange={(e) => setAdapterType(e.target.value)}
            >
              {ADAPTER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">Config (JSON)</label>
            <input
              className="w-80 rounded-md border border-slate-300 px-3 py-2 text-sm font-mono"
              value={configText}
              onChange={(e) => setConfigText(e.target.value)}
            />
          </div>
          <PrimaryButton type="submit" disabled={!integrationName.trim()}>
            Add integration
          </PrimaryButton>
        </form>
      </Card>

      <Card title="Datasets">
        {datasets === null ? (
          <Loading />
        ) : (
          <div className="mb-4 space-y-2">
            {datasets.length === 0 && <p className="text-sm italic text-slate-400">No datasets yet.</p>}
            {datasets.map((dataset) => (
              <Link
                key={dataset.id}
                to={`/datasets/${dataset.id}`}
                className="block rounded-md border border-slate-200 p-3 hover:border-slate-400 hover:bg-slate-50"
              >
                <div className="font-medium text-slate-900">{dataset.name}</div>
                {dataset.description && <div className="text-xs text-slate-500">{dataset.description}</div>}
              </Link>
            ))}
          </div>
        )}

        <form onSubmit={handleCreateDataset} className="flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
          <div>
            <label className="block text-xs font-medium text-slate-500">Dataset name</label>
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">Evaluation pack</label>
            <select
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={packId}
              onChange={(e) => setPackId(e.target.value)}
            >
              {(packs || []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.slug})
                </option>
              ))}
            </select>
          </div>
          <PrimaryButton type="submit" disabled={!datasetName.trim() || !packId}>
            Create dataset
          </PrimaryButton>
        </form>
        <form onSubmit={handleCreatePack} className="mt-3 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
          <div>
            <label className="block text-xs font-medium text-slate-500">New evaluation pack: slug</label>
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={newPackSlug}
              onChange={(e) => setNewPackSlug(e.target.value)}
              placeholder="e.g. my_app_pack"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">Name</label>
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={newPackName}
              onChange={(e) => setNewPackName(e.target.value)}
            />
          </div>
          <SecondaryButton type="submit" disabled={!newPackSlug.trim() || !newPackName.trim()}>
            Create evaluation pack
          </SecondaryButton>
        </form>
      </Card>

      <div>
        <Link to={`/runs/new?project_id=${projectId}`}>
          <PrimaryButton>Create a run for this project</PrimaryButton>
        </Link>
      </div>
    </div>
  )
}
