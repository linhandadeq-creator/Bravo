"use client";

import { FileText, Paperclip } from "lucide-react";

import { Button } from "@/components/ui/button";
import { type ProjectFile } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export const FILE_KIND_LABELS: Record<string, string> = {
  TUMOR_VCF: "pf.kindTumorVcf",
  NORMAL_VCF: "pf.kindNormalVcf",
  HLA: "pf.kindHla",
  EXPRESSION: "pf.kindExpression",
};

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectFilesPanel({
  files,
  kinds,
  onUse,
  busy,
}: {
  files: ProjectFile[];
  kinds: string[];
  onUse: (file: ProjectFile) => void;
  busy?: boolean;
}) {
  const { t } = useI18n();
  const matched = files.filter((file) => kinds.includes(file.kind));
  if (matched.length === 0) return null;

  return (
    <section className="rounded-lg border border-border">
      <div className="flex items-center gap-2 border-b border-border px-5 py-3">
        <Paperclip className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
        <h2 className="text-sm font-semibold">{t("pf.title")}</h2>
      </div>
      <ul className="divide-y divide-border">
        {matched.map((file) => (
          <li
            key={file.id}
            className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5"
          >
            <div className="flex min-w-0 items-center gap-2.5">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0">
                <div className="truncate text-[13px] font-medium">{file.filename}</div>
                <div className="text-[11px] text-muted-foreground">
                  {t(FILE_KIND_LABELS[file.kind] ?? "pf.kindOther")} · {humanSize(file.file_size_bytes)}
                </div>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => onUse(file)}
            >
              {t("pf.use")}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
