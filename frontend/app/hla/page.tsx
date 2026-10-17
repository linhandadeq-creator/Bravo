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
  addHlaManual,
  analyzeHla,
  fetchHla,
  fetchHlaStatus,
  fetchPopulationCoverage,
  fetchProjectFileContent,
  runSyntheticIntegration,
  uploadHla,
  type HLAProfile,
  type HlaStatus,
  type PopulationCoverage,
  type ProjectFile,
} from "@/lib/api";
import { MODE_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";
import { playSound } from "@/lib/sound";
import { useProjectRuns } from "@/lib/use-project-runs";
import { useToast } from "@/components/toast";

const MANUAL_PLACEHOLDER = `[
  { "allele": "HLA-A*02:01", "class": "I" },
  { "allele": "HLA-DRB1*15:01", "class": "II" }
]`;

export default function HlaPage() {
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

  const [profiles, setProfiles] = useState<HLAProfile[]>([]);
  const [status, setStatus] = useState<HlaStatus | null>(null);
  const [coverage, setCoverage] = useState<PopulationCoverage | null>(null);
  const [analysis, setAnalysis] = useState<{
    action?: string;
    profiles?: HLAProfile[];
    message?: string;
  } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fmt, setFmt] = useState("auto");
  const [source, setSource] = useState("manual");
  const [method, setMethod] = useState("manual");
  const [version, setVersion] = useState("1.0.0");
  const [manual, setManual] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    if (!id) {
      setProfiles([]);
      setStatus(null);
      setCoverage(null);
      return;
    }
    const [rows, state, cov] = await Promise.all([
      fetchHla(id),
      fetchHlaStatus(id),
      fetchPopulationCoverage(id).catch(() => null),
    ]);
    setProfiles(rows);
    setStatus(state);
    setCoverage(cov);
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
      setError(err instanceof Error ? err.message : t("hla.syntheticFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleAnalyze() {
    if (!runId) {
      setError(t("hla.selectRunFirst"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await analyzeHla(runId);
      setAnalysis(result);
      playSound("success");
      push(t("hla.analyzed"), "success");
      await load(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("hla.analyzeFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleUseProjectFile(file: ProjectFile) {
    if (!runId) {
      setError(t("hla.selectRunFirst"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const content = await fetchProjectFileContent(projectId, file.id);
      const blob = new Blob([content], { type: "text/plain" });
      const attached = new File([blob], file.filename, { type: "text/plain" });
      await uploadHla(runId, {
        file: attached,
        fmt: "auto",
        source: file.kind === "HLA" ? `project:${file.filename}` : source,
        method: method,
        version: version,
      });
      playSound("upload");
      push(t("hla.projectFileUsed", { name: file.filename }), "success");
      await load(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("variants.uploadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!runId || !file) {
      setError(t("hla.needRunFile"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await uploadHla(runId, {
        file,
        fmt: fmt === "auto" ? undefined : fmt,
        source,
        method,
        version,
      });
      setFile(null);
      await load(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("variants.uploadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleManual() {
    if (!runId) {
      setError(t("hla.selectRunFirst"));
      return;
    }
    let alleles: Record<string, unknown>[];
    try {
      alleles = JSON.parse(manual || "[]");
      if (!Array.isArray(alleles)) throw new Error(t("hla.jsonArray"));
    } catch (err) {
      setError(
        err instanceof Error
          ? t("hla.invalidJson", { msg: err.message })
          : t("hla.invalidJsonShort")
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await addHlaManual(runId, { alleles, source, method, version });
      setManual("");
      await load(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("hla.manualFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("page.hla.title")}
        description={t("page.hla.desc")}
      >
        <Button
          size="sm"
          variant="outline"
          onClick={handleSynthetic}
          disabled={busy || !projectId}
        >
          <FlaskConical className="h-4 w-4" />
          {t("hla.synthetic")}
        </Button>
        <Button size="sm" onClick={handleAnalyze} disabled={busy || !runId}>
          <Sparkles className="h-4 w-4" />
          {t("hla.analyze")}
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
            {runs.length === 0 ? <option value="">{t("hla.noRuns")}</option> : null}
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
        kinds={["HLA"]}
        onUse={handleUseProjectFile}
        busy={busy}
      />

      {status ? (
        <IntegrationBanner status={status.status} message={status.message} />
      ) : null}

      {analysis ? (
        <section className="rounded-lg border border-border">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold">{t("hla.analysisResult")}</h2>
            <StatusBadge status={analysis.profiles && analysis.profiles.length ? "VALID" : "INVALID"} />
          </div>
          <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
            <div className="bg-background px-4 py-3">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                {t("hla.col.class")} I
              </div>
              <div className="mt-0.5 tabular text-sm">{status?.class_i ?? "—"}</div>
            </div>
            <div className="bg-background px-4 py-3">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                {t("hla.col.class")} II
              </div>
              <div className="mt-0.5 tabular text-sm">{status?.class_ii ?? "—"}</div>
            </div>
            <div className="bg-background px-4 py-3">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                {t("hla.valid")}
              </div>
              <div className="mt-0.5 tabular text-sm">{status?.valid ?? "—"}</div>
            </div>
            <div className="bg-background px-4 py-3">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                {t("hla.duplicate")}
              </div>
              <div className="mt-0.5 tabular text-sm">{status?.duplicate ?? "—"}</div>
            </div>
          </div>
          <p className="px-5 py-3 text-xs text-muted-foreground">
            {analysis.message ?? ""}
          </p>
        </section>
      ) : null}

      {coverage ? (
        <section className="rounded-lg border border-border">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold">
              {t("hla.populationCoverage")}
            </h2>
            <span className="text-sm font-semibold tabular">
              {(coverage.overall_coverage * 100).toFixed(1)}%
            </span>
          </div>
          <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
            {Object.entries(coverage.per_locus).map(([locus, value]) => (
              <div key={locus} className="bg-background px-4 py-3">
                <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  {locus}
                </div>
                <div className="mt-0.5 tabular text-sm">
                  {(value.coverage * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
          <p className="px-5 py-3 text-xs text-muted-foreground">{coverage.note}</p>
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
          <h2 className="text-sm font-semibold">{t("hla.import")}</h2>
        </div>
        <form onSubmit={handleUpload} className="space-y-4 p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="file">{t("hla.file")}</Label>
              <FileInput
                id="file"
                accept=".json,.csv,.tsv,.txt"
                onChange={setFile}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fmt">{t("hla.format")}</Label>
              <Select id="fmt" value={fmt} onChange={(e) => setFmt(e.target.value)}>
                <option value="auto">{t("hla.auto")}</option>
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
                <option value="tsv">TSV</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="source">{t("hla.source")}</Label>
              <Input
                id="source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="method">{t("hla.method")}</Label>
              <Input
                id="method"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="version">{t("hla.version")}</Label>
              <Input
                id="version"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" size="sm" disabled={busy}>
              {t("hla.upload")}
            </Button>
            <span className="text-xs text-muted-foreground">
              {t("hla.versionNote", { version })}
            </span>
          </div>
        </form>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("hla.manual")}</h2>
        </div>
        <div className="space-y-3 p-5">
          <Textarea
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            placeholder={MANUAL_PLACEHOLDER}
            rows={5}
            className="font-mono text-xs"
          />
          <Button size="sm" variant="outline" onClick={handleManual} disabled={busy}>
            {t("hla.addManual")}
          </Button>
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">
            {t("hla.profiles", { n: profiles.length })}
          </h2>
          {status ? (
            <span className="text-xs text-muted-foreground">
              {t("hla.summary", {
                a: status.class_i,
                b: status.class_ii,
                c: status.duplicate,
              })}
            </span>
          ) : null}
        </div>
        {profiles.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            {t("hla.noData")}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("hla.col.allele")}</TableHead>
                <TableHead>{t("hla.col.class")}</TableHead>
                <TableHead>{t("hla.col.source")}</TableHead>
                <TableHead>{t("hla.col.method")}</TableHead>
                <TableHead>{t("hla.col.confidence")}</TableHead>
                <TableHead>{t("hla.col.validation")}</TableHead>
                <TableHead>{t("hla.col.status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {profiles.map((profile) => (
                <TableRow key={profile.id}>
                  <TableCell className="font-mono text-xs">
                    {profile.allele ?? profile.allele_raw ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs">
                    {profile.allele_class ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs">{profile.source ?? "—"}</TableCell>
                  <TableCell className="text-xs">{profile.method ?? "—"}</TableCell>
                  <TableCell className="tabular text-xs">
                    {profile.confidence ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs">
                    {profile.is_valid ? (
                      <span className="text-emerald-600">{t("hla.valid")}</span>
                    ) : (
                      <span className="text-red-600">{profile.invalid_reason}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <StatusBadge
                      status={
                        !profile.is_valid
                          ? "INVALID"
                          : profile.is_duplicate
                            ? "duplicate"
                            : "VALID"
                      }
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <p className="text-xs text-muted-foreground">
        {t("hla.footerBefore")}{" "}
        <Link href={`/variants/${runId}`} className="underline">
          {t("hla.footerLink")}
        </Link>{" "}
        {t("hla.footerAfter")}
      </p>
    </div>
  );
}
