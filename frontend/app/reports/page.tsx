"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, FileText, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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
  fetchReport,
  fetchReports,
  generateReport,
  reportDownloadUrl,
  runReportUrl,
  type Report,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useProjectRuns } from "@/lib/use-project-runs";

const FORMATS = [
  { value: "pdf", label: "PDF" },
  { value: "html", label: "HTML" },
  { value: "markdown", label: "Markdown" },
  { value: "json", label: "JSON" },
  { value: "csv", label: "CSV" },
];

const FORMAT_LABELS: Record<string, string> = {
  pdf: "PDF",
  markdown: "Markdown",
  html: "HTML",
  json: "JSON",
  csv: "CSV",
};

export default function ReportsPage() {
  const { t } = useI18n();
  const { projects, projectId, setProjectId, runs, runId, setRunId } =
    useProjectRuns();

  const [format, setFormat] = useState("html");
  const [reports, setReports] = useState<Report[]>([]);
  const [preview, setPreview] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadReports = useCallback(async (pid: string, rid: string) => {
    if (!pid) {
      setReports([]);
      return;
    }
    const list = await fetchReports({ projectId: pid, runId: rid || undefined });
    setReports(list);
    if (list.length) {
      const full = await fetchReport(list[0].id);
      setPreview(full);
    } else {
      setPreview(null);
    }
  }, []);

  useEffect(() => {
    loadReports(projectId, runId).catch(() => undefined);
  }, [projectId, runId, loadReports]);

  async function handleGenerate() {
    if (!runId) {
      setError(t("rep.needRun"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const report = await generateReport(runId, {
        format,
        generated_by: "researcher@lab",
      });
      setPreview(report);
      await loadReports(projectId, runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("rep.generateFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("page.reports.title")}
        description={t("page.reports.desc")}
      >
        <Button
          size="sm"
          variant="outline"
          disabled={!runId}
          onClick={() =>
            runId && window.open(runReportUrl(runId, "html"), "_blank")
          }
        >
          <FileText className="h-4 w-4" />
          {t("rep.directHtml")}
        </Button>
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="project">{t("common.project")}</Label>
          <Select
            id="project"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="run">{t("common.run")}</Label>
          <Select id="run" value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.length === 0 ? <option value="">{t("rep.noRuns")}</option> : null}
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {new Date(run.created_at).toLocaleString()} · {run.status}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <section className="flex flex-wrap items-end gap-3 rounded-lg border border-border p-5">
        <div className="w-56 space-y-2">
          <Label htmlFor="format">{t("rep.format")}</Label>
          <Select
            id="format"
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            {FORMATS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.value === "csv" ? t("rep.csvCandidates") : item.label}
              </option>
            ))}
          </Select>
        </div>
        <Button size="sm" onClick={handleGenerate} disabled={busy || !runId}>
          <Sparkles className="h-4 w-4" />
          {busy ? t("rep.generating") : t("rep.generate")}
        </Button>
        {runId ? (
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            {t("rep.directExport")}
            {["pdf", "markdown", "html", "json", "csv"].map((fmt) => (
              <a
                key={fmt}
                href={runReportUrl(runId, fmt)}
                target="_blank"
                rel="noreferrer"
                className="rounded-md border border-border bg-white/60 px-2 py-0.5 hover:text-foreground"
              >
                {FORMAT_LABELS[fmt]}
              </a>
            ))}
          </div>
        ) : null}
      </section>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {preview ? (
        <section className="rounded-lg border border-border">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 px-5 py-3">
            <h2 className="text-sm font-semibold">{t("rep.preview")}</h2>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{FORMAT_LABELS[preview.format] ?? preview.format}</span>
              <Button asChild size="sm" variant="outline">
                <a href={reportDownloadUrl(preview.id)} target="_blank" rel="noreferrer">
                  <Download className="h-4 w-4" />
                  {t("rep.download")}
                </a>
              </Button>
            </div>
          </div>
          {preview.format === "pdf" ? (
            <div className="flex flex-col items-start gap-3 p-6 text-sm">
              <p className="text-muted-foreground">{t("rep.pdfReady")}</p>
              <Button asChild size="sm">
                <a href={reportDownloadUrl(preview.id)} target="_blank" rel="noreferrer">
                  <Download className="h-4 w-4" />
                  {t("rep.pdfDownload")}
                </a>
              </Button>
            </div>
          ) : preview.format === "html" ? (
            <iframe
              title="report-preview"
              srcDoc={preview.content ?? ""}
              className="h-[70vh] w-full rounded-b-lg bg-white"
            />
          ) : (
            <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-b-lg bg-white/60 p-5 font-mono text-[11px] leading-relaxed">
              {preview.content}
            </pre>
          )}
        </section>
      ) : null}

      <section className="rounded-lg border border-border">
        <div className="border-b border-border/70 px-5 py-3">
          <h2 className="text-sm font-semibold">
            {t("rep.generatedList", { n: reports.length })}
          </h2>
        </div>
        {reports.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            {t("rep.noReports")}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("rep.col.title")}</TableHead>
                <TableHead>{t("rep.col.format")}</TableHead>
                <TableHead>{t("rep.col.generatedBy")}</TableHead>
                <TableHead>{t("rep.col.time")}</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {reports.map((report) => (
                <TableRow key={report.id}>
                  <TableCell className="text-xs">
                    <button
                      type="button"
                      className="text-left hover:underline"
                      onClick={() =>
                        fetchReport(report.id).then(setPreview).catch(() => undefined)
                      }
                    >
                      {report.title}
                    </button>
                  </TableCell>
                  <TableCell className="text-xs">
                    {FORMAT_LABELS[report.format] ?? report.format}
                  </TableCell>
                  <TableCell className="text-xs">
                    {report.generated_by ?? "—"}
                  </TableCell>
                  <TableCell className="tabular text-xs text-muted-foreground">
                    {new Date(report.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <a
                      href={reportDownloadUrl(report.id)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      {t("rep.download")}
                    </a>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  );
}
