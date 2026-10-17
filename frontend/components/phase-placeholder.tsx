"use client";

import { Construction } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { useI18n } from "@/lib/i18n";

export function PhasePlaceholder({
  title,
  description,
  items,
}: {
  title: string;
  description: string;
  items: string[];
}) {
  const { lang } = useI18n();
  return (
    <div className="space-y-6">
      <PageHeader title={title} description={description} />
      <div className="rounded-lg border border-dashed border-border p-6">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Construction className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
          {lang === "en" ? "Planned for a later phase" : "计划在后续阶段实现"}
        </div>
        <ul className="mt-4 space-y-2">
          {items.map((item) => (
            <li
              key={item}
              className="flex items-center gap-2 text-sm text-muted-foreground"
            >
              <span className="h-1 w-1 rounded-full bg-muted-foreground/60" />
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
