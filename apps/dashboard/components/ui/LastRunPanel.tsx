import { Calendar, Hash } from "lucide-react";

interface LastRunPanelProps {
  created_at: string;
  crawl_policy_version: string;
  ac_version_hash: string;
  ec_version_hash: string;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function LastRunPanel({
  created_at,
  crawl_policy_version,
  ac_version_hash,
  ec_version_hash,
}: LastRunPanelProps) {
  return (
    <div className="card p-5">
      <h3 className="text-lg font-medium text-gray-900">Last run</h3>
      <dl className="mt-4 space-y-3 text-sm">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-gray-400" />
          <div>
            <dt className="text-gray-500">Created</dt>
            <dd className="font-medium text-gray-900">{formatDate(created_at)}</dd>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Hash className="h-4 w-4 text-gray-400" />
          <div>
            <dt className="text-gray-500">Crawl policy</dt>
            <dd className="font-mono text-gray-900">{crawl_policy_version}</dd>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Hash className="h-4 w-4 text-gray-400" />
          <div>
            <dt className="text-gray-500">AC / EC version</dt>
            <dd className="truncate font-mono text-xs text-gray-600" title={`AC: ${ac_version_hash} EC: ${ec_version_hash}`}>
              {ac_version_hash.slice(0, 8)}… / {ec_version_hash.slice(0, 8)}…
            </dd>
          </div>
        </div>
      </dl>
    </div>
  );
}
