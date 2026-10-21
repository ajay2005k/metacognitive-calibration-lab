export default function MetricCard({ label, value, note }) {
  return (
    <div className="panel p-5">
      <p className="text-xs font-medium text-muted">{label}</p>
      <p
        className={`mt-3 font-semibold tracking-tight ${value === "not enough variation" ? "text-sm text-muted" : "text-3xl"}`}
      >
        {value}
      </p>
      {note && <p className="mt-2 text-xs text-muted">{note}</p>}
    </div>
  );
}
