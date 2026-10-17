"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { AnnotationPanel } from "@/components/annotation-panel";
import { IntegrationReadiness } from "@/components/integration-readiness";
import { PageHeader } from "@/components/page-header";
import { QcDashboard } from "@/components/qc-dashboard";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  fetchAnalysisRun,
  fetchRunVariants,
  fetchSomaticCandidates,
  type AnalysisRun,
  type SomaticCandidate,
  type Variant,
} from "@/lib/api";
import { MODE_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";

const CLASSIFICATIONS = ["ALL", "TUMOR_ONLY", "NORMAL_ONLY", "SHARED", "UNCERTAIN"];

const CLASSIFICATION_LABELS: Record<string, string> = {
  ALL: "run.all",
  TUMOR_ONLY: "qc.tumorOnly",
  NORMAL_ONLY: "qc.normalOnly",
  SHARED: "qc.shared",
  UNCERTAIN: "qc.uncertain",
};

const ROLE_LABELS: Record<string, string> = {
  ALL: "run.all",
  TUMOR: "ann.tumor",
  NORMAL: "ann.normal",
};

function formatAf(value: number | null): string {
  return value === null || value === undefined ? "—" : value.toFixed(3);
}

export default function VariantRunPage() {
  const params = useParams<{ id: string }>();
  const runId = params?.id;

  const { t, lang } = useI18n();

  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<SomaticCandidate[]>([]);
  const [classification, setClassification] = useState("ALL");
  const [variants, setVariants] = useState<Variant[]>([]);
  const [role, setRole] = useState("ALL");
  const [validOnly, setValidOnly] = useState(false);
  const [includeDuplicates, setIncludeDuplicates] = useState(true);

  useEffect(() => {
    if (!runId) return;
    fetchAnalysisRun(runId)
      .then(setRun)
      .catch((err) =>
        setError(err instanceof Error ? err.message : t("run.loadFailed"))
      );
  }, [runId, t]);

  useEffect(() => {
    if (!runId) return;
    fetchSomaticCandidates(
      runId,
      classification === "ALL" ? undefined : classification
    )
      .then(setCandidates)
      .catch(() => setCandidates([]));
  }, [runId, classification]);

  const loadVariants = useCallback(async () => {
    if (!runId) return;
    try {
      setVariants(
        await fetchRunVariants(runId, {
          role: role === "ALL" ? undefined : role,
          validOnly,
          includeDuplicates,
        })
      );
    } catch {
      setVariants([]);
    }
  }, [runId, role, validOnly, includeDuplicates]);

  useEffect(() => {
    void loadVariants();
  }, [loadVariants]);

  return (
    <div className="space-y-6">
      <PageHeader
        title={run ? `${t("run.title")} ${run.id.slice(0, 8)}` : t("common.run")}
        description={
          run
            ? `${label(MODE_LABELS, run.mode, lang)} · ${t("run.creating")} ${new Date(run.created_at).toLocaleString()}`
            : undefined
        }
      >
        <Button asChild size="sm" variant="outline">
          <Link href="/variants">
            <ArrowLeft className="h-4 w-4" />
            {t("run.back")}
          </Link>
        </Button>
      </PageHeader>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : !run ? (
        <div className="text-sm text-muted-foreground">{t("common.loading")}</div>
      ) : (
        <>
          <QcDashboard run={run} />

          <AnnotationPanel
            runId={run.id}
            projectId={run.project_id}
            runReferenceBuild={run.reference_build}
          />

          <IntegrationReadiness runId={run.id} />

          <section className="rounded-lg border border-border">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">
                {t("run.somaticN", { n: candidates.length })}
              </h2>
              <div className="flex flex-wrap gap-1">
                {CLASSIFICATIONS.map((item) => (
                  <Button
                    key={item}
                    size="sm"
                    variant={classification === item ? "secondary" : "ghost"}
                    onClick={() => setClassification(item)}
                  >
                    {t(CLASSIFICATION_LABELS[item] ?? item.replace(/_/g, " "))}
                  </Button>
                ))}
              </div>
            </div>
            {candidates.length === 0 ? (
              <div className="px-5 py-8 text-sm text-muted-foreground">
                {t("run.noSomatic")}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("run.col.locus")}</TableHead>
                    <TableHead>{t("run.col.change")}</TableHead>
                    <TableHead>{t("run.classification")}</TableHead>
                    <TableHead>{t("run.col.tumorAfDepth")}</TableHead>
                    <TableHead>{t("run.col.normalAfDepth")}</TableHead>
                    <TableHead>{t("run.col.genotypeTn")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {candidates.map((candidate) => (
                    <TableRow key={candidate.id}>
                      <TableCell className="tabular text-xs">
                        {candidate.chromosome}:{candidate.position}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {candidate.reference}&gt;{candidate.alternate}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={candidate.classification} />
                      </TableCell>
                      <TableCell className="tabular text-xs">
                        {formatAf(candidate.tumor_allele_frequency)} /{" "}
                        {candidate.tumor_depth ?? "—"}
                      </TableCell>
                      <TableCell className="tabular text-xs">
                        {formatAf(candidate.normal_allele_frequency)} /{" "}
                        {candidate.normal_depth ?? "—"}
                      </TableCell>
                      <TableCell className="tabular text-xs">
                        {candidate.tumor_genotype ?? "—"} /{" "}
                        {candidate.normal_genotype ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </section>

          <section className="rounded-lg border border-border">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">
                {t("run.variantsN", { n: variants.length })}
              </h2>
              <div className="flex flex-wrap items-center gap-1">
                {["ALL", "TUMOR", "NORMAL"].map((item) => (
                  <Button
                    key={item}
                    size="sm"
                    variant={role === item ? "secondary" : "ghost"}
                    onClick={() => setRole(item)}
                  >
                    {t(ROLE_LABELS[item] ?? item)}
                  </Button>
                ))}
                <Button
                  size="sm"
                  variant={validOnly ? "secondary" : "ghost"}
                  onClick={() => setValidOnly((v) => !v)}
                >
                  {t("run.validOnly")}
                </Button>
                <Button
                  size="sm"
                  variant={includeDuplicates ? "ghost" : "secondary"}
                  onClick={() => setIncludeDuplicates((v) => !v)}
                >
                  {t("run.hideDuplicates")}
                </Button>
              </div>
            </div>
            {variants.length === 0 ? (
              <div className="px-5 py-8 text-sm text-muted-foreground">
                {t("run.noVariants")}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("run.col.role")}</TableHead>
                    <TableHead>{t("run.col.locus")}</TableHead>
                    <TableHead>{t("run.col.change")}</TableHead>
                    <TableHead>{t("run.col.type")}</TableHead>
                    <TableHead>{t("run.col.dp")}</TableHead>
                    <TableHead>{t("run.col.af")}</TableHead>
                    <TableHead>{t("run.col.gt")}</TableHead>
                    <TableHead>{t("run.col.flags")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {variants.slice(0, 500).map((variant) => (
                    <TableRow key={variant.id}>
                      <TableCell className="text-xs">{t(ROLE_LABELS[variant.sample_role] ?? variant.sample_role)}</TableCell>
                      <TableCell className="tabular text-xs">
                        <Link
                          href={`/variants/${run.id}/variant/${variant.id}`}
                          className="hover:text-foreground hover:underline"
                        >
                          {variant.chromosome_normalized ?? variant.chromosome}:
                          {variant.position ?? "—"}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {variant.reference ?? "—"}&gt;{variant.alternate ?? "—"}
                      </TableCell>
                      <TableCell className="text-xs">
                        {variant.variant_type ?? "—"}
                      </TableCell>
                      <TableCell className="tabular text-xs">
                        {variant.depth ?? "—"}
                      </TableCell>
                      <TableCell className="tabular text-xs">
                        {formatAf(variant.allele_frequency)}
                      </TableCell>
                      <TableCell className="tabular text-xs">
                        {variant.genotype ?? "—"}
                      </TableCell>
                      <TableCell className="text-xs">
                        {!variant.is_valid ? (
                          <span className="text-red-600">
                            {variant.invalid_reason}
                          </span>
                        ) : variant.is_duplicate ? (
                          <span className="text-amber-600">{t("run.flag.dup")}</span>
                        ) : variant.chromosome_normalized_flag ? (
                          <span className="text-muted-foreground">
                            {t("run.flag.chr")}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">{t("run.flag.ok")}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </section>
        </>
      )}
    </div>
  );
}
