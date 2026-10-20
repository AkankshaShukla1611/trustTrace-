import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading, PrimaryButton } from '../components/common'
import StatusBadge from '../components/StatusBadge'

export default function Projects() {
  const [projects, setProjects] = useState(null)
  const [error, setError] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)

  async function load() {
    try {
      setProjects(await api.listProjects())
    } catch (err) {
      setError(err)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleCreate(e) {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    setError(null)
    try {
      await api.createProject({ name, description: description || null })
      setName('')
      setDescription('')
      await load()
    } catch (err) {
      setError(err)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-slate-900">Projects & Integrations</h2>
      <ErrorBanner error={error} />

      <Card title="Create a project">
        <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-500">Name</label>
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Acme Doc QA"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">Description</label>
            <input
              className="w-80 rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="optional"
            />
          </div>
          <PrimaryButton type="submit" disabled={creating || !name.trim()}>
            {creating ? 'Creating...' : 'Create project'}
          </PrimaryButton>
        </form>
      </Card>

      <Card title="All projects">
        {!projects ? (
          <Loading />
        ) : projects.length === 0 ? (
          <p className="text-sm italic text-slate-400">No projects yet -- create one above.</p>
        ) : (
          <div className="space-y-3">
            {projects.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className="block rounded-md border border-slate-200 p-4 hover:border-slate-400 hover:bg-slate-50"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-900">{project.name}</div>
                    {project.description && <div className="text-sm text-slate-500">{project.description}</div>}
                  </div>
                  <div className="flex gap-2">
                    {project.integrations.map((integration) => (
                      <StatusBadge key={integration.id} status={integration.status} />
                    ))}
                    {project.integrations.length === 0 && (
                      <span className="text-xs italic text-slate-400">no integrations configured</span>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
