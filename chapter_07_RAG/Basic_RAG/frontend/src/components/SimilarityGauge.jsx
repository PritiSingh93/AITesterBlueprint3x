export default function SimilarityGauge({ value, labelA, labelB }) {
  const pct = Math.max(0, Math.min(1, value)) * 100

  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span className="truncate">{labelA}</span>
        <span className="truncate">{labelB}</span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 text-center text-sm font-semibold text-slate-700">
        cosine similarity: {value.toFixed(4)}
      </p>
    </div>
  )
}
