"use client";

import Link from "next/link";
import { X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { EvalMetricsRates } from "@/lib/types";
import { MetricBadge } from "@/components/ui/MetricBadge";

interface DomainDrawerProps {
  domain: string | null;
  rates: EvalMetricsRates | null;
  basePath: string;
  onClose: () => void;
}

export function DomainDrawer({ domain, rates, basePath, onClose }: DomainDrawerProps) {
  return (
    <AnimatePresence>
      {domain && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 z-50 h-full w-full max-w-md border-l border-gray-200 bg-white shadow-xl"
          >
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
                <h2 className="text-lg font-semibold text-gray-900">{domain}</h2>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-5">
                {rates && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-medium uppercase tracking-wide text-gray-500">
                      KPIs
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs text-gray-500">Mention</p>
                        <MetricBadge type="mention" value={rates.mention_rate} className="mt-0.5" />
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Citation</p>
                        <MetricBadge type="citation" value={rates.citation_rate} className="mt-0.5" />
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Attribution</p>
                        <MetricBadge type="attribution" value={rates.attribution_rate} className="mt-0.5" />
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Hallucination</p>
                        <MetricBadge type="hallucination" value={rates.hallucination_rate} className="mt-0.5" />
                      </div>
                    </div>
                    <div className="pt-4">
                      <Link
                        href={`${basePath}/worst-queries?domain=${encodeURIComponent(domain)}`}
                        className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary/90"
                      >
                        View worst queries →
                      </Link>
                    </div>
                    <p className="text-xs text-gray-400">Trends and lead signals (future)</p>
                  </div>
                )}
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
