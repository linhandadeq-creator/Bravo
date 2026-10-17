"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";

import { IntegrationBanner } from "@/components/integration-banner";
import { CheckStatusDot } from "@/components/status-badge";
import { fetchIntegrationStatus, type IntegrationStatus } from "@/lib/api";
import { CHECK_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";

export function IntegrationReadiness({ runId }: { runId: string }) {
  const { t, lang } = useI18n();
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchIntegrationStatus(runId)
      .then(setStatus)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load status")
      );
  }, [runId]);

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
        {error}
      </div>
    );
  }
  if (!status) return null;

  return (
    <section className="rounded-lg border border-border">
      <div className="flex items-center gap-2 border-b border-border/70 px-5 py-3">
        <ShieldCheck className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
        <h2 className="text-sm font-semibold">{t("ready.title")}</h2>
      </div>
      <div className="space-y-4 p-5">
        <IntegrationBanner
          status={status.status}
          message={status.status === "READY" ? t("ready.ready") : t("ready.blocked")}
        />
        <ul className="divide-y divide-border/70 rounded-md border border-border">
          {status.checks.map((check) => (
            <li key={check.id} className="flex items-start gap-3 px-4 py-2 text-xs">
              <span className="mt-1">
                <CheckStatusDot status={check.status} />
              </span>
              <span className="w-28 shrink-0 font-medium">
                {label(CHECK_LABELS, check.id, lang)}
              </span>
              <span className="text-muted-foreground">{check.detail}</span>
            </li>
          ))}
        </ul>
        <div className="grid gap-3 text-xs sm:grid-cols-2">
          <div>
            <div className="font-medium">{t("ready.linked")}</div>
            <div className="mt-1 font-mono text-muted-foreground">
              {status.linked_genes.length ? status.linked_genes.join(", ") : "—"}
            </div>
          </div>
          <div>
            <div className="font-medium">{t("ready.without")}</div>
            <div className="mt-1 font-mono text-muted-foreground">
              {status.genes_without_expression.length
                ? status.genes_without_expression.join(", ")
                : t("ready.none")}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
