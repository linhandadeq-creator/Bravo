"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertTriangle, ArrowLeft } from "lucide-react";

import { PageHeader } from "@/components/page-header";
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
import { fetchCandidateDetail, type CandidateDetail } from "@/lib/api";
import { CONSEQUENCE_LABELS, PROVIDER_LABELS, label } from "@/lib/labels";
import { useI18n } from "@/lib/i18n";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-background px-4 py-2.5">
      <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm">{value ?? "—"}</dd>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-border">
      <div className="border-b border-border px-5 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
      </div>
      <dl className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2">
        {children}
      </dl>
    </section>
  );
}

export default function CandidateDetailPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ candidateId: string }>();
  const candidateId = params?.candidateId;
  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!candidateId) return;
    fetchCandidateDetail(candidateId)
      .then(setDetail)
      .catch((err) =>
        setError(err instanceof Error ? err.message : t("cd.loadFailed"))
      );
  }, [candidateId, t]);

  const candidate = detail?.candidate;

  return (
    <div className="space-y-6">
      <PageHeader
        title={candidate ? `${candidate.gene ?? t("cd.candidate")} ${candidate.protein_change ?? ""}` : t("cd.candidate")}
        description={
          candidate
            ? `${candidate.hla_allele ?? "—"} · ${candidate.id.slice(0, 8)}`
            : undefined
        }
      >
        <Button asChild size="sm" variant="outline">
          <Link href="/neoantigens">
            <ArrowLeft className="h-4 w-4" />
            {t("nav.neoantigens")}
          </Link>
        </Button>
      </PageHeader>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : !detail || !candidate ? (
        <div className="text-sm text-muted-foreground">{t("common.loading")}</div>
      ) : (
        <>
          <div
            className={
              "flex items-start gap-3 rounded-lg border px-4 py-3 text-xs " +
              (detail.provider_is_mock
                ? "border-amber-200 bg-amber-50 text-amber-800"
                : "border-border bg-secondary/40 text-muted-foreground")
            }
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              {detail.provider_is_mock
                ? t("cd.mockNote")
                : t("cd.providerPrefix")}
              {detail.disclaimer}
            </span>
          </div>

          <Panel title={t("cd.candidate")}>
            <Row label={t("cd.candidateId")} value={<span className="font-mono text-xs">{candidate.id}</span>} />
            <Row label={t("common.status")} value={<StatusBadge status={candidate.status} />} />
            <Row
              label={t("cd.predStatus")}
              value={<StatusBadge status={candidate.prediction_status} />}
            />
            <Row label={t("cd.peptideRep")} value={<span className="font-mono text-xs">{candidate.peptide_representation}</span>} />
            <Row label={t("cd.peptideSeq")} value={<span className="font-mono text-xs">{candidate.peptide_sequence ?? "—"}</span>} />
            <Row label="HLA" value={`${candidate.hla_allele ?? "—"}${t("cd.hlaClass", { c: candidate.hla_class ?? "—" })}`} />
          </Panel>

          <Panel title={t("cd.variant")}>
            <Row
              label={t("cd.locus")}
              value={
                detail.variant
                  ? `${detail.variant.chromosome_normalized ?? detail.variant.chromosome}:${detail.variant.position}`
                  : "—"
              }
            />
            <Row
              label={t("cd.change")}
              value={
                detail.variant
                  ? `${detail.variant.reference}>${detail.variant.alternate}`
                  : "—"
              }
            />
            <Row label={t("cd.variantType")} value={detail.variant?.variant_type ?? "—"} />
            <Row
              label={t("cd.genotype")}
              value={detail.variant?.genotype ?? "—"}
            />
          </Panel>

          <Panel title={t("cd.annotation")}>
            <Row label={t("cd.gene")} value={candidate.gene ?? "—"} />
            <Row label={t("cd.geneId")} value={candidate.gene_id ?? "—"} />
            <Row label={t("cd.transcript")} value={candidate.transcript ?? "—"} />
            <Row label={t("cd.transcriptId")} value={candidate.transcript_id ?? "—"} />
            <Row label={t("cd.consequence")} value={label(CONSEQUENCE_LABELS, candidate.consequence, lang)} />
            <Row label={t("cd.proteinChange")} value={candidate.protein_change ?? "—"} />
            <Row
              label={t("cd.annProvider")}
              value={
                detail.annotation?.provider
                  ? label(PROVIDER_LABELS, detail.annotation.provider, lang)
                  : "—"
              }
            />
            <Row
              label={t("cd.annProviderVersion")}
              value={detail.annotation?.provider_version ?? "—"}
            />
            {candidate.peptide_sequence ? (
              <Row label={t("vd.peptide")} value={candidate.peptide_sequence} />
            ) : null}
            {detail.annotation?.hgvs_c ? (
              <Row label={t("vd.hgvsC")} value={detail.annotation.hgvs_c} />
            ) : null}
            {detail.annotation?.hgvs_p ? (
              <Row label={t("vd.hgvsP")} value={detail.annotation.hgvs_p} />
            ) : null}
            {detail.annotation?.known_variants?.length ? (
              <Row
                label={t("vd.known")}
                value={(detail.annotation.known_variants ?? []).join(", ")}
              />
            ) : null}
            {detail.annotation?.clinical_significance ? (
              <Row
                label={t("vd.clinSig")}
                value={detail.annotation.clinical_significance}
              />
            ) : null}
          </Panel>

          <Panel title={t("cd.exprEvidence")}>
            <Row label={t("cd.geneSymbol")} value={candidate.expression_evidence?.gene_symbol ?? "—"} />
            <Row
              label={t("cd.expression")}
              value={
                candidate.expression_evidence?.expression_value != null
                  ? `${candidate.expression_evidence.expression_value} ${candidate.expression_evidence.unit ?? ""}`
                  : "—"
              }
            />
            <Row label={t("cd.source")} value={candidate.expression_evidence?.source ?? "—"} />
            <Row label={t("common.status")} value={candidate.expression_evidence?.status ?? "—"} />
          </Panel>

          <Panel title={t("cd.mutEvidence")}>
            <Row label={t("cd.somaticClass")} value={candidate.mutation_evidence?.classification ?? "—"} />
            <Row
              label={t("cd.tumorAf")}
              value={candidate.mutation_evidence?.tumor_allele_frequency ?? "—"}
            />
            <Row
              label={t("cd.normalAf")}
              value={candidate.mutation_evidence?.normal_allele_frequency ?? "—"}
            />
            <Row label={t("cd.tumorDepth")} value={candidate.mutation_evidence?.tumor_depth ?? "—"} />
            <Row label={t("cd.quality")} value={candidate.mutation_evidence?.quality ?? "—"} />
            <Row label={t("cd.filter")} value={candidate.mutation_evidence?.filter ?? "—"} />
          </Panel>

          <section className="rounded-lg border border-border">
            <div className="border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">
                {t("cd.predictions", { n: detail.predictions.length })}
              </h2>
            </div>
            {detail.predictions.length === 0 ? (
              <div className="px-5 py-6 text-sm text-muted-foreground">
                {t("cd.noPredictions")} {t("cd.predStatus")}:{" "}
                <span className="text-red-600">
                  {candidate.prediction_status === "UNAVAILABLE"
                    ? t("cd.predUnavailable")
                    : candidate.prediction_status}
                </span>
                .
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("cd.col.metric")}</TableHead>
                    <TableHead>{t("cd.col.value")}</TableHead>
                    <TableHead>{t("cd.col.provider")}</TableHead>
                    <TableHead>{t("cd.col.version")}</TableHead>
                    <TableHead>{t("cd.col.status")}</TableHead>
                    <TableHead>{t("cd.col.inputHash")}</TableHead>
                    <TableHead>{t("cd.col.timestamp")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.predictions.map((prediction) => (
                    <TableRow key={prediction.id}>
                      <TableCell className="text-xs">{prediction.metric_name}</TableCell>
                      <TableCell className="tabular text-xs">
                        {prediction.prediction_value}
                      </TableCell>
                      <TableCell className="text-xs">
                        {prediction.provider
                          ? label(PROVIDER_LABELS, prediction.provider, lang)
                          : "—"}
                      </TableCell>
                      <TableCell className="text-xs">
                        {prediction.provider_version}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={prediction.status ?? "—"} />
                      </TableCell>
                      <TableCell className="font-mono text-[11px]">
                        {prediction.input_hash?.slice(0, 16)}
                      </TableCell>
                      <TableCell className="tabular text-xs">
                        {prediction.timestamp
                          ? new Date(prediction.timestamp).toLocaleString()
                          : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </section>

          <Panel title={t("cd.ranking")}>
            <Row
              label={t("cd.score")}
              value={
                <span className="text-base font-semibold">
                  {candidate.ranking_score ?? "—"}
                </span>
              }
            />
            <Row
              label={t("cd.config")}
              value={
                <span className="font-mono text-xs">
                  {candidate.ranking_configuration_id ?? "—"}
                </span>
              }
            />
            <Row
              label={t("cd.components")}
              value={
                <span className="font-mono text-xs">
                  {JSON.stringify(candidate.ranking_evidence?.components ?? {})}
                </span>
              }
            />
            <Row
              label={t("cd.weights")}
              value={
                <span className="font-mono text-xs">
                  {JSON.stringify(candidate.ranking_evidence?.weights ?? {})}
                </span>
              }
            />
            <Row
              label={t("cd.rankingVersion")}
              value={candidate.ranking_evidence?.version ?? "—"}
            />
            <Row
              label={t("cd.annProvider")}
              value={`${
                detail.provider
                  ? label(PROVIDER_LABELS, detail.provider, lang)
                  : "—"
              }${detail.provider_is_mock ? t("cd.mockSuffix") : ""}`}
            />
          </Panel>
        </>
      )}
    </div>
  );
}
