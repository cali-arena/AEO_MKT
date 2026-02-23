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
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-900">Last run</h3>
      <dl className="mt-3 space-y-2 text-sm">
        <div>
          <dt className="text-gray-500">Created</dt>
          <dd className="font-medium text-gray-900">{formatDate(created_at)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Crawl policy version</dt>
          <dd className="font-mono text-gray-900">{crawl_policy_version}</dd>
        </div>
        <div>
          <dt className="text-gray-500">AC version hash</dt>
          <dd className="truncate font-mono text-xs text-gray-900" title={ac_version_hash}>
            {ac_version_hash}
          </dd>
        </div>
        <div>
          <dt className="text-gray-500">EC version hash</dt>
          <dd className="truncate font-mono text-xs text-gray-900" title={ec_version_hash}>
            {ec_version_hash}
          </dd>
        </div>
      </dl>
    </div>
  );
}
