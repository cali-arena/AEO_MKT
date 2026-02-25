"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

interface KpiCardProps {
  label: string;
  value: number;
  format?: "percent" | "number" | "decimal";
  trend?: number | null;
  sparklineData?: number[];
  accent?: "primary" | "success" | "warning" | "error" | "neutral";
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

const ACCENT_STYLES: Record<string, string> = {
  primary: "border-l-accent bg-blue-50/50",
  success: "border-l-emerald-500 bg-emerald-50/50",
  warning: "border-l-amber-500 bg-amber-50/50",
  error: "border-l-rose-500 bg-rose-50/50",
  neutral: "border-l-gray-300 bg-gray-50/50",
};

export function KpiCard({
  label,
  value,
  format = "percent",
  trend = null,
  sparklineData,
  accent = "primary",
}: KpiCardProps) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const num = typeof value === "number" && !Number.isNaN(value) ? value : 0;
    const start = displayValue;
    const duration = 600;
    const startTime = performance.now();
    const tick = (now: number) => {
      const elapsed = now - startTime;
      const t = Math.min(elapsed / duration, 1);
      const eased = 1 - (1 - t) * (1 - t);
      setDisplayValue(start + (num - start) * eased);
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [value]);

  const displayStr =
    format === "percent"
      ? `${(displayValue * 100).toFixed(1)}%`
      : format === "decimal"
        ? displayValue.toFixed(2)
        : Math.round(displayValue).toString();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`card border-l-4 p-5 ${ACCENT_STYLES[accent] ?? ACCENT_STYLES.neutral}`}
    >
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <div className="mt-1 flex items-baseline justify-between gap-2">
        <p className="text-3xl font-bold tracking-tight text-gray-900">
          {displayStr}
        </p>
        {trend != null && !Number.isNaN(trend) && (
          <span
            className={`text-sm font-medium ${
              trend >= 0 ? "text-emerald-600" : "text-rose-600"
            }`}
          >
            {trend >= 0 ? "▲" : "▼"} {Math.abs(trend).toFixed(1)}%
          </span>
        )}
      </div>
      {sparklineData && sparklineData.length > 0 && (
        <MiniSparkline data={sparklineData} />
      )}
    </motion.div>
  );
}

function MiniSparkline({ data }: { data: number[] }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 100 / (data.length - 1 || 1);
  const points = data
    .map((v, i) => `${(i * w).toFixed(2)},${(100 - ((v - min) / range) * 100).toFixed(2)}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="mt-3 h-8 w-full">
      <defs>
        <linearGradient id="sparkline-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline fill="none" stroke="#3B82F6" strokeWidth="2" points={points} />
      <polygon fill="url(#sparkline-fill)" points={`0,100 ${points} 100,100`} />
    </svg>
  );
}
