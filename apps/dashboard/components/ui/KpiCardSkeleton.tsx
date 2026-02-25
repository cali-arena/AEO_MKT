import { motion } from "framer-motion";

export function KpiCardSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="card animate-pulse rounded-xl border border-gray-200 bg-white p-5"
    >
      <div className="h-4 w-24 rounded bg-gray-200" />
      <div className="mt-2 h-9 w-20 rounded bg-gray-200" />
      <div className="mt-3 h-8 w-full rounded bg-gray-100" />
    </motion.div>
  );
}
