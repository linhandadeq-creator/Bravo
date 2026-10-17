"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { FlaskConical, Sparkles, Upload } from "lucide-react";

import { IntegrationBanner } from "@/components/integration-banner";
import { PageHeader } from "@/components/page-header";
import { ProjectFilesPanel } from "@/components/project-files-panel";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FileInput } from "@/components/ui/file-input";
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
import { Textarea } from "@/components/ui/textarea";
import {
  addExpressionManual,
  analyzeExpression,
  fetchExpression,
  fetchExpressionStatus,
  fetchProjectFileContent,
  runSyntheticIntegration,
  uploadExpression,
  type ExpressionRecord,
  type ExpressionStatus,
  type ProjectFile,
} from "@/lib/api";
import { MODE_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";
import { playSound } from "@/lib/sound";
import { useProjectRuns } from "@/lib/use-project-runs";
import { useToast } from "@/components/toast";

const MANUAL_PLACEHOLDER = `[
  { "gene_symbol": "MOCKGENE1", "expression_value": 12.5, "unit": "TPM" },
  { "gene_id": "ENSG00000141510.12", "gene_symbol": "TP53", "expression_value": 20.1, "unit": "TPM" }
]`;

export default function ExpressionPage() {
  const { t, lang } = useI18n();
  const { push } = useToast();
  const {
    projects,
    projectId,
    setProjectId,
    runs,
    runId,
    setRunId,
    loadRuns,
    projectFiles,
  } = useProjectRuns();

  const [records, setRecords] = useState<ExpressionRecord[]>([]);
  const [status, setStatus] = useState<ExpressionStatus | null>(null);
  const [analysis, setAnalysis] = useState<{
    action?: string;
    top_expressed?: ExpressionRecord[];
    message?: string;
  } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fmt, setFmt] = useState("auto");
  const [source, setSource] = useState("rnaseq");
  const [unit, setUnit] = useState("TPM");
  const [manual, setManual] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    if (!id) {
      setRecords([]);
      setStatus(null);
      return;
    }
    const [rows, state] = await Promise.all([
      fetchExpression(id),
      fetchExpressionStatus(id),
    ]);
    setRecords(rows);
    setStatus(state);
  }, []);

  useEffect(() => {
    load(runId).catch(() => undefined);
  }, [runId, load]);

  async function handleSynthetic() {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await runSyntheticIntegration(projectId);
      await loadRuns(projectId, false);
      setRunId(result.analysis_run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("expr.syntheticFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleAnalyze() {
    if (!runId) {
      setError(t("expr.selectRunFirst"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await analyzeExpression(runId);
      setAnalysis(result);
      playSound("success");
      push(t("expr.analyzed"), "success");
      await load(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("expr.analyzeFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleUseProjectFile(file: ProjectFile) {
    if (!runId) {
      setError(t("expr.selectRunFirst"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const content = await fetchProjectFileContent(projectId, file.id);
      const blob = new Blob([content], { type: "text/plain" });
      const attached = new File([blob], file.filename, { type: "text/plain" });
      await uploadExpression(runId, {
        file: attached,
        fmt: "auto",
        source: `project:${file.filename}`,
        unit,
      });
      playSound("upload");
      push(t("expr.projectFileUsed", { name: file.filename }), "success");
      await load(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("variants.uploadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleManual() {
    if (!runId) {
      setError(t("expr.selectRunFirst"));
      return;
    }
    let parsed: Record<string, unknown>[];
    try {
      parsed = JSON.parse(manual || "[]");
      if (!Array.isArray(parsed)) throw new Error(t("expr.jsonArray"));
    } catch (err) {
      setError(
        err instanceof Error
          ? t("expr.invalidJson", { msg: err.message })
          : t("expr.invalidJsonShort")
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await addExpressionManual(runId, { records: parsed, source, unit });
      setManual("");
      await load(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("expr.manualFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!runId || !file) {
      setError(t("expr.needRunFile"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await uploadExpression(runId, {
        file,
        fmt: fmt === "auto" ? undefined : fmt,
        source,
        unit,
      });
      setFile(null);
      await load(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("variants.uploadFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("page.expression.title")}
        description={t("page.expression.desc")}
      >
        <Button
          size="sm"
          variant="outline"
          onClick={handleSynthetic}
          disabled={busy || !projectId}
        >
          <FlaskConical className="h-4 w-4" />
          {t("expr.synthetic")}
        </Button>
        <Button size="sm" onClick={handleAnalyze} disabled={busy || !runId}>
          <Sparkles className="h-4 w-4" />
          {t("expr.analyze")}
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
            {runs.length === 0 ? <option value="">{t("expr.noRuns")}</option> : null}
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {label(MODE_LABELS, run.mode, lang)} · {new Date(run.created_at).toLocaleString()} ·{" "}
                {run.status}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <ProjectFilesPanel
        files={projectFiles}
        kinds={["EXPRESSION"]}
        onUse={handleUseProjectFile}
        busy={busy}
      />

      {status ? (
        <IntegrationBanner status={status.status} message={status.message} />
      ) : null}

      {analysis ? (
        <section className="rounded-lg border border-border">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold">{t("expr.analysisResult")}</h2>
            <span className="text-xs text-muted-foreground">
              {t("expr.topExpressed", { n: analysis.top_expressed?.length ?? 0 })}
            </span>
          </div>
          {analysis.top_expressed && analysis.top_expressed.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("expr.col.gene")}</TableHead>
                  <TableHead>{t("expr.col.expression")}</TableHead>
                  <TableHead>{t("expr.col.unit")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {analysis.top_expressed.slice(0, 10).map((record) => (
                  <TableRow key={`${record.gene_id}-${record.gene_symbol}`}>
                    <TableCell className="text-xs">
                      {record.gene_symbol ?? record.gene_id ?? "—"}
                    </TableCell>
                    <TableCell className="tabular text-xs">
                      {record.expression_value ?? "—"}
                    </TableCell>
                    <TableCell className="text-xs">{record.unit ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="px-5 py-6 text-sm text-muted-foreground">
              {t("expr.noData")}
            </div>
          )}
        </section>
      ) : null}

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <section className="rounded-lg border border-border">
        <div className="flex items-center gap-2 border-b border-border px-5 py-3">
          <Upload className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold">{t("expr.import")}</h2>
        </div>
        <form onSubmit={handleUpload} className="space-y-4 p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="file">{t("expr.file")}</Label>
              <FileInput
                id="file"
                accept=".csv,.tsv,.txt"
                onChange={setFile}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fmt">{t("expr.format")}</Label>
              <Select id="fmt" value={fmt} onChange={(e) => setFmt(e.target.value)}>
                <option value="auto">{t("expr.auto")}</option>
                <option value="csv">CSV</option>
                <option value="tsv">TSV</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="source">{t("expr.source")}</Label>
              <Input
                id="source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="unit">{t("expr.unitFallback")}</Label>
              <Input id="unit" value={unit} onChange={(e) => setUnit(e.target.value)} />
            </div>
          </div>
          <Button type="submit" size="sm" disabled={busy}>
            {t("expr.upload")}
          </Button>
        </form>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("expr.manual")}</h2>
        </div>
        <div className="space-y-3 p-5">
          <Textarea
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            placeholder={MANUAL_PLACEHOLDER}
            rows={5}
            className="font-mono text-xs"
          />
          <Button size="sm" variant="outline" disabled={busy} onClick={handleManual}>
            {t("expr.addManual")}
          </Button>
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">
            {t("expr.records", { n: records.length })}
          </h2>
          {status ? (
            <span className="text-xs text-muted-foreground">
              {t("expr.summary", {
                g: status.gene_level,
                t: status.transcript_level,
                n: status.normalized_identifiers,
              })}
            </span>
          ) : null}
        </div>
        {records.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            {t("expr.noData")}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("expr.col.gene")}</TableHead>
                <TableHead>{t("expr.col.transcript")}</TableHead>
                <TableHead>{t("expr.col.expression")}</TableHead>
                <TableHead>{t("expr.col.unit")}</TableHead>
                <TableHead>{t("expr.col.level")}</TableHead>
                <TableHead>{t("expr.col.source")}</TableHead>
                <TableHead>{t("expr.col.status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((record) => (
                <TableRow key={record.id}>
                  <TableCell className="text-xs">
                    <div className="font-medium">
                      {record.gene_symbol ?? record.gene_id ?? "—"}
                    </div>
                    {record.raw_gene_id &&
                    record.raw_gene_id !== record.gene_id ? (
                      <div className="text-[11px] text-muted-foreground">
                        {record.raw_gene_id} → {record.gene_id}
                      </div>
                    ) : null}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {record.transcript_id ?? "—"}
                  </TableCell>
                  <TableCell className="tabular text-xs">
                    {record.expression_value ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs">{record.unit ?? "—"}</TableCell>
                  <TableCell className="text-xs">{record.level}</TableCell>
                  <TableCell className="text-xs">{record.source ?? "—"}</TableCell>
                  <TableCell className="text-xs">
                    {record.is_valid ? (
                      record.gene_id_changed || record.transcript_id_changed ? (
                        <StatusBadge status="normalized" />
                      ) : (
                        <StatusBadge status="VALID" />
                      )
                    ) : (
                      <span className="text-red-600">{record.invalid_reason}</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <p className="text-xs text-muted-foreground">
        {t("expr.footerBefore")}{" "}
        <Link href={`/variants/${runId}`} className="underline">
          {t("expr.footerLink")}
        </Link>
        {t("expr.footerAfter")}
      </p>
    </div>
  );
}
