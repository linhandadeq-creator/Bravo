"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, FlaskConical, Search } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  fetchNeoantigenCandidates,
  fetchPredictionProviders,
  fetchRankingConfig,
  runNeoantigenEngine,
  updateRankingConfig,
  type NeoantigenCandidate,
  type PredictionProvider,
  type RankingConfig,
} from "@/lib/api";
import { PROVIDER_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";
import { useProjectRuns } from "@/lib/use-project-runs";

const STATUS_OPTIONS = ["ALL", "RANKED", "PREDICTED", "GENERATED", "REJECTED", "UNCERTAIN", "FAILED"];
const PREDICTION_OPTIONS = ["ALL", "MOCK", "AVAILABLE", "UNAVAILABLE", "FAILED", "PENDING"];
const WEIGHT_KEYS = [
  "presentation",
  "expression",
  "mutation",
  "tumor_specificity",
  "variant_quality",
];

const STATUS_TEXT_KEYS: Record<string, string> = {
  ALL: "neo.st.all",
  RANKED: "neo.st.ranked",
  PREDICTED: "neo.st.predicted",
  GENERATED: "neo.st.generated",
  REJECTED: "neo.st.rejected",
  UNCERTAIN: "neo.st.uncertain",
  FAILED: "neo.st.failed",
  MOCK: "neo.st.mock",
  AVAILABLE: "neo.st.available",
  UNAVAILABLE: "neo.st.unavailable",
  PENDING: "neo.st.pending",
};

const WEIGHT_KEYS_LABELS: Record<string, string> = {
  presentation: "neo.weight.presentation",
  expression: "neo.weight.expression",
  mutation: "neo.weight.mutation",
  tumor_specificity: "neo.weight.tumor_specificity",
  variant_quality: "neo.weight.variant_quality",
};

function expressionOf(candidate: NeoantigenCandidate): string {
  const evidence = candidate.expression_evidence;
  if (!evidence || evidence.expression_value == null) return "—";
  return `${evidence.expression_value} ${evidence.unit ?? ""}`.trim();
}

export default function NeoantigensPage() {
  const { t, lang } = useI18n();
  const { projects, projectId, setProjectId, runs, runId, setRunId } =
    useProjectRuns();

  const [providers, setProviders] = useState<PredictionProvider[]>([]);
  const [provider, setProvider] = useState("mock");
  const [config, setConfig] = useState<RankingConfig | null>(null);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [candidates, setCandidates] = useState<NeoantigenCandidate[]>([]);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [predictionFilter, setPredictionFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState("");
  const [sort, setSort] = useState("score_desc");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedProvider = providers.find((p) => p.name === provider);

  useEffect(() => {
    fetchPredictionProviders()
      .then((data) => {
        setProviders(data);
        const real = data.find((p) => !p.is_mock && p.status === "AVAILABLE");
        setProvider(real?.name ?? data.find((p) => p.is_mock)?.name ?? "mock");
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!projectId) return;
    fetchRankingConfig(projectId)
      .then((data) => {
        setConfig(data);
        setWeights(data.weights);
      })
      .catch(() => undefined);
  }, [projectId]);

  const loadCandidates = useCallback(async () => {
    if (!runId) {
      setCandidates([]);
      return;
    }
    try {
      setCandidates(
        await fetchNeoantigenCandidates(runId, {
          status: statusFilter === "ALL" ? undefined : statusFilter,
          predictionStatus: predictionFilter === "ALL" ? undefined : predictionFilter,
          search: search || undefined,
          minScore: minScore ? Number(minScore) : undefined,
          sort,
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("neo.loadFailed"));
    }
  }, [runId, statusFilter, predictionFilter, search, minScore, sort, t]);

  useEffect(() => {
    void loadCandidates();
  }, [loadCandidates]);

  async function handleSaveWeights() {
    if (!projectId) return;
    try {
      const updated = await updateRankingConfig(projectId, weights);
      setConfig(updated);
      setMessage(t("neo.weightSaved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("neo.saveWeightsFailed"));
    }
  }

  async function handleRun() {
    if (!runId || !projectId) {
      setError(t("neo.selectFirst"));
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await updateRankingConfig(projectId, weights);
      const summary = await runNeoantigenEngine(runId, { provider, weights });
      setMessage(
        t("neo.genMsg", {
          g: summary.generated,
          r: summary.rejected,
          p: summary.prediction.predicted,
          s: summary.prediction.provider_status,
          k: summary.ranking.ranked,
        })
      );
      await loadCandidates();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("neo.runFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("page.neoantigens.title")}
        description={t("page.neoantigens.desc")}
      />

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
            {runs.length === 0 ? <option value="">{t("neo.noRuns")}</option> : null}
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {run.mode} · {new Date(run.created_at).toLocaleString()} · {run.status}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <section className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-border p-4">
          <div className="space-y-2">
            <Label htmlFor="provider">{t("neo.provider")}</Label>
            <Select
              id="provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              {providers.map((item) => (
                <option key={item.name} value={item.name}>
                  {label(PROVIDER_LABELS, item.name, lang)} · {t(STATUS_TEXT_KEYS[item.status] ?? item.status)}
                  {item.is_mock ? t("neo.mockSuffix") : t("neo.realSuffix")}
                </option>
              ))}
            </Select>
          </div>
          {selectedProvider ? (
            <div
              className={
                "mt-3 flex items-start gap-2 rounded-md border px-3 py-2 text-xs " +
                (selectedProvider.is_mock
                  ? "border-amber-200 bg-amber-50 text-amber-800"
                  : selectedProvider.status === "AVAILABLE"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-red-200 bg-red-50 text-red-800")
              }
            >
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                {selectedProvider.is_mock
                  ? t("neo.mockWarn")
                  : selectedProvider.status === "AVAILABLE"
                    ? t("neo.realOk")
                    : t("neo.unavailWarn")}
              </span>
            </div>
          ) : null}
        </div>

        <div className="rounded-lg border border-border p-4">
          <div className="mb-2 text-sm font-semibold">
            {t("neo.rankingWeights")} {config ? `(v${config.version})` : ""}
          </div>
          <div className="space-y-2">
            {WEIGHT_KEYS.map((key) => (
              <div key={key} className="flex items-center gap-3">
                <span className="w-40 text-xs text-muted-foreground">{t(WEIGHT_KEYS_LABELS[key] ?? key)}</span>
                <Input
                  type="number"
                  step="0.05"
                  min="0"
                  value={weights[key] ?? 0}
                  onChange={(e) =>
                    setWeights((current) => ({
                      ...current,
                      [key]: Number(e.target.value),
                    }))
                  }
                  className="h-8 w-28"
                />
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={handleSaveWeights}>
              {t("neo.saveWeights")}
            </Button>
            <Button size="sm" onClick={handleRun} disabled={busy || !runId}>
              <FlaskConical className="h-4 w-4" />
              {busy ? t("neo.running") : t("neo.runEngine")}
            </Button>
          </div>
        </div>
      </section>

      <div className="rounded-md border border-border bg-secondary/40 px-4 py-3 text-xs text-muted-foreground">
        {t("neo.disclaimer")}
      </div>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="rounded-md border border-border bg-secondary/40 px-4 py-3 text-sm">
          {message}
        </div>
      ) : null}

      <section className="rounded-lg border border-border">
        <div className="flex flex-wrap items-end gap-3 border-b border-border px-5 py-3">
          <div className="space-y-1">
            <Label className="text-[11px]">{t("neo.status")}</Label>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-8 w-32"
            >
              {STATUS_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {t(STATUS_TEXT_KEYS[item] ?? item)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-[11px]">{t("neo.prediction")}</Label>
            <Select
              value={predictionFilter}
              onChange={(e) => setPredictionFilter(e.target.value)}
              className="h-8 w-32"
            >
              {PREDICTION_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {t(STATUS_TEXT_KEYS[item] ?? item)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-[11px]">{t("neo.minScore")}</Label>
            <Input
              type="number"
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              className="h-8 w-24"
              placeholder="0"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-[11px]">{t("neo.sort")}</Label>
            <Select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="h-8 w-32"
            >
              <option value="score_desc">{t("neo.sortScoreDesc")}</option>
              <option value="score_asc">{t("neo.sortScoreAsc")}</option>
              <option value="gene">{t("neo.sortGene")}</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-[11px]">{t("neo.search")}</Label>
            <div className="flex items-center gap-1">
              <Search className="h-3.5 w-3.5 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 w-44"
                placeholder={t("neo.searchPh")}
              />
            </div>
          </div>
          <div className="ml-auto text-xs text-muted-foreground">
            {t("neo.candidateCount", { n: candidates.length })}
          </div>
        </div>

        {candidates.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            {t("neo.noCandidates")}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("neo.col.candidate")}</TableHead>
                <TableHead>{t("neo.col.gene")}</TableHead>
                <TableHead>{t("neo.col.mutation")}</TableHead>
                <TableHead>HLA</TableHead>
                <TableHead>{t("neo.col.expression")}</TableHead>
                <TableHead>{t("neo.col.prediction")}</TableHead>
                <TableHead>{t("neo.col.specificity")}</TableHead>
                <TableHead>{t("neo.col.quality")}</TableHead>
                <TableHead>{t("neo.col.score")}</TableHead>
                <TableHead>{t("neo.col.status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {candidates.map((candidate) => (
                <TableRow key={candidate.id}>
                  <TableCell className="text-xs">
                    <Link
                      href={`/neoantigens/${candidate.id}`}
                      className="font-mono hover:underline"
                    >
                      {candidate.id.slice(0, 8)}
                    </Link>
                  </TableCell>
                  <TableCell className="text-xs">{candidate.gene ?? "—"}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {candidate.protein_change ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs">
                    {candidate.hla_allele ?? "—"}
                  </TableCell>
                  <TableCell className="tabular text-xs">
                    {expressionOf(candidate)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {candidate.prediction_status === "UNAVAILABLE" ? (
                      <span className="text-red-600">{t("neo.predUnavailable")}</span>
                    ) : candidate.prediction_status === "MOCK" ? (
                      <StatusBadge status="MOCK" />
                    ) : (
                      t(STATUS_TEXT_KEYS[candidate.prediction_status] ?? candidate.prediction_status)
                    )}
                  </TableCell>
                  <TableCell className="tabular text-xs">
                    {candidate.ranking_evidence?.components?.tumor_specificity ?? "—"}
                  </TableCell>
                  <TableCell className="tabular text-xs">
                    {candidate.mutation_evidence?.quality ?? "—"}
                  </TableCell>
                  <TableCell className="tabular text-xs font-medium">
                    {candidate.ranking_score ?? "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={candidate.status} />
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
