interface KpiCardProps {
  label: string;
  value: number;
  format?: "percent" | "number" | "decimal";
}

function formatValue(value: number, format: KpiCardProps["format"]): string {
  switch (format) {
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "decimal":
      return value.toFixed(2);
    default:
      return value.toString();
  }
}

export function KpiCard({
  label,
  value,
  format = "percent",
}: KpiCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">
        {formatValue(value, format)}
      </p>
    </div>
  );
}
