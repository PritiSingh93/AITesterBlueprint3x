import DocumentPanel from './DocumentPanel.jsx'
import PipelineFlow from './PipelineFlow.jsx'
import QueryPanel from './QueryPanel.jsx'

export default function RagFlowTab() {
  return (
    <div>
      <PipelineFlow />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DocumentPanel />
        <QueryPanel />
      </div>
    </div>
  )
}
