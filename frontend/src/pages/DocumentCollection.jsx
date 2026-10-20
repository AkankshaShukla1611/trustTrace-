import { Fragment, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorBanner, Loading } from '../components/common'
import StatusBadge from '../components/StatusBadge'

export default function DocumentCollection() {
  const { projectId } = useParams()
  const [documents, setDocuments] = useState(null)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [expandedId, setExpandedId] = useState(null)
  const [expandedDoc, setExpandedDoc] = useState(null)

  async function load() {
    try {
      setDocuments(await api.listDocuments(projectId))
    } catch (err) {
      setError(err)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  async function handleUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await api.uploadDocument(projectId, file)
      await load()
    } catch (err) {
      setError(err)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  async function handleExpand(docId) {
    if (expandedId === docId) {
      setExpandedId(null)
      setExpandedDoc(null)
      return
    }
    setExpandedId(docId)
    setError(null)
    try {
      setExpandedDoc(await api.getDocument(docId))
    } catch (err) {
      setError(err)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/projects/${projectId}`} className="text-sm text-sky-700 hover:underline">
          &larr; Project
        </Link>
        <h2 className="text-xl font-bold text-slate-900">Document Collection</h2>
        <p className="text-sm text-slate-500">
          Upload PDF, TXT, or JSON fixtures. PDFs are read with native text extraction first; a scanned/image PDF
          falls back to OCR only if an OCR provider key is configured on the backend -- otherwise it's saved with an
          honest "partial" status rather than pretended to be fully read.
        </p>
      </div>

      <ErrorBanner error={error} />

      <Card title="Upload a document">
        <input type="file" accept=".pdf,.txt,.json" disabled={uploading} onChange={handleUpload} className="text-sm" />
        {uploading && <p className="mt-2 text-sm text-slate-500">Uploading and extracting...</p>}
      </Card>

      <Card title={`Documents (${documents?.length ?? '...'})`}>
        {documents === null ? (
          <Loading />
        ) : documents.length === 0 ? (
          <p className="text-sm italic text-slate-400">No documents uploaded yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1">Filename</th>
                <th className="py-1">Type</th>
                <th className="py-1">Pages</th>
                <th className="py-1">Extraction</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <Fragment key={doc.id}>
                  <tr
                    onClick={() => handleExpand(doc.id)}
                    className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                  >
                    <td className="py-2 pr-4 font-medium">{doc.filename}</td>
                    <td className="py-2 pr-4 text-slate-500">{doc.doc_type}</td>
                    <td className="py-2 pr-4">{doc.page_count}</td>
                    <td className="py-2 pr-4">
                      <StatusBadge status={doc.extraction_status} />
                    </td>
                    <td className="py-2 text-sky-700">{expandedId === doc.id ? 'hide' : 'view'}</td>
                  </tr>
                  {expandedId === doc.id && (
                    <tr>
                      <td colSpan={5} className="bg-slate-50 p-4">
                        {!expandedDoc ? (
                          <Loading />
                        ) : (
                          <>
                            {expandedDoc.extraction_notes && (
                              <p className="mb-3 text-xs text-amber-700">{expandedDoc.extraction_notes}</p>
                            )}
                            <div className="space-y-2">
                              {expandedDoc.pages.map((page) => (
                                <div key={page.page_number} className="rounded border border-slate-200 bg-white p-2">
                                  <div className="mb-1 text-xs font-semibold text-slate-500">
                                    Page {page.page_number}
                                  </div>
                                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                                    {page.text || '(empty)'}
                                  </pre>
                                </div>
                              ))}
                            </div>
                          </>
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
