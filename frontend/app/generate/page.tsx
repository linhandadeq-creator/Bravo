"use client";

import Link from "next/link";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ban, Download, FileText, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { ProjectFilesPanel } from "@/components/project-files-panel";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FileInput } from "@/components/ui/file-input";
import { OneClickPipeline } from "@/components/one-click-pipeline";
import { useToast } from "@/components/toast";
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
  blueprintUrl,
  cancelOneClickJob,
  createOneClickJobWithProgress,
  fetchOneClickJob,
  fetchPredictionProviders,
  fetchProjectFileContent,
  fetchProjectFiles,
  fetchProjects,
  fetchProviders,
  productionPackageUrl,
  reportDownloadUrl,
  runReportUrl,
  worklistUrl,
  REFERENCE_BUILDS,
  type OneClickJob,
  type OneClickResult,
  type PredictionProvider,
  type Project,
  type ProjectFile,
  type Provider,
} from "@/lib/api";
import { PROVIDER_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";
import { playSound } from "@/lib/sound";
import {
  hasStoredResult,
  isEmptyState,
  loadOneClick,
  saveOneClick,
} from "@/lib/oneclick-store";
import {
  SCHEME_COMPONENTS,
  resolveWorldClassScheme,
} from "@/lib/world-class-scheme";

const SEGMENT_LABELS: Record<string, string> = {
  "5PRIME": "gen.seg.5PRIME",
  "3PRIME": "gen.seg.3PRIME",
  ANTIGEN: "gen.seg.ANTIGEN",
  SPACER: "gen.seg.SPACER",
};

export default function GeneratePage() {
  const { t, lang } = useI18n();
  const { push } = useToast();
  const [tumorFile, setTumorFile] = useState<File | null>(null);
  const [normalFile, setNormalFile] = useState<File | null>(null);
  const [hlaFile, setHlaFile] = useState<File | null>(null);
  const [expressionFile, setExpressionFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState(t("gen.defaultProjectName"));
  const [referenceBuild, setReferenceBuild] = useState("GRCh38");
  const [provider, setProvider] = useState("mock");
  const [providers, setProviders] = useState<PredictionProvider[]>([]);
  const [annotationProvider, setAnnotationProvider] = useState("mock");
  const [annotationProviders, setAnnotationProviders] = useState<Provider[]>([]);
  const [topN, setTopN] = useState("5");
  const [simulationFormat, setSimulationFormat] = useState("mRNA-LNP");
  const [useSynthetic, setUseSynthetic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OneClickResult | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [liveStages, setLiveStages] = useState<OneClickJob["stages"]>([]);
  const [uploadPct, setUploadPct] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [schemeApplied, setSchemeApplied] = useState(false);

  // Refs so the polling callback can persist the current values without
  // capturing stale state.
  const projectIdRef = useRef(projectId);
  const startedAtRef = useRef(startedAt);
  useEffect(() => {
    projectIdRef.current = projectId;
  }, [projectId]);
  useEffect(() => {
    startedAtRef.current = startedAt;
  }, [startedAt]);

  function applyWorldClassScheme() {
    const applied = resolveWorldClassScheme(providers, annotationProviders);
    setProvider(applied.provider);
    setAnnotationProvider(applied.annotationProvider);
    setTopN(String(applied.topN));
    setSimulationFormat(applied.simulationFormat);
    setReferenceBuild(applied.referenceBuild);
    setSchemeApplied(true);
    playSound("success");
    push(
      t("scheme.applied", {
        provider: applied.providerReal
          ? `${label(PROVIDER_LABELS, applied.provider, lang)} · REAL`
          : "MOCK",
        annotation: applied.annotationReal ? "REAL" : "MOCK",
      }),
      "success"
    );
  }

  useEffect(() => {
    fetchProjects()
      .then((data) => setProjects(data))
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!projectId) {
      setProjectFiles([]);
      return;
    }
    fetchProjectFiles(projectId)
      .then(setProjectFiles)
      .catch(() => setProjectFiles([]));
  }, [projectId]);

  useEffect(() => {
    fetchPredictionProviders()
      .then((data) => {
        setProviders(data);
        setProvider((current) => {
          if (current !== "mock") return current;
          const real = data.find((p) => !p.is_mock && p.status === "AVAILABLE");
          return real?.name ?? "mock";
        });
      })
      .catch(() => setProviders([]));
    fetchProviders()
      .then((data) => {
        setAnnotationProviders(data);
        setAnnotationProvider((current) => {
          if (current !== "mock") return current;
          const real =
            data.find((p) => p.name === "offline" && p.available) ??
            data.find((p) => p.available);
          return real?.name ?? "mock";
        });
      })
      .catch(() => setAnnotationProviders([]));
  }, []);

  function buildForm(demo: boolean): FormData {
    const form = new FormData();
    form.append("project_name", projectName);
    if (projectId) form.append("project_id", projectId);
    form.append("reference_build", referenceBuild);
    form.append("provider", provider);
    form.append("annotation_provider", annotationProvider);
    form.append("top_n", topN);
    form.append("simulation_format", simulationFormat);
    form.append("use_synthetic_context", useSynthetic ? "true" : "false");
    form.append("demo", demo ? "true" : "false");
    if (tumorFile) form.append("tumor_file", tumorFile);
    if (normalFile) form.append("normal_file", normalFile);
    if (hlaFile) form.append("hla_file", hlaFile);
    if (expressionFile) form.append("expression_file", expressionFile);
    return form;
  }

  const pollJob = useCallback(
    async (id: string) => {
      for (;;) {
        await new Promise((resolve) => setTimeout(resolve, 1200));
        let current;
        try {
          current = await fetchOneClickJob(id);
        } catch {
          // The job no longer exists (e.g. the backend was restarted). Say so
          // clearly rather than leaving a frozen "in progress" view.
          setError(t("gen.jobLost"));
          push(t("gen.jobLost"), "error");
          break;
        }
        setLiveStages(current.stages);
        if (current.status === "SUCCESS" || current.status === "BLOCKED") {
          if (current.result) {
            setResult(current.result);
            // Persist immediately so the sequence survives a fast module switch
            // without waiting for the state-effect to flush.
            saveOneClick({
              projectId: projectIdRef.current,
              startedAt: startedAtRef.current,
              jobId: id,
              result: current.result,
              liveStages: current.stages,
            });
          }
          break;
        }
        if (current.status === "FAILED") {
          const message = current.error || t("gen.failed");
          setError(message);
          push(message, "error");
          break;
        }
        if (current.status === "CANCELLED") {
          push(t("gen.cancelled"), "info");
          break;
        }
      }
    },
    [push, t]
  );

  async function run(demo: boolean) {
    if (!demo && !tumorFile) {
      setError(t("gen.needTumor"));
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    setLiveStages([]);
    setUploadPct(0);
    setStartedAt(null);
    setCancelling(false);
    try {
      const job = await createOneClickJobWithProgress(buildForm(demo), setUploadPct);
      setJobId(job.id);
      setStartedAt(Date.now());
      await pollJob(job.id);
    } catch (err) {
      const message = err instanceof Error ? err.message : t("gen.failed");
      setError(message);
      push(message, "error");
    } finally {
      setBusy(false);
      setJobId(null);
      setCancelling(false);
    }
  }

  // Restore the last one-click result across refresh / navigation, and resume
  // an in-flight job if one was running.
  const restoredRef = useRef(false);
  useEffect(() => {
    if (restoredRef.current) return;
    restoredRef.current = true;
    const saved = loadOneClick();
    if (!saved) return;
    if (saved.projectId) setProjectId(saved.projectId);
    if (saved.startedAt) setStartedAt(saved.startedAt);
    if (Array.isArray(saved.liveStages)) {
      setLiveStages(saved.liveStages as OneClickJob["stages"]);
    }
    if (saved.result) {
      setResult(saved.result as OneClickResult);
      return;
    }
    if (saved.jobId) {
      setJobId(saved.jobId);
      setBusy(true);
      void pollJob(saved.jobId).finally(() => {
        setBusy(false);
        setJobId(null);
        setCancelling(false);
      });
    }
  }, [pollJob]);

  // Persist on every meaningful change. The first run is skipped so the empty
  // mount state never overwrites an already-stored result; an empty state is
  // also refused if a stored result exists.
  const firstPersistRef = useRef(true);
  useEffect(() => {
    if (firstPersistRef.current) {
      firstPersistRef.current = false;
      return;
    }
    const state = { projectId, startedAt, jobId, result, liveStages };
    if (isEmptyState(state) && hasStoredResult()) {
      return;
    }
    saveOneClick(state);
  }, [projectId, startedAt, jobId, result, liveStages]);

  async function cancelRun() {
    if (!jobId || cancelling) return;
    setCancelling(true);
    try {
      await cancelOneClickJob(jobId);
      push(t("gen.cancellingToast"), "info");
    } catch (err) {
      setCancelling(false);
      push(err instanceof Error ? err.message : t("gen.failed"), "error");
    }
  }

  function fileValidator(extensions: string[], maxMb: number) {
    return (file: File): string | null => {
      const lower = file.name.toLowerCase();
      if (!extensions.some((ext) => lower.endsWith(ext))) return t("common.invalidFile");
      if (file.size > maxMb * 1024 * 1024) return t("common.fileTooLarge");
      return null;
    };
  }

  async function onTumorSelected(file: File | null) {
    setTumorFile(file);
    if (!file) return;
    try {
      const head = (await file.slice(0, 4096).text()).toLowerCase();
      if (head.includes("grch38") || head.includes("hg38")) setReferenceBuild("GRCh38");
      else if (head.includes("grch37") || head.includes("hg19") || head.includes("b37"))
        setReferenceBuild("GRCh37");
    } catch {
      // ignore
    }
  }

  async function handleUseProjectFile(file: ProjectFile) {
    setBusy(true);
    setError(null);
    try {
      const content = await fetchProjectFileContent(projectId, file.id);
      const blob = new Blob([content], { type: "text/plain" });
      const attached = new File([blob], file.filename, { type: "text/plain" });
      if (file.kind === "TUMOR_VCF") await onTumorSelected(attached);
      else if (file.kind === "NORMAL_VCF") setNormalFile(attached);
      else if (file.kind === "HLA") setHlaFile(attached);
      else if (file.kind === "EXPRESSION") setExpressionFile(attached);
      push(t("gen.projectFileUsed", { name: file.filename }), "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("gen.failed"));
    } finally {
      setBusy(false);
    }
  }

  const providerMeta = providers.find((p) => p.name === provider);
  const providerIsMock = providerMeta ? providerMeta.is_mock : provider === "mock";
  const preflightOk = Boolean(
    tumorFile && normalFile && (hlaFile || useSynthetic) && (expressionFile || useSynthetic)
  );

  const blueprint = result?.blueprint ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("page.generate.title")}
        description={t("page.generate.desc")}
      >
        <Button size="sm" variant="outline" onClick={() => run(true)} disabled={busy}>
          <Sparkles className="h-4 w-4" />
          {t("gen.synthetic")}
        </Button>
      </PageHeader>

      <div className="rounded-md border border-border bg-secondary/40 px-4 py-3 text-xs text-muted-foreground">
        {t("gen.research")}
      </div>

      <section className="rounded-lg border border-accent/30">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold">{t("scheme.title")}</h2>
            <p className="mt-0.5 text-[11px] text-muted-foreground">{t("scheme.subtitle")}</p>
          </div>
          <Button
            size="sm"
            onClick={applyWorldClassScheme}
            disabled={busy}
          >
            {schemeApplied ? t("scheme.reapply") : t("scheme.apply")}
          </Button>
        </div>
        <div className="grid gap-2 p-5 sm:grid-cols-2 lg:grid-cols-3">
          {SCHEME_COMPONENTS.map((component) => (
            <div key={component.id} className="rounded-xl border border-border px-3.5 py-2.5">
              <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {t(component.labelKey)}
              </div>
              <div className="mt-0.5 text-[12.5px] leading-snug">
                {t(component.valueKey)}
              </div>
            </div>
          ))}
        </div>
        {schemeApplied ? (
          <div className="border-t border-border px-5 py-3 text-xs text-emerald-600">
            {t("scheme.appliedNote")}
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("gen.projectFiles")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <div className="max-w-md space-y-2">
            <Label htmlFor="proj">{t("common.project")}</Label>
            <Select
              id="proj"
              value={projectId}
              onChange={(e) => {
                setProjectId(e.target.value);
                if (e.target.value) {
                  const project = projects.find((p) => p.id === e.target.value);
                  if (project) setProjectName(project.name);
                }
              }}
            >
              <option value="">{t("gen.noProject")}</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
          </div>
          <ProjectFilesPanel
            files={projectFiles}
            kinds={["TUMOR_VCF", "NORMAL_VCF", "HLA", "EXPRESSION"]}
            onUse={handleUseProjectFile}
            busy={busy}
          />
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("gen.uploadParams")}</h2>
        </div>
        <div className="space-y-5 p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="tumor">{t("gen.tumor")}</Label>
              <FileInput id="tumor" accept=".vcf,.gz" onChange={onTumorSelected} validate={fileValidator([".vcf", ".vcf.gz", ".gz"], 3072)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="normal">{t("gen.normal")}</Label>
              <FileInput id="normal" accept=".vcf,.gz" onChange={setNormalFile} validate={fileValidator([".vcf", ".vcf.gz", ".gz"], 3072)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="hla">{t("gen.hla")}</Label>
              <FileInput id="hla" accept=".json,.csv,.tsv" onChange={setHlaFile} validate={fileValidator([".json", ".csv", ".tsv", ".txt"], 64)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="expr">{t("gen.expr")}</Label>
              <FileInput id="expr" accept=".csv,.tsv" onChange={setExpressionFile} validate={fileValidator([".csv", ".tsv", ".txt"], 64)} />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            <div className="space-y-2">
              <Label htmlFor="pname">{t("gen.projectName")}</Label>
              <Input id="pname" value={projectName} onChange={(e) => setProjectName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="build">{t("gen.build")}</Label>
              <Select id="build" value={referenceBuild} onChange={(e) => setReferenceBuild(e.target.value)}>
                {REFERENCE_BUILDS.map((build) => (
                  <option key={build} value={build}>{build}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="provider">{t("gen.provider")}</Label>
              <Select id="provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
                {(providers.length ? providers : []).map((item) => (
                  <option key={item.name} value={item.name}>
                    {label(PROVIDER_LABELS, item.name, lang)}
                    {item.is_mock
                      ? " · MOCK"
                      : item.status === "AVAILABLE"
                        ? " · REAL"
                        : ` · ${item.status}`}
                  </option>
                ))}
                {providers.length === 0 ? (
                  <option value="mock">{t("gen.providerMock")}</option>
                ) : null}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="annotation-provider">{t("gen.annotationProvider")}</Label>
              <Select
                id="annotation-provider"
                value={annotationProvider}
                onChange={(e) => setAnnotationProvider(e.target.value)}
              >
                {(annotationProviders.length ? annotationProviders : [{ name: "mock", available: true } as Provider]).map(
                  (item) => (
                    <option key={item.name} value={item.name}>
                      {label(PROVIDER_LABELS, item.name, lang)}
                      {item.name === "mock"
                        ? " · MOCK"
                        : item.available
                          ? " · REAL"
                          : " · UNAVAILABLE"}
                    </option>
                  )
                )}
              </Select>
              {annotationProviders.find((x) => x.name === annotationProvider)
                ?.description ? (
                <p
                  className={
                    "text-[11px] " +
                    (annotationProviders.find((x) => x.name === annotationProvider)
                      ?.available
                      ? "text-muted-foreground"
                      : "text-amber-700")
                  }
                >
                  {
                    annotationProviders.find((x) => x.name === annotationProvider)
                      ?.description
                  }
                </p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="topn">{t("gen.topN")}</Label>
              <Input id="topn" type="number" min="1" max="20" value={topN} onChange={(e) => setTopN(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fmt">{t("gen.format")}</Label>
              <Select id="fmt" value={simulationFormat} onChange={(e) => setSimulationFormat(e.target.value)}>
                <option value="mRNA-LNP">mRNA-LNP</option>
                <option value="circRNA">circRNA (PIE)</option>
                <option value="saRNA">saRNA</option>
              </Select>
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={useSynthetic} onChange={(e) => setUseSynthetic(e.target.checked)} />
            {t("gen.useSynthetic")}
          </label>

          {providerIsMock ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
              {t("gen.mockBanner")}
            </div>
          ) : (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
              {t("gen.realBanner", { name: provider })}
            </div>
          )}

          <div className="rounded-md border border-border px-4 py-3 text-xs">
            <div className="mb-1 font-medium">{t("pre.title")}</div>
            <ul className="space-y-0.5 text-muted-foreground">
              <li>{tumorFile ? `✓ ${tumorFile.name}` : `• ${t("gen.tumor")}`}</li>
              {!normalFile ? <li>• {t("pre.normalMissing")}</li> : <li>✓ {normalFile.name}</li>}
              {!hlaFile && !useSynthetic ? <li>• {t("pre.hlaMissing")}</li> : null}
              {!expressionFile && !useSynthetic ? <li>• {t("pre.exprMissing")}</li> : null}
              <li className={preflightOk ? "text-emerald-700" : "text-amber-700"}>
                {preflightOk ? t("pre.ready") : t("common.loading")}
              </li>
            </ul>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => run(false)} disabled={busy}>
              <Sparkles className="h-4 w-4" />
              {busy ? t("gen.generating") : t("gen.generate")}
            </Button>
            {busy ? (
              <Button
                size="sm"
                variant="outline"
                onClick={cancelRun}
                disabled={cancelling || !jobId}
              >
                <Ban className="h-3.5 w-3.5" />
                {cancelling ? t("gen.cancelling") : t("gen.cancelRun")}
              </Button>
            ) : null}
            {busy ? (
              <span className="flex items-center gap-2">
                <span className="h-1 w-48 overflow-hidden rounded-full bg-secondary">
                  <span
                    className={
                      uploadPct < 100
                        ? "block h-full rounded-full bg-accent transition-[width] duration-200"
                        : "block h-full w-1/3 rounded-full bg-accent [animation:indeterminate_1.2s_ease-in-out_infinite]"
                    }
                    style={uploadPct < 100 ? { width: `${Math.max(4, uploadPct)}%` } : undefined}
                  />
                </span>
                {uploadPct < 100 ? (
                  <span className="text-xs text-muted-foreground">{uploadPct}%</span>
                ) : null}
              </span>
            ) : null}
          </div>
        </div>
      </section>

      <OneClickPipeline
        stages={result?.stages ?? liveStages}
        running={Boolean(jobId) && !result}
        startedAt={startedAt}
        cancelling={cancelling}
        onCancel={cancelRun}
        context={{
          "gen.build": referenceBuild,
          "gen.annotationProvider": annotationProvider,
          "gen.provider": provider,
          "gen.topN": topN,
          "gen.format": simulationFormat,
        }}
      />

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {result ? (
        <>
          <div
            className={
              "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm " +
              (result.status === "SUCCESS"
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-amber-200 bg-amber-50 text-amber-800")
            }
          >
            <div className="space-y-0.5">
              <div className="font-semibold">
                {t("gen.result")}:{" "}
                {result.status === "SUCCESS" ? t("gen.success") : result.status === "BLOCKED" ? t("gen.blocked") : t("gen.failedShort")}
              </div>
              <div className="text-xs">{result.message}</div>
            </div>
          </div>

          {result.status === "SUCCESS" && result.analysis_run_id ? (
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm" variant="outline">
                <Link href="/neoantigens">{t("gen.viewCandidates")}</Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link href={`/variants/${result.analysis_run_id}`}>{t("gen.viewRun")}</Link>
              </Button>
            </div>
          ) : null}

          {blueprint && result.construct_id ? (
            <>
              <section className="rounded-lg border border-border">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
                  <h2 className="text-sm font-semibold">{t("gen.blueprint")}</h2>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Button asChild size="sm">
                      <a href={blueprintUrl(result.construct_id, "pdf")} target="_blank" rel="noreferrer">
                        <Download className="h-4 w-4" />
                        {t("gen.downloadPdf")}
                      </a>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <a href={blueprintUrl(result.construct_id, "svg")} target="_blank" rel="noreferrer">
                        SVG
                      </a>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <a href={blueprintUrl(result.construct_id, "html")} target="_blank" rel="noreferrer">
                        <FileText className="h-4 w-4" />
                        {t("gen.blueprintHtml")}
                      </a>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <a href={productionPackageUrl(result.construct_id, "markdown")} target="_blank" rel="noreferrer">
                        <FileText className="h-4 w-4" />
                        {t("gen.productionPackage")}
                      </a>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <a href={worklistUrl(result.construct_id)} target="_blank" rel="noreferrer">
                        <Download className="h-4 w-4" />
                        {t("gen.worklistCsv")}
                      </a>
                    </Button>
                  </div>
                </div>
                <div className="space-y-4 p-5">
                  <div className="overflow-x-auto rounded-md border border-border bg-white p-4">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={blueprintUrl(result.construct_id, "svg")}
                      alt={t("gen.blueprintAlt")}
                      className="max-w-full"
                    />
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {t("gen.representation")}<span className="font-mono">{blueprint.construct_representation}</span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {t("gen.seqLen", { n: blueprint.sequence_length })}
                  </div>
                  {blueprint.sequence_qc ? (
                    <div className="flex items-center gap-2 text-xs">
                      {t("gen.seqQc")}:
                      <StatusBadge status={blueprint.sequence_qc.status} />
                      <span className="text-muted-foreground">
                        {t("gen.manufacturability", {
                          n: blueprint.sequence_qc.manufacturability_score,
                        })}
                      </span>
                    </div>
                  ) : null}
                </div>
              </section>

              <section className="rounded-lg border border-border">
                <div className="border-b border-border px-5 py-3">
                  <h2 className="text-sm font-semibold">{t("gen.antigenSeq")}</h2>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("gen.col.segment")}</TableHead>
                      <TableHead>{t("gen.col.type")}</TableHead>
                      <TableHead>{t("gen.col.gene")}</TableHead>
                      <TableHead>{t("gen.col.proteinChange")}</TableHead>
                      <TableHead>HLA</TableHead>
                      <TableHead>{t("gen.col.peptide")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {blueprint.segments.map((segment) => (
                      <TableRow key={segment.index}>
                        <TableCell className="font-mono text-xs">{segment.label}</TableCell>
                        <TableCell className="text-xs">
                          {SEGMENT_LABELS[segment.type]
                            ? t(SEGMENT_LABELS[segment.type])
                            : segment.type}
                        </TableCell>
                        <TableCell className="text-xs">{segment.gene ?? "—"}</TableCell>
                        <TableCell className="font-mono text-xs">{segment.protein_change ?? "—"}</TableCell>
                        <TableCell className="text-xs">{segment.hla_allele ?? "—"}</TableCell>
                        <TableCell className="font-mono text-xs">{segment.peptide_sequence ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </section>

              <section className="rounded-lg border border-border">
                <div className="border-b border-border px-5 py-3">
                  <h2 className="text-sm font-semibold">{t("gen.simSeq")}</h2>
                </div>
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all p-5 font-mono text-[11px] leading-relaxed text-muted-foreground">
                  {blueprint.sequence}
                </pre>
              </section>

              {result.report_id ? (
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {t("gen.analysisReport")}
                  <a href={reportDownloadUrl(result.report_id)} target="_blank" rel="noreferrer" className="underline">
                    {t("gen.downloadHtml")}
                  </a>
                  {result.analysis_run_id ? (
                    <>
                      <a href={runReportUrl(result.analysis_run_id, "pdf")} target="_blank" rel="noreferrer" className="underline">
                        {t("gen.downloadPdfReport")}
                      </a>
                      <a href={runReportUrl(result.analysis_run_id, "html")} target="_blank" rel="noreferrer" className="underline">
                        {t("gen.viewOnline")}
                      </a>
                    </>
                  ) : null}
                </div>
              ) : null}

              <p className="text-xs text-muted-foreground">{blueprint.disclaimer}</p>
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
