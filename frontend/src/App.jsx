import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Projects from './pages/Projects'
import ProjectDetail from './pages/ProjectDetail'
import DocumentCollection from './pages/DocumentCollection'
import DatasetDetail from './pages/DatasetDetail'
import Runs from './pages/Runs'
import RunNew from './pages/RunNew'
import RunDetail from './pages/RunDetail'
import RegressionCompare from './pages/RegressionCompare'
import EvaluationMethodology from './pages/EvaluationMethodology'
import Reports from './pages/Reports'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:projectId" element={<ProjectDetail />} />
          <Route path="/projects/:projectId/documents" element={<DocumentCollection />} />
          <Route path="/datasets/:datasetId" element={<DatasetDetail />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/new" element={<RunNew />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/regression" element={<RegressionCompare />} />
          <Route path="/methodology" element={<EvaluationMethodology />} />
          <Route path="/reports" element={<Reports />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
