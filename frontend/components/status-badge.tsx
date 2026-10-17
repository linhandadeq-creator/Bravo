"use client";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const STYLES: Record<string, string> = {
  PASS: "border-emerald-200 bg-emerald-50 text-emerald-700",
  FAILED: "border-amber-200 bg-amber-50 text-amber-700",
  BLOCKED: "border-red-200 bg-red-50 text-red-700",
  TUMOR_ONLY: "border-red-200 bg-red-50 text-red-700",
  NORMAL_ONLY: "border-border bg-secondary text-foreground",
  SHARED: "border-border bg-secondary text-foreground",
  UNCERTAIN: "border-amber-200 bg-amber-50 text-amber-700",
  active: "border-border bg-secondary text-foreground",
  VALID: "border-emerald-200 bg-emerald-50 text-emerald-700",
  INVALID: "border-red-200 bg-red-50 text-red-700",
  duplicate: "border-amber-200 bg-amber-50 text-amber-700",
  normalized: "border-border bg-secondary text-foreground",
  ANNOTATED: "border-emerald-200 bg-emerald-50 text-emerald-700",
  PARTIAL: "border-amber-200 bg-amber-50 text-amber-700",
  UNAVAILABLE: "border-red-200 bg-red-50 text-red-700",
  MOCK: "border-amber-200 bg-amber-50 text-amber-700",
  RANKED: "border-emerald-200 bg-emerald-50 text-emerald-700",
  PREDICTED: "border-border bg-secondary text-foreground",
  GENERATED: "border-border bg-secondary text-foreground",
  REJECTED: "border-border bg-secondary text-muted-foreground",
  PENDING: "border-border bg-secondary text-muted-foreground",
  RUNNING: "border-accent/40 bg-accent/10 text-accent",
  WARNING: "border-amber-200 bg-amber-50 text-amber-700",
  PRODUCTION_READY: "border-emerald-200 bg-emerald-50 text-emerald-700",
  DESIGN_FAILED: "border-red-200 bg-red-50 text-red-700",
};

const LABELS: Record<string, string> = {
  PASS: "通过",
  FAILED: "失败",
  BLOCKED: "已阻止",
  VALID: "有效",
  INVALID: "无效",
  duplicate: "重复",
  normalized: "已标准化",
  ANNOTATED: "已注释",
  PARTIAL: "部分",
  UNAVAILABLE: "不可用",
  MOCK: "模拟",
  RANKED: "已排序",
  PREDICTED: "已预测",
  GENERATED: "已生成",
  REJECTED: "已剔除",
  UNCERTAIN: "不确定",
  PENDING: "待处理",
  RUNNING: "进行中",
  WARNING: "警告",
  TUMOR_ONLY: "仅肿瘤",
  NORMAL_ONLY: "仅正常",
  SHARED: "共有",
  active: "进行中",
  DRAFT: "草稿",
  VALIDATED_SIMULATION: "模拟已验证",
  LOCKED: "已锁定",
  READY: "就绪",
  HLA_AVAILABLE: "HLA 可用",
  HLA_INVALID: "HLA 无效",
  HLA_UNAVAILABLE: "HLA 缺失",
  EXPRESSION_AVAILABLE: "表达谱可用",
  EXPRESSION_INVALID: "表达谱无效",
  EXPRESSION_UNAVAILABLE: "表达谱缺失",
  AVAILABLE: "可用",
  PRODUCTION_READY: "可生产",
  DESIGN_FAILED: "设计未通过",
};

const LABELS_EN: Record<string, string> = {
  PASS: "Pass",
  FAILED: "Failed",
  BLOCKED: "Blocked",
  VALID: "Valid",
  INVALID: "Invalid",
  duplicate: "Duplicate",
  normalized: "Normalized",
  ANNOTATED: "Annotated",
  PARTIAL: "Partial",
  UNAVAILABLE: "Unavailable",
  MOCK: "Mock",
  RANKED: "Ranked",
  PREDICTED: "Predicted",
  GENERATED: "Generated",
  REJECTED: "Rejected",
  UNCERTAIN: "Uncertain",
  PENDING: "Pending",
  RUNNING: "Running",
  WARNING: "Warning",
  TUMOR_ONLY: "Tumour-only",
  NORMAL_ONLY: "Normal-only",
  SHARED: "Shared",
  active: "Active",
  DRAFT: "Draft",
  VALIDATED_SIMULATION: "Validated",
  LOCKED: "Locked",
  READY: "Ready",
  HLA_AVAILABLE: "HLA available",
  HLA_INVALID: "HLA invalid",
  HLA_UNAVAILABLE: "HLA missing",
  EXPRESSION_AVAILABLE: "Expression available",
  EXPRESSION_INVALID: "Expression invalid",
  EXPRESSION_UNAVAILABLE: "Expression missing",
  AVAILABLE: "Available",
  PRODUCTION_READY: "Production ready",
  DESIGN_FAILED: "Design failed",
};

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const { lang } = useI18n();
  const labels = lang === "en" ? LABELS_EN : LABELS;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        STYLES[status] ?? "border-border bg-secondary text-foreground",
        status === "RUNNING" && "animate-pulse",
        className
      )}
    >
      {labels[status] ?? status.replace(/_/g, " ")}
    </span>
  );
}

export function CheckStatusDot({ status }: { status: string }) {
  const color =
    status === "pass"
      ? "bg-emerald-500"
      : status === "warn"
        ? "bg-amber-500"
        : "bg-red-500";
  return <span className={cn("inline-block h-1.5 w-1.5 rounded-full", color)} />;
}
