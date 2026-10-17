"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { fetchVariantDetail, type Variant, type VariantDetail } from "@/lib/api";
import {
  CONSEQUENCE_LABELS,
  IMPACT_LABELS,
  PROVIDER_LABELS,
  label,
} from "@/lib/labels";
import { useI18n } from "@/lib/i18n";

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="bg-background px-4 py-2.5">
      <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className={"mt-0.5 text-sm" + (mono ? " font-mono" : "")}>{value ?? "—"}</dd>
    </div>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
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

function evidencePanel(
  title: string,
  evidence: Variant | null,
  t: (key: string, params?: Record<string, string | number>) => string
) {
  if (!evidence) {
    return (
      <Panel title={title}>
        <div className="bg-background px-4 py-6 text-sm text-muted-foreground">
          {t("vd.noEvidence", { title })}
        </div>
      </Panel>
    );
  }
  return (
    <Panel title={title}>
      <Row label={t("vd.genotype")} value={evidence.genotype ?? "—"} />
      <Row label={t("vd.depth")} value={evidence.depth ?? "—"} />
      <Row
        label={t("vd.af")}
        value={
          evidence.allele_frequency === null
            ? "—"
            : evidence.allele_frequency.toFixed(3)
        }
      />
      <Row label={t("vd.quality")} value={evidence.quality ?? "—"} />
      <Row label={t("vd.filter")} value={evidence.filter ?? "—"} />
      <Row label={t("vd.variantType")} value={evidence.variant_type ?? "—"} />
      <Row
        label={t("vd.reference")}
        value={evidence.chromosome_normalized ?? evidence.chromosome}
      />
    </Panel>
  );
}

export default function VariantDetailPage() {
  const params = useParams<{ id: string; variantId: string }>();
  const runId = params?.id;
  const variantId = params?.variantId;

  const { t, lang } = useI18n();

  const [detail, setDetail] = useState<VariantDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !variantId) return;
    fetchVariantDetail(runId, variantId)
      .then(setDetail)
      .catch((err) =>
        setError(err instanceof Error ? err.message : t("vd.loadFailed"))
      );
  }, [runId, variantId, t]);

  const variant = detail?.variant;
  const annotation = detail?.annotation;
  const annotationRun = detail?.annotation_run;

  return (
    <div className="space-y-6">
      <PageHeader
        title={
          variant
            ? `${variant.chromosome_normalized ?? variant.chromosome}:${variant.position} ${variant.reference}>${variant.alternate}`
            : t("vd.variant")
        }
        description={runId ? `${t("run.title")} ${runId.slice(0, 8)}` : undefined}
      >
        <Button asChild size="sm" variant="outline">
          <Link href={`/variants/${runId}`}>
            <ArrowLeft className="h-4 w-4" />
            {t("vd.run")}
          </Link>
        </Button>
      </PageHeader>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : !detail ? (
        <div className="text-sm text-muted-foreground">{t("common.loading")}</div>
      ) : (
        <>
          <Panel title={t("vd.variant")}>
            <Row
              label={t("vd.locus")}
              value={`${variant?.chromosome_normalized ?? variant?.chromosome}:${variant?.position}`}
            />
            <Row label={t("vd.change")} value={`${variant?.reference}>${variant?.alternate}`} />
            <Row label={t("vd.variantType")} value={variant?.variant_type ?? "—"} />
            <Row label={t("vd.sampleRole")} value={variant?.sample_role ?? "—"} />
            <Row
              label={t("vd.chrNorm")}
              value={variant?.chromosome_normalized_flag ? t("vd.yes") : t("vd.no")}
            />
            <Row
              label={t("vd.validity")}
              value={
                variant?.is_valid ? (
                  variant?.is_duplicate ? (
                    <span className="text-amber-600">{t("vd.duplicate")}</span>
                  ) : (
                    t("vd.valid")
                  )
                ) : (
                  <span className="text-red-600">
                    {variant?.invalid_reason ?? t("vd.invalid")}
                  </span>
                )
              }
            />
          </Panel>

          {evidencePanel(t("vd.tumor"), detail.tumor_evidence, t)}
          {evidencePanel(t("vd.normal"), detail.normal_evidence, t)}

          <Panel title={t("vd.annotation")}>
            <Row
              label={t("common.status")}
              value={annotation ? <StatusBadge status={annotation.status} /> : t("vd.noAnnotation")}
            />
            <Row label={t("vd.gene")} value={annotation?.gene ?? "—"} />
            <Row label={t("vd.geneId")} value={annotation?.gene_id ?? "—"} />
            <Row label={t("vd.transcript")} value={annotation?.transcript ?? "—"} />
            <Row label={t("vd.transcriptId")} value={annotation?.transcript_id ?? "—"} />
            <Row label={t("vd.consequence")} value={label(CONSEQUENCE_LABELS, annotation?.consequence, lang)} />
            <Row label={t("vd.impact")} value={label(IMPACT_LABELS, annotation?.impact, lang)} />
            <Row label={t("vd.proteinChange")} value={annotation?.protein_change ?? "—"} />
            <Row label={t("vd.cdsPos")} value={annotation?.cds_position ?? "—"} />
            <Row
              label={t("vd.proteinPos")}
              value={annotation?.protein_position ?? "—"}
            />
            {annotation?.hgvs_c ? (
              <Row label={t("vd.hgvsC")} value={annotation.hgvs_c} mono />
            ) : null}
            {annotation?.hgvs_p ? (
              <Row label={t("vd.hgvsP")} value={annotation.hgvs_p} mono />
            ) : null}
            {annotation?.mutated_peptide ? (
              <Row label={t("vd.peptide")} value={annotation.mutated_peptide} mono />
            ) : null}
            {annotation?.known_variants?.length ? (
              <Row
                label={t("vd.known")}
                value={(annotation.known_variants ?? []).join(", ")}
              />
            ) : null}
            {annotation?.clinical_significance ? (
              <Row label={t("vd.clinSig")} value={annotation.clinical_significance} />
            ) : null}
          </Panel>

          <Panel title={t("vd.reference")}>
            <Row
              label={t("vd.vcfBuild")}
              value={annotationRun?.reference_build ?? "—"}
            />
            <Row
              label={t("vd.annBuild")}
              value={annotation?.reference_build ?? "—"}
            />
            <Row
              label={t("vd.transcriptSource")}
              value={annotation?.transcript_source ?? "—"}
            />
            <Row
              label={t("vd.annVersion")}
              value={annotation?.annotation_version ?? "—"}
            />
          </Panel>

          <Panel title={t("vd.provenance")}>
            <Row label={t("vd.provider")} value={label(PROVIDER_LABELS, annotation?.provider, lang)} />
            <Row label={t("vd.providerVersion")} value={annotation?.provider_version ?? "—"} />
            <Row label={t("common.referenceBuild")} value={annotation?.reference_build ?? "—"} />
            <Row
              label={t("vd.annVersion")}
              value={annotation?.annotation_version ?? "—"}
            />
            <Row
              label={t("vd.timestamp")}
              value={
                annotation?.annotation_timestamp
                  ? new Date(annotation.annotation_timestamp).toLocaleString()
                  : "—"
              }
            />
            <Row
              label={t("vd.inputHash")}
              value={
                <span className="break-all font-mono text-xs">
                  {annotation?.input_hash ?? "—"}
                </span>
              }
            />
            <Row
              label={t("vd.parameters")}
              value={
                <span className="break-all font-mono text-xs">
                  {annotation?.parameters
                    ? JSON.stringify(annotation.parameters)
                    : "{}"}
                </span>
              }
            />
            <Row
              label={t("vd.annRun")}
              value={annotationRun?.id?.slice(0, 8) ?? "—"}
            />
          </Panel>
        </>
      )}
    </div>
  );
}
