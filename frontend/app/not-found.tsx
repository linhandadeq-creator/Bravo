"use client";

import Link from "next/link";
import { Compass } from "lucide-react";

import { useI18n } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useI18n();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <span className="lg-1 lg-edge flex h-12 w-12 items-center justify-center rounded-2xl text-muted-foreground">
        <Compass className="h-6 w-6" />
      </span>
      <h1 className="text-[22px] font-semibold tracking-tight">{t("nf.title")}</h1>
      <p className="max-w-md text-sm text-muted-foreground">{t("nf.desc")}</p>
      <Link
        href="/"
        className="press lg-2 lg-edge mt-1 inline-flex items-center rounded-xl px-3.5 py-2 text-[13px] font-medium text-foreground"
      >
        {t("nf.home")}
      </Link>
    </div>
  );
}
