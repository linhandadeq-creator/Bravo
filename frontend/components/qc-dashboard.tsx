"use client";

import { AlertTriangle, Ban, CheckCircle2 } from "lucide-react";

import { CheckStatusDot, StatusBadge } from "@/components/status-badge";
import { CHECK_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";
import type { AnalysisRun, SampleQc } from "@/lib/api";

function Metric({
  label: metricLabel,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number | string;
  hint?: string;
  tone?: "default" | "danger" | "warning" | "success";
}) {
  const toneClass =
    tone === "danger"
      ? "text-red-600"
      : tone === "warning"
        ? "text-amber-600"
        : tone === "success"
          ? "text-emerald-600"
          : "text-foreground";
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-[11px] font-medium text-muted-foreground">
        {metricLabel}
      </div>
      <div className={`mt-1.5 text-xl font-semibold tabular ${toneClass}`}>
        {value}
      </div>
      {hint ? (
        <div className="mt-0.5 text-[11px] text-muted-foreground">{hint}</div>
      ) : null}
    </div>
  );
}

function statusBannerTone(status: string) {
  if (status === "PASS") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "FAILED") return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-red-200 bg-red-50 text-red-800";
}

export function QcDashboard({ run }: { run: AnalysisRun }) {
  const { t, lang } = useI18n();
  const qc = run.qc_summary;
  const somatic = run.somatic_summary;

  return (
    <div className="space-y-6">
      <div
        className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${statusBannerTone(
          run.status
        )}`}
      >
        {run.status === "PASS" ? (
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
        ) : run.status === "FAILED" ? (
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        ) : (
          <Ban className="mt-0.5 h-4 w-4 shrink-0" />
        )}
        <div className="min-w-0 space-y-0.5">
          <div className="flex items-center gap-2 text-sm font-semibold">
            {t("qc.title")} <StatusBadge status={run.status} />
          </div>
          {run.error_message ? (
            <div className="text-xs leading-relaxed">{run.error_message}</div>
          ) : (
            <div className="text-xs">{t("qc.passNote")}</div>
          )}
        </div>
      </div>

      {qc ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label={t("qc.raw")} value={qc.raw_variants} hint={t("qc.rawHint")} />
            <Metric label={t("qc.valid")} value={qc.valid_variants} tone="success" />
            <Metric
              label={t("qc.invalid")}
              value={qc.invalid_variants}
              tone={qc.invalid_variants ? "danger" : "default"}
            />
            <Metric
              label={t("qc.duplicate")}
              value={qc.duplicate_variants}
              tone={qc.duplicate_variants ? "warning" : "default"}
            />
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric
              label={t("qc.tumorOnly")}
              value={somatic?.TUMOR_ONLY ?? "—"}
              hint={t("qc.tumorOnlyHint")}
              tone="danger"
            />
            <Metric label={t("qc.normalOnly")} value={somatic?.NORMAL_ONLY ?? "—"} />
            <Metric label={t("qc.shared")} value={somatic?.SHARED ?? "—"} />
            <Metric
              label={t("qc.uncertain")}
              value={somatic?.UNCERTAIN ?? "—"}
              tone={somatic?.UNCERTAIN ? "warning" : "default"}
            />
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric
              label={t("qc.malformed")}
              value={qc.malformed_records}
              tone={qc.malformed_records ? "warning" : "default"}
            />
            <Metric
              label={t("qc.missing")}
              value={qc.missing_field_records}
              tone={qc.missing_field_records ? "warning" : "default"}
            />
            <Metric
              label={t("qc.chrNorm")}
              value={qc.chromosome_normalizations}
              hint={t("qc.chrHint")}
            />
            <Metric
              label={t("qc.unique")}
              value={qc.unique_variants}
              hint={t("qc.uniqueHint")}
            />
          </div>

          <section className="rounded-lg border border-border">
            <div className="border-b border-border/70 px-5 py-3">
              <h2 className="text-sm font-semibold">{t("qc.checks")}</h2>
            </div>
            <ul className="divide-y divide-border/70">
              {qc.checks.map((check) => (
                <li
                  key={check.id}
                  className="flex items-start gap-3 px-5 py-2.5 text-sm"
                >
                  <span className="mt-1.5">
                    <CheckStatusDot status={check.status} />
                  </span>
                  <span className="w-40 shrink-0 font-medium">
                    {label(CHECK_LABELS, check.id, lang)}
                  </span>
                  <span className="text-muted-foreground">{check.detail}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="grid gap-3 md:grid-cols-2">
            <SamplePanel
              title={t("qc.tumorSample")}
              sample={qc.tumor}
              missing={t("qc.noTumor")}
            />
            <SamplePanel
              title={t("qc.normalSample")}
              sample={qc.normal}
              missing={t("qc.noNormal")}
            />
          </section>
        </>
      ) : null}
    </div>
  );
}

function Row({ label: rowLabel, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-transparent px-4 py-2.5">
      <dt className="text-[11px] text-muted-foreground">{rowLabel}</dt>
      <dd className="mt-0.5 tabular text-sm">{value}</dd>
    </div>
  );
}

function SamplePanel({
  title,
  sample,
  missing,
}: {
  title: string;
  sample: SampleQc | null;
  missing: string;
}) {
  const { t } = useI18n();
  return (
    <div className="rounded-lg border border-border">
      <div className="border-b border-border/70 px-4 py-2.5 text-sm font-semibold">
        {title}
      </div>
      {sample ? (
        <dl className="grid grid-cols-2 gap-px bg-border/40">
          <Row label={t("qc.r.raw")} value={sample.raw_variants} />
          <Row label={t("qc.r.valid")} value={sample.valid_variants} />
          <Row label={t("qc.r.invalid")} value={sample.invalid_variants} />
          <Row label={t("qc.r.duplicate")} value={sample.duplicate_variants} />
          <Row label={t("qc.r.unique")} value={sample.unique_variants} />
          <Row label={t("qc.r.malformed")} value={sample.malformed_records} />
          <Row label={t("qc.r.missing")} value={sample.missing_field_records} />
          <Row label={t("qc.r.chr")} value={sample.chromosome_normalizations} />
        </dl>
      ) : (
        <div className="px-4 py-6 text-sm text-muted-foreground">{missing}</div>
      )}
    </div>
  );
}
