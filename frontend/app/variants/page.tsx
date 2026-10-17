"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { FlaskConical, Play, RefreshCw, Upload } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { ProjectFilesPanel } from "@/components/project-files-panel";
import { QcDashboard } from "@/components/qc-dashboard";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
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
import {
  fetchAnalysisRuns,
  fetchProjectFileContent,
  fetchProjectFiles,
  fetchProjects,
  REFERENCE_BUILDS,
  runSyntheticAnalysis,
  uploadAnalysis,
  type AnalysisRun,
  type Project,
  type ProjectFile,
} from "@/lib/api";
import { MODE_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";

export default function VariantsPage() {
  const { t, lang } = useI18n();
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [projectId, setProjectId] = useState("");
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [referenceBuild, setReferenceBuild] = useState<string>("GRCh38");
  const [tumorFile, setTumorFile] = useState<File | null>(null);
  const [normalFile, setNormalFile] = useState<File | null>(null);
  const [tumorBuild, setTumorBuild] = useState("");
  const [normalBuild, setNormalBuild] = useState("");
  const [busy, setBusy] = useState<"upload" | "synthetic" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [latest, setLatest] = useState<AnalysisRun | null>(null);

  const loadProjectFiles = useCallback(async (id: string) => {
    if (!id) {
      setProjectFiles([]);
      return;
    }
    try {
      setProjectFiles(await fetchProjectFiles(id));
    } catch {
      setProjectFiles([]);
    }
  }, []);

  const loadRuns = useCallback(async (id: string) => {
    if (!id) {
      setRuns([]);
      return;
    }
    try {
      setRuns(await fetchAnalysisRuns(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs");
    }
  }, []);

  useEffect(() => {
    fetchProjects()
      .then((data) => {
        setProjects(data);
        if (data.length) {
          setProjectId(data[0].id);
          void loadRuns(data[0].id);
          void loadProjectFiles(data[0].id);
        }
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load projects")
      );
  }, [loadRuns, loadProjectFiles]);

  async function handleUseProjectFile(file: ProjectFile) {
    setBusy("upload");
    setError(null);
    try {
      const content = await fetchProjectFileContent(projectId, file.id);
      const blob = new Blob([content], { type: "text/plain" });
      const attached = new File([blob], file.filename, { type: "text/plain" });
      if (file.kind === "NORMAL_VCF") {
        setNormalFile(attached);
      } else {
        setTumorFile(attached);
        const head = content.slice(0, 4096).toLowerCase();
        if (head.includes("grch37") || head.includes("hg19") || head.includes("b37")) {
          setReferenceBuild("GRCh37");
        } else if (head.includes("grch38") || head.includes("hg38")) {
          setReferenceBuild("GRCh38");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("variants.uploadFailed"));
    } finally {
      setBusy(null);
    }
  }

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!projectId || !tumorFile) {
      setError(t("variants.needProject"));
      return;
    }
    setBusy("upload");
    setError(null);
    try {
      const run = await uploadAnalysis({
        projectId,
        tumorFile,
        normalFile,
        referenceBuild: referenceBuild || undefined,
        tumorReferenceBuild: tumorBuild || undefined,
        normalReferenceBuild: normalBuild || undefined,
      });
      setLatest(run);
      setTumorFile(null);
      setNormalFile(null);
      await loadRuns(projectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("variants.uploadFailed"));
    } finally {
      setBusy(null);
    }
  }

  async function handleSynthetic() {
    if (!projectId) {
      setError(t("variants.selectProjectFirst"));
      return;
    }
    setBusy("synthetic");
    setError(null);
    try {
      const run = await runSyntheticAnalysis(projectId, referenceBuild);
      setLatest(run);
      await loadRuns(projectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("variants.syntheticFailed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("page.variants.title")}
        description={t("page.variants.desc")}
      >
        <Button
          size="sm"
          variant="outline"
          onClick={() => projectId && loadRuns(projectId)}
        >
          <RefreshCw className="h-4 w-4" />
          {t("common.refresh")}
        </Button>
      </PageHeader>

      {projects.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-5 py-8 text-sm text-muted-foreground">
          {t("variants.noProjects")}
        </div>
      ) : (
        <>
        <ProjectFilesPanel
          files={projectFiles}
          kinds={["TUMOR_VCF", "NORMAL_VCF"]}
          onUse={handleUseProjectFile}
          busy={busy !== null}
        />
        <section className="rounded-lg border border-border">
          <div className="flex items-center gap-2 border-b border-border/70 px-5 py-3">
            <Upload className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold">{t("variants.newRun")}</h2>
          </div>
          <form onSubmit={handleUpload} className="space-y-5 p-5">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="project">{t("variants.project")}</Label>
                <Select
                  id="project"
                  value={projectId}
                  onChange={(e) => {
                    setProjectId(e.target.value);
                    setLatest(null);
                    void loadRuns(e.target.value);
                    void loadProjectFiles(e.target.value);
                  }}
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="build">{t("variants.build")}</Label>
                <Select
                  id="build"
                  value={referenceBuild}
                  onChange={(e) => setReferenceBuild(e.target.value)}
                >
                  {REFERENCE_BUILDS.map((build) => (
                    <option key={build} value={build}>
                      {build}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="tumor-file">{t("variants.tumorFile")}</Label>
                <FileInput
                  id="tumor-file"
                  accept=".vcf,.gz"
                  onChange={setTumorFile}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="normal-file">{t("variants.normalFile")}</Label>
                <FileInput
                  id="normal-file"
                  accept=".vcf,.gz"
                  onChange={setNormalFile}
                />
              </div>
            </div>

            <details className="rounded-md border border-border px-4 py-3">
              <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
                {t("variants.advanced")}
              </summary>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="tumor-build">{t("variants.tumorBuild")}</Label>
                  <Select
                    id="tumor-build"
                    value={tumorBuild}
                    onChange={(e) => setTumorBuild(e.target.value)}
                  >
                    <option value="">{t("variants.useRunBuild")}</option>
                    {REFERENCE_BUILDS.map((build) => (
                      <option key={build} value={build}>
                        {build}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="normal-build">{t("variants.normalBuild")}</Label>
                  <Select
                    id="normal-build"
                    value={normalBuild}
                    onChange={(e) => setNormalBuild(e.target.value)}
                  >
                    <option value="">{t("variants.useRunBuild")}</option>
                    {REFERENCE_BUILDS.map((build) => (
                      <option key={build} value={build}>
                        {build}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
            </details>

            <p className="text-xs leading-relaxed text-muted-foreground">
              {t("variants.pairNote1")} <strong>{t("variants.pairNote2")}</strong>
              {t("variants.pairNote3")}
            </p>

            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit" size="sm" disabled={busy !== null}>
                <Play className="h-4 w-4" />
                {busy === "upload" ? t("variants.analysing") : t("variants.run")}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleSynthetic}
                disabled={busy !== null}
              >
                <FlaskConical className="h-4 w-4" />
                {busy === "synthetic" ? t("variants.generating") : t("variants.loadSynthetic")}
              </Button>
            </div>
          </form>
        </section>
        </>
      )}

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {latest ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">{t("variants.latestQc")}</h2>
            <Link
              href={`/variants/${latest.id}`}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              {t("variants.openFull")}
            </Link>
          </div>
          <QcDashboard run={latest} />
        </section>
      ) : null}

      <section className="rounded-lg border border-border">
        <div className="border-b border-border/70 px-5 py-3">
          <h2 className="text-sm font-semibold">{t("variants.runs")}</h2>
        </div>
        {runs.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            {t("variants.noRuns")}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("variants.col.created")}</TableHead>
                <TableHead>{t("variants.col.mode")}</TableHead>
                <TableHead>{t("variants.col.build")}</TableHead>
                <TableHead>{t("variants.col.rawValid")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead className="w-16" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => (
                <TableRow key={run.id}>
                  <TableCell className="tabular text-xs text-muted-foreground">
                    {new Date(run.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-xs">
                    {label(MODE_LABELS, run.mode, lang)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {run.reference_build ?? "—"}
                  </TableCell>
                  <TableCell className="tabular text-xs">
                    {run.qc_summary
                      ? `${run.qc_summary.raw_variants} / ${run.qc_summary.valid_variants}`
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={run.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <Link
                      href={`/variants/${run.id}`}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      {t("common.view")}
                    </Link>
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
