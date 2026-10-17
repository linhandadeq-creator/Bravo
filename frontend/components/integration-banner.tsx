"use client";

import { AlertTriangle, Ban, CheckCircle2 } from "lucide-react";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function IntegrationBanner({
  status,
  message,
}: {
  status: string;
  message: string;
}) {
  const { lang } = useI18n();
  const labels: Record<string, { zh: string; en: string }> = {
    READY: { zh: "就绪", en: "Ready" },
    HLA_AVAILABLE: { zh: "HLA 可用", en: "HLA available" },
    HLA_INVALID: { zh: "HLA 无效", en: "HLA invalid" },
    HLA_UNAVAILABLE: { zh: "HLA 缺失", en: "HLA missing" },
    EXPRESSION_AVAILABLE: { zh: "表达谱可用", en: "Expression available" },
    EXPRESSION_INVALID: { zh: "表达谱无效", en: "Expression invalid" },
    EXPRESSION_UNAVAILABLE: { zh: "表达谱缺失", en: "Expression missing" },
  };
  const ok = status.endsWith("_AVAILABLE") || status === "READY";
  const invalid = status.endsWith("_INVALID");
  const tone = ok
    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
    : invalid
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : "border-red-200 bg-red-50 text-red-800";
  const Icon = ok ? CheckCircle2 : invalid ? AlertTriangle : Ban;
  const title =
    labels[status]?.[lang === "zh" ? "zh" : "en"] ?? status.replace(/_/g, " ");

  return (
    <div className={cn("flex items-start gap-3 rounded-lg border px-4 py-3", tone)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 space-y-0.5">
        <div className="text-sm font-semibold">{title}</div>
        <div className="text-xs leading-relaxed">{message}</div>
      </div>
    </div>
  );
}
