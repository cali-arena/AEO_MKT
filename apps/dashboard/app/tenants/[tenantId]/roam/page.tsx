"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  CheckCircle,
  Clock,
  FileText,
  Package,
  Radio,
  RefreshCw,
  Truck,
  Upload,
  XCircle,
} from "lucide-react";

import {
  fetchBolUploads,
  fetchJobs,
  fetchRoamStatus,
  fetchShipments,
  fetchSourceMessages,
  triggerRoamSync,
  uploadBol,
  ApiError,
} from "@/lib/api";
import type {
  BolUpload,
  ParsedJob,
  RoamStatus,
  Shipment,
  SourceMessage,
} from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";

// ---------------------------------------------------------------------------
// Real-time polling primitive
// ---------------------------------------------------------------------------

/**
 * Periodically invoke `fn`. Pauses when the tab is backgrounded
 * (document.hidden) and triggers an immediate refetch when the window
 * regains focus. Keeps the polling lightweight on idle tabs.
 */
function usePolling(fn: () => void | Promise<void>, intervalMs: number, deps: unknown[] = []) {
  // Always read the latest fn without restarting the interval.
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;

    const start = () => {
      if (timer != null) return;
      timer = setInterval(() => {
        if (!document.hidden) void fnRef.current();
      }, intervalMs);
    };
    const stop = () => {
      if (timer != null) {
        clearInterval(timer);
        timer = null;
      }
    };
    const onVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        void fnRef.current();
        start();
      }
    };
    const onFocus = () => {
      void fnRef.current();
    };

    void fnRef.current();
    start();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", onFocus);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", onFocus);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps]);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const POLL_MS = 10_000;

function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString();
  } catch {
    return s;
  }
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    parsed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    low_confidence: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    no_match: "bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-400",
    ok: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    running: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
    partial: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    error: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    extracted: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    pending_ocr: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    uploaded: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        cls[status] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {status}
    </span>
  );
}

function SectionHeader({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: React.ElementType;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-4 flex items-center gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-800 text-accent">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-slate-100">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
    </div>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-700/60 bg-slate-800/50 p-5 ${className}`}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Roam Sync Status (polled)
// ---------------------------------------------------------------------------

function RoamSection() {
  const [status, setStatus] = useState<RoamStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const s = await fetchRoamStatus();
      setStatus(s);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  usePolling(load, POLL_MS);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const r = await triggerRoamSync();
      setSyncResult(
        `Sync complete: ${r.processed ?? 0} new, ${r.skipped ?? 0} skipped, ${r.failed ?? 0} failed.`
      );
      await load();
    } catch (e) {
      setSyncResult(`Sync failed: ${e instanceof ApiError ? e.message : String(e)}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <section className="mb-8">
      <SectionHeader
        icon={Activity}
        title="Roam Sync"
        subtitle="Live status — polls /crawler/integrations/roam/status every 10 s"
      />
      <Card>
        {loading ? (
          <div className="h-20 animate-pulse rounded bg-slate-700/40" />
        ) : error ? (
          <p className="text-sm text-rose-400">{error}</p>
        ) : status ? (
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-slate-500">Configured</dt>
                <dd className="flex items-center gap-1 font-medium text-slate-100">
                  {status.configured ? (
                    <>
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-400" /> Yes
                    </>
                  ) : (
                    <>
                      <XCircle className="h-3.5 w-3.5 text-rose-400" /> No
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Workspace ID</dt>
                <dd className="font-medium text-slate-100">
                  {status.workspace_id || (
                    <span className="text-amber-400">not set</span>
                  )}
                </dd>
              </div>
              {status.poll_interval_seconds != null && (
                <div>
                  <dt className="text-slate-500">Poll interval</dt>
                  <dd className="font-medium text-slate-100">
                    {status.poll_interval_seconds}s
                  </dd>
                </div>
              )}
              {status.last_run && (
                <>
                  <div>
                    <dt className="text-slate-500">Last run</dt>
                    <dd className="font-medium text-slate-100">
                      <StatusBadge status={status.last_run.status} />
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Processed</dt>
                    <dd className="font-medium text-slate-100">
                      {status.last_run.processed} new / {status.last_run.skipped} dup
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Started</dt>
                    <dd className="font-medium text-slate-100">
                      {fmtDate(status.last_run.started_at)}
                    </dd>
                  </div>
                </>
              )}
            </dl>
            <div className="flex flex-col items-start gap-2">
              <button
                onClick={handleSync}
                disabled={syncing || !status.configured}
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
                {syncing ? "Syncing…" : "Sync Now"}
              </button>
              {!status.configured && (
                <p className="text-xs text-slate-500">Set ROAM_API_TOKEN to enable</p>
              )}
              {syncResult && (
                <p className="max-w-xs text-xs text-slate-400">{syncResult}</p>
              )}
            </div>
          </div>
        ) : null}
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section: Source Messages (polled)
// ---------------------------------------------------------------------------

function SourceMessagesSection() {
  const [messages, setMessages] = useState<SourceMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetchSourceMessages(20);
      setMessages(r.messages);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  usePolling(load, POLL_MS);

  return (
    <section className="mb-8">
      <SectionHeader
        icon={Clock}
        title="Source Messages"
        subtitle="Latest 20 from /crawler/source-messages?source=roam (auto-refresh)"
      />
      <Card className="overflow-hidden p-0">
        {loading ? (
          <div className="h-40 animate-pulse rounded-xl bg-slate-700/40" />
        ) : error ? (
          <div className="p-5">
            <p className="text-sm text-rose-400">{error}</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="p-5">
            <EmptyState
              icon={<Clock className="h-6 w-6" />}
              title="No messages yet"
              description="Trigger a Roam sync to ingest messages."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700/60 bg-slate-800/80">
                  {["ID", "Source ID", "Chat ID", "Received", "Processed"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-slate-500"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/40">
                {messages.map((m) => (
                  <tr key={m.id} className="transition-colors hover:bg-slate-700/20">
                    <td className="px-4 py-2 font-mono text-xs text-slate-400">{m.id}</td>
                    <td className="max-w-[180px] truncate px-4 py-2 font-mono text-xs text-slate-300">
                      {m.source_id}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">{m.chat_id || "—"}</td>
                    <td className="whitespace-nowrap px-4 py-2 text-xs text-slate-400">
                      {fmtDate(m.received_at)}
                    </td>
                    <td className="px-4 py-2">
                      <StatusBadge status={m.processed ? "extracted" : "pending_ocr"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section: BOL Upload (on-demand refresh after upload)
// ---------------------------------------------------------------------------

function BolSection() {
  const [uploads, setUploads] = useState<BolUpload[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadUploads = useCallback(async () => {
    try {
      const r = await fetchBolUploads(10);
      setUploads(r.uploads);
    } catch {
      // non-fatal
    }
  }, []);

  useEffect(() => {
    void loadUploads();
  }, [loadUploads]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg(null);
    setError(null);
    try {
      const r = await uploadBol(file);
      setUploadMsg(`Uploaded: ${r.filename} (${r.status})`);
      if (fileRef.current) fileRef.current.value = "";
      await loadUploads();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <section className="mb-8">
      <SectionHeader
        icon={FileText}
        title="BOL Upload"
        subtitle="Upload PDF / image — text extracted automatically"
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleUpload} className="flex flex-col gap-3">
            <label className="block">
              <span className="text-xs font-medium text-slate-400">
                File (PDF, PNG, JPG — max 20 MB)
              </span>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                className="mt-1.5 block w-full text-sm text-slate-400
                  file:mr-3 file:cursor-pointer file:rounded-lg
                  file:border-0 file:bg-slate-700 file:px-3 file:py-1.5
                  file:text-sm file:font-medium file:text-slate-200
                  hover:file:bg-slate-600"
              />
            </label>
            <button
              type="submit"
              disabled={uploading}
              className="flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Upload className={`h-4 w-4 ${uploading ? "animate-bounce" : ""}`} />
              {uploading ? "Uploading…" : "Upload"}
            </button>
            {uploadMsg && <p className="text-xs text-emerald-400">{uploadMsg}</p>}
            {error && <p className="text-xs text-rose-400">{error}</p>}
          </form>
        </Card>

        <Card className="overflow-hidden p-0">
          <p className="border-b border-slate-700/60 px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">
            Recent uploads
          </p>
          {uploads.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-slate-500">
              No uploads yet
            </div>
          ) : (
            <ul className="divide-y divide-slate-700/40">
              {uploads.map((u) => (
                <li
                  key={u.id}
                  className="flex items-center justify-between px-4 py-2.5 text-sm"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-200">{u.filename}</p>
                    <p className="text-xs text-slate-500">
                      {fmtBytes(u.file_size)} · {fmtDate(u.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={u.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section: Jobs & Shipments (on-demand)
// ---------------------------------------------------------------------------

function JobsShipmentsSection() {
  const [jobs, setJobs] = useState<ParsedJob[]>([]);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [jobCount, setJobCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchJobs(20), fetchShipments(10)])
      .then(([j, s]) => {
        if (cancelled) return;
        setJobs(j.jobs);
        setJobCount(j.count);
        setShipments(s.shipments);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="mb-8">
      <SectionHeader
        icon={Package}
        title="Jobs & Shipments"
        subtitle={`${jobCount} parsed jobs total — latest 20 shown`}
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="overflow-hidden p-0">
          <p className="border-b border-slate-700/60 px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">
            Parsed Jobs (latest 20)
          </p>
          {loading ? (
            <div className="h-40 animate-pulse bg-slate-700/40" />
          ) : jobs.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-slate-500">
              No jobs yet — run POST /jobs/parse
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700/60 bg-slate-800/80">
                    {["Ref", "Carrier", "Status", "Conf", "Source"].map((h) => (
                      <th
                        key={h}
                        className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-500"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/40">
                  {jobs.map((j) => (
                    <tr key={j.id} className="transition-colors hover:bg-slate-700/20">
                      <td className="px-3 py-2 font-mono text-xs text-slate-300">
                        {j.shipment_reference || "—"}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-400">
                        {j.carrier_name || "—"}
                      </td>
                      <td className="px-3 py-2">
                        <StatusBadge status={j.parsing_status} />
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-400">
                        {(j.confidence_score * 100).toFixed(0)}%
                      </td>
                      <td className="max-w-[80px] truncate px-3 py-2 text-xs text-slate-500">
                        {j.source_type === "roam_message" ? "Roam" : "BOL"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="overflow-hidden p-0">
          <p className="border-b border-slate-700/60 px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">
            Shipments (latest 10)
          </p>
          {loading ? (
            <div className="h-40 animate-pulse bg-slate-700/40" />
          ) : shipments.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-slate-500">
              No shipments extracted yet
            </div>
          ) : (
            <ul className="divide-y divide-slate-700/40">
              {shipments.map((s) => (
                <li key={s.id} className="px-4 py-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-sm font-medium text-slate-200">
                        {s.shipment_reference}
                      </p>
                      <p className="text-xs text-slate-500">
                        {[s.carrier_name, s.origin, s.destination]
                          .filter(Boolean)
                          .join(" · ") || "No details extracted"}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
                      <Truck className="h-3.5 w-3.5" />
                      {s.pickup_date || "—"}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

export default function RoamRealtimePage() {
  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="h-5 w-5 text-emerald-400" />
            <h1 className="text-xl font-bold text-slate-100">ROAM — Real Time</h1>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-300 ring-1 ring-emerald-500/30">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
              </span>
              Live
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Roam sync · BOL upload · parsed jobs and shipments · status &amp; messages
            auto-refresh every {POLL_MS / 1000}s.
          </p>
        </div>
      </div>

      <RoamSection />
      <SourceMessagesSection />
      <BolSection />
      <JobsShipmentsSection />
    </div>
  );
}
