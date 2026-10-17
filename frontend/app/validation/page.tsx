"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Play, XCircle } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  fetchValidationReport,
  fetchValidationReports,
  runFullValidation,
  type ValidationReport,
} from "@/lib/api";
import { CATEGORY_LABELS, CASE_NAME_LABELS, STAGE_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";

function compact(value: unknown): string {
  if (value === null || value === undefined) return "—";
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 90 ? `${text.slice(0, 90)}…` : text;
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: "default" | "success" | "danger" | "warning";
}) {
  const toneClass =
    tone === "success"
      ? "text-emerald-600"
      : tone === "danger"
        ? "text-red-600"
        : tone === "warning"
          ? "text-amber-600"
          : "text-foreground";
  return (
    <div className="rounded-lg border border-border p-4">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={`mt-1.5 text-2xl font-semibold tabular ${toneClass}`}>
        {value}
      </div>
    </div>
  );
}

export default function ValidationPage() {
  const { t, lang } = useI18n();
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    fetchValidationReports()
      .then(async (reports) => {
        if (reports.length) {
          setReport(await fetchValidationReport(reports[0].id));
        }
      })
      .catch(() => undefined);
  }, []);

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      setReport(await runFullValidation());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("val.runFailed"));
    } finally {
      setBusy(false);
    }
  }

  const categories = useMemo(() => {
    if (!report?.category_summary) return [];
    return Object.keys(report.category_summary);
  }, [report]);

  const filteredCases = useMemo(() => {
    if (!report?.cases) return [];
    return report.cases.filter(
      (c) =>
        (category === "ALL" || c.category === category) &&
        (statusFilter === "ALL" || c.status === statusFilter)
    );
  }, [report, category, statusFilter]);

  const validated = report?.status === "VALIDATED_SOFTWARE_BUILD";

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("page.validation.title")}
        description={t("page.validation.desc")}
      >
        <Button size="sm" onClick={handleRun} disabled={busy}>
          <Play className="h-4 w-4" />
          {busy ? t("val.running") : t("val.run")}
        </Button>
      </PageHeader>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {!report ? (
        <div className="rounded-lg border border-dashed border-border px-5 py-10 text-center text-sm text-muted-foreground">
          {t("val.noReport")}
        </div>
      ) : (
        <>
          <div
            className={
              "flex items-start gap-3 rounded-lg border px-4 py-4 " +
              (validated
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-red-200 bg-red-50 text-red-800")
            }
          >
            {validated ? (
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
            ) : (
              <XCircle className="mt-0.5 h-5 w-5 shrink-0" />
            )}
            <div className="space-y-1">
              <div className="text-base font-semibold">
                {validated ? t("val.validated") : t("val.notValidated")}
              </div>
              <div className="text-xs leading-relaxed">
                {report.disclaimer ?? t("val.disclaimer")}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label={t("val.totalTests")} value={report.total_tests} />
            <Metric label={t("val.passed")} value={report.passed} tone="success" />
            <Metric
              label={t("val.failed")}
              value={report.failed}
              tone={report.failed ? "danger" : "default"}
            />
            <Metric
              label={t("val.warnings")}
              value={report.warnings}
              tone={report.warnings ? "warning" : "default"}
            />
          </div>

          <section className="rounded-lg border border-border">
            <div className="border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">{t("val.pipelineHealth")}</h2>
            </div>
            <div className="flex flex-wrap gap-2 p-5">
              {(report.pipeline_health ?? []).map((stage) => (
                <div
                  key={stage.stage}
                  className={
                    "flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs " +
                    (stage.status === "PASS"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : stage.status === "FAIL"
                        ? "border-red-200 bg-red-50 text-red-700"
                        : stage.status === "WARNING"
                          ? "border-amber-200 bg-amber-50 text-amber-700"
                          : "border-border text-muted-foreground")
                  }
                >
                  <span className="font-medium">
                    {label(STAGE_LABELS, stage.stage, lang)}
                  </span>
                  <span className="opacity-70">{stage.status}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-border p-5">
              <h2 className="text-sm font-semibold">{t("val.reproducibility")}</h2>
              {report.reproducibility ? (
                <div className="mt-3 space-y-2 text-xs">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={report.reproducibility.status} />
                    <span className="text-muted-foreground">
                      {t("val.deterministic")}:{" "}
                      {String(report.reproducibility.deterministic)} ·{" "}
                      {t("val.seed")}:{" "}
                      {String(report.reproducibility.random_seed ?? t("ready.none"))}
                    </span>
                  </div>
                  <ul className="space-y-1 text-muted-foreground">
                    {Object.entries(report.reproducibility.details).map(([key, ok]) => (
                      <li key={key}>
                        {ok ? "✓" : "✗"} {key}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>

            <div className="rounded-lg border border-border p-5">
              <h2 className="text-sm font-semibold">{t("val.categories")}</h2>
              <div className="mt-3 space-y-1 text-xs">
                {report.category_summary
                  ? Object.entries(report.category_summary).map(([key, value]) => (
                      <div key={key} className="flex justify-between gap-4">
                        <span className="text-muted-foreground">
                          {label(CATEGORY_LABELS, key, lang)}
                        </span>
                        <span className="tabular">
                          {t("val.passTotal", { p: value.passed, t: value.total })}
                          {value.failed ? ` · ${value.failed} ${t("val.failSuffix")}` : ""}
                          {value.warnings ? ` · ${value.warnings} ${t("val.warnSuffix")}` : ""}
                        </span>
                      </div>
                    ))
                  : null}
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-border">
            <div className="flex flex-wrap items-end gap-3 border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">{t("val.cases")}</h2>
              <div className="ml-auto flex items-center gap-2">
                <Select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="h-8 w-56"
                >
                  <option value="ALL">{t("val.allCategories")}</option>
                  {categories.map((item) => (
                    <option key={item} value={item}>
                      {label(CATEGORY_LABELS, item, lang)}
                    </option>
                  ))}
                </Select>
                <Select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="h-8 w-32"
                >
                  {["ALL", "PASS", "FAIL", "WARNING"].map((item) => (
                    <option key={item} value={item}>
                      {item === "ALL"
                        ? t("val.all")
                        : item === "PASS"
                          ? t("val.passed")
                          : item === "FAIL"
                            ? t("val.failed")
                            : t("val.warnings")}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("val.step")}</TableHead>
                  <TableHead>{t("val.name")}</TableHead>
                  <TableHead>{t("val.expected")}</TableHead>
                  <TableHead>{t("val.actual")}</TableHead>
                  <TableHead>{t("val.status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCases.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="text-xs">
                      {label(STAGE_LABELS, item.step, lang)}
                    </TableCell>
                    <TableCell className="text-xs">
                      {label(CASE_NAME_LABELS, item.name, lang)}
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-muted-foreground">
                      {compact(item.expected_result)}
                    </TableCell>
                    <TableCell className="font-mono text-[11px]">
                      {compact(item.actual_result)}
                    </TableCell>
                    <TableCell>
                      {item.status === "PASS" ? (
                        <span className="text-xs text-emerald-600">PASS</span>
                      ) : item.status === "WARNING" ? (
                        <span className="inline-flex items-center gap-1 text-xs text-amber-600">
                          <AlertTriangle className="h-3 w-3" /> WARNING
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-red-600">
                          <XCircle className="h-3 w-3" /> FAIL
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>

          <section className="rounded-lg border border-border">
            <div className="border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">
                {t("val.audit")} ({report.audit_logs?.length ?? 0})
              </h2>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("val.timestamp")}</TableHead>
                  <TableHead>{t("val.step")}</TableHead>
                  <TableHead>{t("val.provider")}</TableHead>
                  <TableHead>{t("val.version")}</TableHead>
                  <TableHead>{t("val.status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(report.audit_logs ?? []).map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="tabular text-xs">
                      {new Date(log.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs">{log.step}</TableCell>
                    <TableCell className="text-xs">{log.provider ?? "—"}</TableCell>
                    <TableCell className="text-xs">{log.version ?? "—"}</TableCell>
                    <TableCell>
                      <StatusBadge status={log.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>

          <p className="text-xs text-muted-foreground">
            {t("val.softVersion")} {report.software_version} ·{" "}
            {report.finished_at ? new Date(report.finished_at).toLocaleString() : ""}
          </p>
        </>
      )}
    </div>
  );
}
