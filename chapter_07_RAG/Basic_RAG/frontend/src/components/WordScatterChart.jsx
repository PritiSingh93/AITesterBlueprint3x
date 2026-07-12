import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const COLORS = ['#6366f1', '#ec4899', '#14b8a6', '#f59e0b', '#8b5cf6', '#0ea5e9', '#ef4444']

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow">
      <strong>{point.word}</strong>
      <div className="text-slate-500">
        x: {point.x.toFixed(3)}, y: {point.y.toFixed(3)}
      </div>
    </div>
  )
}

export default function WordScatterChart({ points, loading }) {
  if (loading) {
    return <p className="py-10 text-center text-sm text-slate-400">Computing projection…</p>
  }
  if (!points || points.length === 0) {
    return <p className="py-10 text-center text-sm text-slate-400">No data yet.</p>
  }

  return (
    <div>
      <div style={{ width: '100%', height: 320 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis type="number" dataKey="x" name="PC1" tick={{ fontSize: 11 }} />
            <YAxis type="number" dataKey="y" name="PC2" tick={{ fontSize: 11 }} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<ChartTooltip />} />
            <Scatter data={points} fill="#6366f1">
              {points.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {points.map((p, i) => (
          <span
            key={p.word}
            className="rounded-full px-2 py-0.5 text-xs font-medium text-white"
            style={{ backgroundColor: COLORS[i % COLORS.length] }}
          >
            {p.word}
          </span>
        ))}
      </div>
    </div>
  )
}
