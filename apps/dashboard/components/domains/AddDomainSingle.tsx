"use client";

import { useState, useCallback } from "react";
import { Loader2, Plus } from "lucide-react";

export type ValidateDomainResult =
  | { valid: true; normalized: string }
  | { valid: false; error: string };

export function validateDomain(domain: string): ValidateDomainResult {
  const raw = domain.trim();
  if (!raw) return { valid: false, error: "Enter a domain" };
  let normalized = raw
    .replace(/^https?:\/\//i, "")
    .replace(/\/.*$/, "")
    .trim()
    .toLowerCase();
  if (!normalized) return { valid: false, error: "Enter a valid domain" };
  const hostnameRegex = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$/i;
  if (!hostnameRegex.test(normalized)) {
    return { valid: false, error: "Use a valid domain (e.g. example.com)" };
  }
  return { valid: true, normalized };
}

interface AddDomainSingleProps {
  onAdd: (domain: string) => Promise<void>;
  disabled?: boolean;
  existingDomains?: Set<string>;
}

export function AddDomainSingle({
  onAdd,
  disabled = false,
  existingDomains = new Set(),
}: AddDomainSingleProps) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showToast = useCallback((type: "success" | "error", message: string) => {
    setToast({ type, message });
    const t = window.setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, []);

  const handleSubmit = useCallback(async () => {
    const result = validateDomain(value);
    setValidationError(null);
    if (!result.valid) {
      setValidationError(result.error);
      return;
    }
    const { normalized } = result;
    if (existingDomains.has(normalized)) {
      setValidationError("Domain is already in the table");
      return;
    }
    setLoading(true);
    try {
      await onAdd(normalized);
      setValue("");
      showToast("success", "Domain added. Evaluation started.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to add domain";
      showToast("error", message);
    } finally {
      setLoading(false);
    }
  }, [value, onAdd, existingDomains, showToast]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="example.com"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setValidationError(null);
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled || loading}
          className="min-w-[200px] flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60 dark:border-slate-600 dark:bg-slate-800 dark:placeholder:text-slate-500"
          aria-label="Domain to add"
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={disabled || loading || !value.trim()}
          title="Adds and starts evaluation immediately"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Plus className="h-4 w-4" aria-hidden />
          )}
          <span>{loading ? "Adding…" : "Add Domain"}</span>
        </button>
      </div>
      {validationError && (
        <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">
          {validationError}
        </p>
      )}
      {toast && (
        <div
          role="status"
          className={`rounded-lg px-3 py-2 text-sm ${
            toast.type === "success"
              ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200"
              : "bg-rose-50 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200"
          }`}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
