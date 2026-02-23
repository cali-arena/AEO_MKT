"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export interface LineMetricChartProps {
  data: Array<Record<string, string | number>>;
  xKey: string;
  yKey: string;
  title?: string;
  label?: string;
  valueFormatter?: (value: number) => string;
  yDomain?: [number | "auto", number | "auto"];
  yTickFormatter?: (value: number) => string;
}

export function LineMetricChart({
  data,
  xKey,
  yKey,
  title,
  label,
  valueFormatter = (v) => (typeof v === "number" ? v.toFixed(2) : String(v)),
  yDomain = [0, 1] as [number, number],
  yTickFormatter = (v) => (v * 100).toFixed(0) + "%",
}: LineMetricChartProps) {
  const formatX = (ts: string | number) => {
    const d = new Date(String(ts));
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "2-digit" });
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      {title && <h3 className="mb-4 text-sm font-semibold text-gray-900">{title}</h3>}
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey={xKey}
            tickFormatter={formatX}
            tick={{ fontSize: 12 }}
            stroke="#9ca3af"
          />
          <YAxis
            domain={yDomain}
            tickFormatter={yTickFormatter}
            tick={{ fontSize: 12 }}
            stroke="#9ca3af"
          />
          <Tooltip
            formatter={(value: number) => [valueFormatter(value), label ?? yKey]}
            labelFormatter={formatX}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey={yKey}
            name={label ?? yKey}
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
