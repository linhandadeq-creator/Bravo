"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useI18n();

  useEffect(() => {
    // Surface the error to the console for diagnostics; never hide it silently.
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <span className="lg-1 lg-edge flex h-12 w-12 items-center justify-center rounded-2xl text-amber-600">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <h1 className="text-[22px] font-semibold tracking-tight">
        {t("error.title")}
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">{t("error.desc")}</p>
      <Button onClick={reset} className="mt-1">
        {t("error.retry")}
      </Button>
    </div>
  );
}
