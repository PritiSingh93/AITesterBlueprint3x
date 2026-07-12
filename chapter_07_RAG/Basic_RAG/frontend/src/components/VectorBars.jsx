export default function VectorBars({ values }) {
  const max = Math.max(...values.map((v) => Math.abs(v)), 0.001)

  return (
    <div className="flex h-24 items-end gap-0.5">
      {values.map((v, i) => {
        const height = Math.max(4, (Math.abs(v) / max) * 100)
        return (
          <div
            key={i}
            title={v.toFixed(4)}
            className={`w-2 rounded-t transition-all ${v >= 0 ? 'bg-brand-500' : 'bg-rose-400'}`}
            style={{ height: `${height}%` }}
          />
        )
      })}
    </div>
  )
}
