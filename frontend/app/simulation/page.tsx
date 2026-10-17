"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Download, Lock, Plus, X } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  createConstruct,
  fetchConstructs,
  fetchNeoantigenCandidates,
  constructExportUrl,
  lockConstruct,
  updateConstructSelection,
  validateConstruct,
  type NeoantigenCandidate,
  type SimulationConstruct,
} from "@/lib/api";
import { CHECK_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";
import { useProjectRuns } from "@/lib/use-project-runs";

export default function SimulationPage() {
  const { t, lang } = useI18n();
  const { projects, projectId, setProjectId, runs, runId, setRunId } =
    useProjectRuns();

  const [candidates, setCandidates] = useState<NeoantigenCandidate[]>([]);
  const [selection, setSelection] = useState<string[]>([]);
  const [construct, setConstruct] = useState<SimulationConstruct | null>(null);
  const [selectedBy, setSelectedBy] = useState("researcher@lab");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const byId = useMemo(() => {
    const map: Record<string, NeoantigenCandidate> = {};
    for (const candidate of candidates) map[candidate.id] = candidate;
    return map;
  }, [candidates]);

  useEffect(() => {
    if (!runId) {
      setCandidates([]);
      setSelection([]);
      setConstruct(null);
      return;
    }
    fetchNeoantigenCandidates(runId, {})
      .then(setCandidates)
      .catch(() => setCandidates([]));
    fetchConstructs(runId)
      .then((list) => {
        if (list.length) {
          setConstruct(list[0]);
          setSelection(list[0].candidate_ids ?? []);
        } else {
          setConstruct(null);
          setSelection([]);
        }
      })
      .catch(() => undefined);
  }, [runId]);

  const available = useMemo(() => {
    const term = search.toLowerCase();
    return candidates
      .filter((c) => !selection.includes(c.id))
      .filter(
        (c) =>
          !term ||
          (c.gene ?? "").toLowerCase().includes(term) ||
          (c.protein_change ?? "").toLowerCase().includes(term) ||
          (c.hla_allele ?? "").toLowerCase().includes(term)
      );
  }, [candidates, selection, search]);

  const locked = construct?.status === "LOCKED";

  function add(id: string) {
    if (locked) return;
    setSelection((current) => [...current, id]);
  }
  function remove(id: string) {
    if (locked) return;
    setSelection((current) => current.filter((value) => value !== id));
  }
  function move(index: number, delta: number) {
    if (locked) return;
    setSelection((current) => {
      const next = [...current];
      const target = index + delta;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  const save = useCallback(async () => {
    if (!runId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved =
        construct && !locked
          ? await updateConstructSelection(construct.id, {
              candidate_ids: selection,
              selected_by: selectedBy,
            })
          : locked
            ? construct
            : await createConstruct(runId, {
                candidate_ids: selection,
                selected_by: selectedBy,
              });
      if (saved) {
        setConstruct(saved);
        setSelection(saved.candidate_ids ?? []);
        setMessage(t("sim.savedSelection", { s: saved.status }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("sim.saveFailed"));
    } finally {
      setBusy(false);
    }
  }, [runId, construct, locked, selection, selectedBy, t]);

  async function handleValidate() {
    if (!construct) {
      setError(t("sim.saveFirst"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await validateConstruct(construct.id);
      setConstruct(result);
      setMessage(t("sim.validationResult", { s: result.status }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("sim.validateFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleLock() {
    if (!construct) return;
    setBusy(true);
    setError(null);
    try {
      const result = await lockConstruct(construct.id);
      setConstruct(result);
      setMessage(t("sim.lockedMsg"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("sim.lockFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("page.simulation.title")}
        description={t("page.simulation.desc")}
      >
        {construct ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              asChild
            >
              <a href={constructExportUrl(construct.id, "json")} target="_blank" rel="noreferrer">
                <Download className="h-4 w-4" />
                JSON
              </a>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <a href={constructExportUrl(construct.id, "csv")} target="_blank" rel="noreferrer">
                CSV
              </a>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <a href={constructExportUrl(construct.id, "report")} target="_blank" rel="noreferrer">
                {t("sim.report")}
              </a>
            </Button>
          </div>
        ) : null}
      </PageHeader>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
        {t("sim.research")}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="project">{t("sim.project")}</Label>
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
          <Label htmlFor="run">{t("sim.run")}</Label>
          <Select id="run" value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.length === 0 ? <option value="">{t("neo.noRuns")}</option> : null}
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {run.mode} · {new Date(run.created_at).toLocaleString()} · {run.status}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="selected-by">{t("sim.selectedBy")}</Label>
          <Input
            id="selected-by"
            value={selectedBy}
            onChange={(e) => setSelectedBy(e.target.value)}
          />
        </div>
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

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Available candidates */}
        <section className="rounded-lg border border-border">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">
              {t("sim.available", { n: available.length })}
            </h2>
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("sim.searchPh")}
              className="mt-2 h-8"
            />
          </div>
          <ul className="max-h-[28rem] divide-y divide-border overflow-auto">
            {available.map((candidate) => (
              <li
                key={candidate.id}
                className="flex items-center justify-between gap-2 px-4 py-2 text-xs"
              >
                <div className="min-w-0">
                  <div className="truncate font-medium">
                    {candidate.gene ?? "—"}{" "}
                    <span className="font-mono text-muted-foreground">
                      {candidate.protein_change ?? ""}
                    </span>
                  </div>
                  <div className="truncate text-muted-foreground">
                    {candidate.hla_allele ?? "—"} · {t("sim.score")} {candidate.ranking_score ?? "—"} ·{" "}
                    {candidate.status}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => add(candidate.id)}
                  disabled={locked}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </li>
            ))}
            {available.length === 0 ? (
              <li className="px-4 py-6 text-xs text-muted-foreground">
                {t("sim.noAvailable")}
              </li>
            ) : null}
          </ul>
        </section>

        {/* Construct simulation */}
        <section className="rounded-lg border border-border">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">{t("sim.construct")}</h2>
          </div>
          <div className="space-y-3 p-4">
            {construct ? <StatusBadge status={construct.status} /> : null}
            <div className="rounded-md border border-border bg-secondary/30 p-3 font-mono text-[11px] leading-relaxed">
              {construct?.construct_representation ?? t("sim.noCandidatesSel")}
            </div>
            <div className="text-xs text-muted-foreground">
              {t("sim.segSummary", {
                n: selection.length,
                nt: construct?.sequence
                  ? t("sim.ntSimulated", { n: construct.sequence.length })
                  : t("sim.noSequence"),
              })}
            </div>
            {construct?.sequence ? (
              <div className="break-all rounded-md border border-border p-3 font-mono text-[10px] text-muted-foreground">
                {construct.sequence.slice(0, 160)}
                {construct.sequence.length > 160 ? "…" : ""}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={save} disabled={busy || locked || !runId}>
                {construct && !locked ? t("sim.saveSelection") : t("sim.createConstruct")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleValidate}
                disabled={busy || !construct}
              >
                {t("sim.validate")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleLock}
                disabled={busy || !construct || construct.status !== "VALIDATED_SIMULATION"}
              >
                <Lock className="h-4 w-4" />
                {t("sim.lock")}
              </Button>
            </div>
          </div>
        </section>

        {/* Selected candidates */}
        <section className="rounded-lg border border-border">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">
              {t("sim.selected", { n: selection.length })}
            </h2>
          </div>
          <ul className="max-h-[28rem] divide-y divide-border overflow-auto">
            {selection.map((id, index) => {
              const candidate = byId[id];
              return (
                <li
                  key={`${id}-${index}`}
                  className="flex items-center justify-between gap-2 px-4 py-2 text-xs"
                >
                  <div className="min-w-0">
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {String(index + 1).padStart(3, "0")} ·{" "}
                      {construct?.items?.[index]?.label ?? `ANTIGEN_${index + 1}`}
                    </div>
                    <div className="truncate font-medium">
                      {candidate?.gene ?? id.slice(0, 8)}{" "}
                      <span className="font-mono text-muted-foreground">
                        {candidate?.protein_change ?? ""}
                      </span>
                    </div>
                    <div className="truncate text-muted-foreground">
                      {candidate?.hla_allele ?? "—"}
                    </div>
                  </div>
                  <div className="flex items-center gap-0.5">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={() => move(index, -1)}
                      disabled={locked}
                    >
                      <ArrowUp className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={() => move(index, 1)}
                      disabled={locked}
                    >
                      <ArrowDown className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={() => remove(id)}
                      disabled={locked}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </li>
              );
            })}
            {selection.length === 0 ? (
              <li className="px-4 py-6 text-xs text-muted-foreground">
                {t("sim.noSelected")}
              </li>
            ) : null}
          </ul>
        </section>
      </div>

      {/* Validation status */}
      <section className="rounded-lg border border-border">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("sim.validationStatus")}</h2>
          {construct?.qc_summary ? (
            <StatusBadge status={construct.qc_summary.status} />
          ) : null}
        </div>
        {!construct?.qc_summary ? (
          <div className="px-5 py-6 text-sm text-muted-foreground">
            {t("sim.noValidation")}
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {construct.qc_summary.checks.map((check) => (
              <li key={check.id} className="flex items-start gap-3 px-5 py-2 text-xs">
                <span
                  className={
                    "mt-1 inline-block h-1.5 w-1.5 rounded-full " +
                    (check.status === "pass"
                      ? "bg-emerald-500"
                      : check.status === "warn"
                        ? "bg-amber-500"
                        : "bg-red-500")
                  }
                />
                <span className="w-52 shrink-0 font-medium">{label(CHECK_LABELS, check.id, lang)}</span>
                <span className="text-muted-foreground">{check.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
