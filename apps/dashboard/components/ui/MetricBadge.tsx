interface MetricBadgeProps {
  value: number;
  type: "mention" | "citation" | "attribution" | "hallucination";
  className?: string;
}

export function MetricBadge({ value, type, className = "" }: MetricBadgeProps) {
  const pct = type === "hallucination" ? value * 100 : value * 100;
  const label = pct.toFixed(1) + "%";
  let style = "bg-gray-100 text-gray-700";
  if (type === "hallucination") {
    if (value > 0) style = "bg-rose-100 text-rose-800 font-medium";
  } else if (type === "mention") {
    if (pct < 50) style = "bg-rose-100 text-rose-800";
    else if (pct >= 80) style = "bg-emerald-100 text-emerald-800";
  } else if (type === "citation") {
    if (pct < 70) style = "bg-amber-100 text-amber-800";
    else if (pct >= 90) style = "bg-emerald-100 text-emerald-800";
  } else {
    if (pct < 70) style = "bg-amber-100 text-amber-800";
    else if (pct >= 90) style = "bg-emerald-100 text-emerald-800";
  }
  return (
    <span
      className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${style} ${className}`}
    >
      {label}
    </span>
  );
}
