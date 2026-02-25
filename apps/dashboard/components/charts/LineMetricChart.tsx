"use client";

import { memo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
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

const gradientId = (title?: string, yKey?: string) =>
  `fill-${String(title ?? "")}-${String(yKey ?? "")}`;

function LineMetricChartInner({
  data,
  xKey,
  yKey,
  title,
  label,
  valueFormatter = (v) => (typeof v === "number" ? (v <= 1 ? `${(v * 100).toFixed(1)}%` : v.toFixed(2)) : String(v)),
  yDomain = [0, 1] as [number, number],
  yTickFormatter = (v) => (v <= 1 ? (v * 100).toFixed(0) + "%" : String(v)),
}: LineMetricChartProps) {
  const formatX = (ts: string | number) => {
    const d = new Date(String(ts));
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "2-digit" });
  };

  return (
    <div className="card p-5 transition-shadow duration-200 hover:shadow-card-hover">
      {title && (
        <h3 className="mb-4 text-lg font-medium text-gray-900">{title}</h3>
      )}
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <defs>
            <linearGradient id={gradientId(title, yKey)} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis
            dataKey={xKey}
            tickFormatter={formatX}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={{ stroke: "#e5e7eb" }}
          />
          <YAxis
            domain={yDomain}
            tickFormatter={yTickFormatter}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value: number) => [valueFormatter(value), label ?? yKey]}
            labelFormatter={formatX}
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e5e7eb",
              boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.08)",
            }}
          />
          <Area
            type="monotone"
            dataKey={yKey}
            stroke="#3B82F6"
            strokeWidth={2}
            fill={`url(#${gradientId(title, yKey)})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export const LineMetricChart = memo(LineMetricChartInner);
