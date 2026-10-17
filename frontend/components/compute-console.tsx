"use client";

import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { PIPELINE_STEPS, pick } from "@/lib/pipeline-content";

type StageResult = { step: string; status: string; detail?: string | null };

const GREEN = new Set(["PASS", "ANNOTATED", "INGESTED", "VALIDATED_SIMULATION", "GENERATED", "AVAILABLE"]);
const AMBER = new Set(["MOCK", "SYNTHETIC_CONTEXT", "PARTIAL", "WARNING"]);
const RED = new Set(["FAILED", "BLOCKED", "UNAVAILABLE", "INVALID"]);

function statusClass(status: string): string {
  const s = status.toUpperCase();
  if (GREEN.has(s)) return "text-emerald-400";
  if (AMBER.has(s)) return "text-amber-400";
  if (RED.has(s)) return "text-red-400";
  return "text-white/50";
}

function stamp(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `+${pad(m)}:${pad(s)}`;
}

/**
 * Terminal-style window that scrolls the real backend computation as it runs.
 * Lines are derived from the pipeline stage events (step / status / output).
 */
export function ComputeConsole({
  stages,
  running,
  startedAt,
  provider,
  annotationProvider,
  className,
  fontSize = 12,
  tall = false,
}: {
  stages: StageResult[];
  running: boolean;
  startedAt: number | null;
  provider: string;
  annotationProvider: string;
  className?: string;
  fontSize?: number;
  tall?: boolean;
}) {
  const { lang, t } = useI18n();
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const seenRef = useRef<Map<string, number>>(new Map());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const map = seenRef.current;
    for (const stage of stages) {
      if (!map.has(stage.step)) map.set(stage.step, Date.now());
    }
  }, [stages]);

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [running]);

  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [stages, running, now]);

  const byStep = new Map(stages.map((s) => [s.step, s]));
  const stageFor = (id: string, aliases?: string[]) => {
    if (byStep.has(id)) return byStep.get(id);
    for (const alias of aliases ?? []) if (byStep.has(alias)) return byStep.get(alias);
    return undefined;
  };
  const runningIndex = running
    ? PIPELINE_STEPS.findIndex((s) => !stageFor(s.id, s.aliases))
    : -1;
  const elapsed = startedAt ? Math.max(0, (running ? now : Date.now()) - startedAt) : 0;

  const lines = PIPELINE_STEPS.map((s) => {
    const st = stageFor(s.id, s.aliases);
    if (!st) return null;
    const at = seenRef.current.get(st.step) ?? startedAt ?? Date.now();
    return {
      key: s.id,
      time: startedAt ? stamp(at - startedAt) : "·",
      label: pick(s.label, lang),
      status: st.status,
      detail: st.detail ?? "",
    };
  }).filter(Boolean) as {
    key: string;
    time: string;
    label: string;
    status: string;
    detail: string;
  }[];

  const runningStep = runningIndex >= 0 ? PIPELINE_STEPS[runningIndex] : null;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border border-white/10 bg-[#0a0e16] text-white shadow-inner",
        className
      )}
    >
      <div className="flex items-center gap-2 border-b border-white/10 bg-black/30 px-3 py-2">
        <span className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </span>
        <span className="ml-1 text-[11px] font-medium text-white/70">
          {t("pipe.consoleTitle")}
        </span>
        <span
          className={cn(
            "ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium",
            running ? "bg-accent/25 text-accent" : "bg-white/10 text-white/60"
          )}
        >
          {running ? t("pipe.consoleRunning") : t("pipe.consoleIdle")}
        </span>
        <span className="tabular text-[10px] text-white/50">{stamp(elapsed)}</span>
      </div>

      <div
        ref={bodyRef}
        className={cn(
          "space-y-0.5 overflow-y-auto px-3 py-2 leading-relaxed",
          tall ? "h-[72vh] max-h-none" : "h-72"
        )}
        style={{ fontSize }}
      >
        <div className="text-white/45">
          <span className="text-emerald-400">$</span> bravo one-click --provider{" "}
          <span className="text-white/80">{provider}</span> --annotation{" "}
          <span className="text-white/80">{annotationProvider}</span>
        </div>
        {lines.map((line) => (
          <div key={line.key} className="flex flex-wrap gap-x-2">
            <span className="tabular text-white/35">{line.time}</span>
            <span className="w-28 shrink-0 truncate text-white/70">{line.label}</span>
            <span className={cn("shrink-0 font-medium", statusClass(line.status))}>
              {line.status}
            </span>
            {line.detail ? (
              <span className="text-white/55">{line.detail}</span>
            ) : null}
          </div>
        ))}
        {runningStep ? (
          <div className="flex flex-wrap gap-x-2">
            <span className="tabular text-white/35">{stamp(elapsed)}</span>
            <span className="w-28 shrink-0 truncate text-white/70">
              {pick(runningStep.label, lang)}
            </span>
            <span className="flex items-center gap-1.5 text-accent">
              <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
              {t("pipe.consoleWorking")}
            </span>
          </div>
        ) : null}
        <div className="text-white/45">
          <span className="text-emerald-400">&gt;</span>{" "}
          <span className="inline-block h-3.5 w-1.5 animate-pulse bg-white/60 align-middle" />
        </div>
      </div>
    </div>
  );
}
