import { motion } from "framer-motion";

export function LastRunPanelSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="card animate-pulse rounded-xl border border-gray-200 bg-white p-5"
    >
      <div className="h-5 w-24 rounded bg-gray-200" />
      <div className="mt-4 space-y-3">
        <div className="h-4 w-32 rounded bg-gray-100" />
        <div className="h-4 w-40 rounded bg-gray-100" />
        <div className="h-4 w-48 rounded bg-gray-100" />
      </div>
    </motion.div>
  );
}
