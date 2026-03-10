"use client";

import { memo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface VisibilityGrowthPoint {
  run_id: string;
  ts: string;
  mention_rate: number;
  citation_rate: number;
  attribution_accuracy: number;
}

interface VisibilityGrowthChartProps {
  data: VisibilityGrowthPoint[];
}

function VisibilityGrowthChartInner({ data }: VisibilityGrowthChartProps) {
  const formatX = (ts: string | number) => {
    const d = new Date(String(ts));
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  const formatPct = (value: number) => `${(value * 100).toFixed(1)}%`;

  return (
    <div className="card p-5">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis
            dataKey="ts"
            tickFormatter={formatX}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={{ stroke: "#e5e7eb" }}
          />
          <YAxis
            domain={[0, 1]}
            tickFormatter={(v) => `${Math.round(v * 100)}%`}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value: number, name: string) => [formatPct(value), name]}
            labelFormatter={(label) => formatX(String(label))}
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e5e7eb",
              boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.08)",
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            type="monotone"
            dataKey="mention_rate"
            name="Mention rate"
            stroke="#2563EB"
            strokeWidth={2}
            dot={{ r: 2.5 }}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="citation_rate"
            name="Citation rate"
            stroke="#0F766E"
            strokeWidth={2}
            dot={{ r: 2.5 }}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="attribution_accuracy"
            name="Attribution accuracy"
            stroke="#7C3AED"
            strokeWidth={2}
            dot={{ r: 2.5 }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export const VisibilityGrowthChart = memo(VisibilityGrowthChartInner);

