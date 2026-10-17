"use client";

import { useCallback, useEffect, useState } from "react";
import { Dna, ShieldCheck } from "lucide-react";

import { CheckStatusDot, StatusBadge } from "@/components/status-badge";
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
  annotateRun,
  fetchAnnotatedVariants,
  fetchAnnotationRun,
  fetchConsequences,
  fetchFilterConfig,
  fetchNeoantigenInput,
  fetchProviders,
  updateFilterConfig,
  type AnnotationRun,
  type AnnotatedVariant,
  type Provider,
} from "@/lib/api";
import { CHECK_LABELS, CONSEQUENCE_LABELS, PROVIDER_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";

export function AnnotationPanel({
  runId,
  projectId,
  runReferenceBuild,
}: {
  runId: string;
  projectId: string;
  runReferenceBuild: string | null;
}) {
  const { t, lang } = useI18n();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [provider, setProvider] = useState("mock");
  const [annotationRun, setAnnotationRun] = useState<AnnotationRun | null>(null);
  const [consequences, setConsequences] = useState<string[]>([]);
  const [allowed, setAllowed] = useState<string[]>([]);
  const [annotated, setAnnotated] = useState<AnnotatedVariant[]>([]);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gate, setGate] = useState<string | null>(null);

  const loadAnnotated = useCallback(
    async (allowedList?: string[]) => {
      setAnnotated(await fetchAnnotatedVariants(runId, allowedList));
    },
    [runId]
  );

  useEffect(() => {
    fetchProviders().then(setProviders).catch(() => setProviders([]));
    fetchConsequences().then(setConsequences).catch(() => setConsequences([]));
    fetchAnnotationRun(runId).then(setAnnotationRun).catch(() => undefined);
    fetchFilterConfig(projectId)
      .then((config) => {
        setAllowed(config.allowed_consequences);
        void loadAnnotated(config.allowed_consequences);
      })
      .catch(() => void loadAnnotated());
  }, [runId, projectId, loadAnnotated]);

  async function handleAnnotate() {
    setBusy(true);
    setError(null);
    setGate(null);
    try {
      const result = await annotateRun(runId, provider);
      setAnnotationRun(result);
      await loadAnnotated(allowed);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("ann.annotateFailed"));
    } finally {
      setBusy(false);
    }
  }

  function toggleConsequence(value: string) {
    setAllowed((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    );
  }

  async function handleSaveFilter() {
    setSaving(true);
    setError(null);
    try {
      const config = await updateFilterConfig(projectId, allowed);
      setAllowed(config.allowed_consequences);
      await loadAnnotated();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("ann.saveFilterFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function handleGateCheck() {
    setGate(null);
    setError(null);
    try {
      const permitted = await fetchNeoantigenInput(runId);
      setGate(t("ann.gatePassed", { n: permitted.length }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("ann.gateFailed"));
    }
  }

  return (
    <section className="space-y-6">
      <div className="rounded-lg border border-border">
        <div className="flex items-center gap-2 border-b border-border/70 px-5 py-3">
          <Dna className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold">{t("ann.title")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-56 space-y-2">
              <Label htmlFor="provider">{t("ann.provider")}</Label>
              <Select
                id="provider"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                {providers.map((item) => (
                  <option key={item.name} value={item.name}>
                    {label(PROVIDER_LABELS, item.name, lang)}
                    {item.available ? "" : `（${t("ann.missing")}）`}
                  </option>
                ))}
              </Select>
            </div>
            <Button size="sm" onClick={handleAnnotate} disabled={busy}>
              {busy ? t("ann.annotating") : t("ann.annotate")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={handleGateCheck}
              disabled={!annotationRun}
            >
              <ShieldCheck className="h-4 w-4" />
              {t("ann.checkGate")}
            </Button>
          </div>

          <p className="text-xs text-muted-foreground">
            {t("ann.buildNote")}
            <span className="font-medium text-foreground">
              {runReferenceBuild ?? t("ann.missing")}
            </span>
            {t("ann.buildNote2")}
          </p>

          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}
          {gate ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {gate}
            </div>
          ) : null}

          {annotationRun ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <StatusBadge status={annotationRun.status} />
                <span className="text-muted-foreground">
                  {label(PROVIDER_LABELS, annotationRun.provider, lang)}{" "}
                  {annotationRun.provider_version} · {annotationRun.annotation_version} ·{" "}
                  {annotationRun.transcript_source}
                </span>
              </div>
              {annotationRun.error_message ? (
                <div className="text-xs text-red-600">
                  {annotationRun.error_message}
                </div>
              ) : null}
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <MiniMetric label={t("ann.variants")} value={annotationRun.variant_count} />
                <MiniMetric label={t("ann.annotated")} value={annotationRun.annotated_count} />
                <MiniMetric label={t("ann.partial")} value={annotationRun.partial_count} />
                <MiniMetric label={t("ann.failed")} value={annotationRun.failed_count} />
              </div>
              {annotationRun.compatibility?.checks?.length ? (
                <ul className="divide-y divide-border/70 rounded-md border border-border">
                  {annotationRun.compatibility.checks.map((check) => (
                    <li
                      key={check.id}
                      className="flex items-start gap-3 px-4 py-2 text-xs"
                    >
                      <span className="mt-1">
                        <CheckStatusDot status={check.status} />
                      </span>
                      <span className="w-40 shrink-0 font-medium">
                        {label(CHECK_LABELS, check.id, lang)}
                      </span>
                      <span className="text-muted-foreground">{check.detail}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">{t("ann.noRun")}</div>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-border">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 px-5 py-3">
          <h2 className="text-sm font-semibold">
            {t("ann.allowed", { n: allowed.length })}
          </h2>
          <Button
            size="sm"
            variant="outline"
            onClick={handleSaveFilter}
            disabled={saving}
          >
            {saving ? t("ann.saving") : t("ann.saveFilter")}
          </Button>
        </div>
        <div className="flex flex-wrap gap-2 p-5">
          {consequences.map((consequence) => {
            const active = allowed.includes(consequence);
            return (
              <button
                key={consequence}
                type="button"
                onClick={() => toggleConsequence(consequence)}
                className={
                  "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors " +
                  (active
                    ? "border-foreground/20 bg-secondary text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground")
                }
              >
                {label(CONSEQUENCE_LABELS, consequence, lang)}
              </button>
            );
          })}
        </div>
        <p className="px-5 pb-4 text-xs text-muted-foreground">
          {t("ann.filterNote")}
        </p>
      </div>

      <div className="rounded-lg border border-border">
        <div className="border-b border-border/70 px-5 py-3">
          <h2 className="text-sm font-semibold">
            {t("ann.annotatedVariants", { n: annotated.length })}
          </h2>
        </div>
        {annotated.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            {t("ann.noAnnotated")}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("ann.role")}</TableHead>
                <TableHead>{t("ann.locus")}</TableHead>
                <TableHead>{t("ann.change")}</TableHead>
                <TableHead>{t("ann.gene")}</TableHead>
                <TableHead>{t("ann.transcript")}</TableHead>
                <TableHead>{t("ann.consequence")}</TableHead>
                <TableHead>{t("ann.protein")}</TableHead>
                <TableHead>{t("ann.status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {annotated.slice(0, 300).map((item) => (
                <TableRow key={item.variant_id}>
                  <TableCell className="text-xs">
                    {item.sample_role === "TUMOR" ? t("ann.tumor") : t("ann.normal")}
                  </TableCell>
                  <TableCell className="tabular text-xs">
                    {item.chromosome}:{item.position}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.reference}&gt;{item.alternate}
                  </TableCell>
                  <TableCell className="text-xs">{item.gene ?? "—"}</TableCell>
                  <TableCell className="text-xs">{item.transcript ?? "—"}</TableCell>
                  <TableCell className="text-xs">
                    {item.consequence
                      ? label(CONSEQUENCE_LABELS, item.consequence, lang)
                      : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.protein_change ?? "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={item.status ?? "—"} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </section>
  );
}

function MiniMetric({ label: metricLabel, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border p-3">
      <div className="text-[11px] text-muted-foreground">{metricLabel}</div>
      <div className="mt-1 tabular text-lg font-semibold">{value}</div>
    </div>
  );
}
