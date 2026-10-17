"use client";

import { Fragment, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Ban,
  Check,
  ClipboardCheck,
  Dna,
  FileText,
  Fingerprint,
  Info,
  Microscope,
  Tags,
  X,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { ComputeConsole } from "@/components/compute-console";
import { StatusBadge } from "@/components/status-badge";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import {
  COMPARISON_ROWS,
  PIPELINE_STEPS,
  PIPELINE_TEXT,
  pick,
} from "@/lib/pipeline-content";

type StageResult = { step: string; status: string; detail?: string | null };
type StepState = "done" | "running" | "failed" | "blocked" | "pending";

function formatDuration(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

const STEP_ICONS: Record<string, LucideIcon> = {
  VCF_QC: ClipboardCheck,
  ANNOTATION: Tags,
  HLA: Fingerprint,
  EXPRESSION: Activity,
  NEOANTIGEN: Microscope,
  CONSTRUCT: Dna,
  REPORT: FileText,
};

const NODE_CLASS: Record<StepState, string> = {
  done: "border-transparent bg-accent text-accent-foreground",
  running: "border-accent/40 bg-accent/10 text-accent",
  failed: "border-transparent bg-destructive text-destructive-foreground",
  blocked: "border-transparent bg-amber-500 text-white",
  pending: "border-border bg-secondary/60 text-muted-foreground",
};

const CHIP_CLASS: Record<StepState, string> = {
  done: "bg-emerald-500/12 text-emerald-600",
  running: "bg-accent/12 text-accent",
  failed: "bg-destructive/12 text-destructive",
  blocked: "bg-amber-500/15 text-amber-600",
  pending: "bg-secondary/70 text-muted-foreground",
};

const DOT_CLASS: Record<StepState, string> = {
  done: "bg-emerald-500",
  running: "bg-accent animate-pulse",
  failed: "bg-destructive",
  blocked: "bg-amber-500",
  pending: "bg-muted-foreground/40",
};

/**
 * Time chips own the 1-second tick so the rest of the pipeline (including the
 * comparison table) does not re-render every second.
 */
function TimeChips({
  running,
  startedAt,
  fraction,
}: {
  running: boolean;
  startedAt: number | null;
  fraction: number;
}) {
  const { t } = useI18n();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setNow(Date.now());
  }, [startedAt]);

  useEffect(() => {
    if (!running) {
      setNow(Date.now());
      return;
    }
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [running]);

  const elapsedMs = startedAt ? Math.max(0, (running ? now : Date.now()) - startedAt) : 0;
  const remainingMs =
    running && startedAt && fraction > 0
      ? Math.max(0, elapsedMs / fraction - elapsedMs)
      : null;
  const etaClock =
    remainingMs != null
      ? new Date(now + remainingMs).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;

  if (!startedAt && !running) return null;
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] tabular text-muted-foreground">
      {startedAt ? <span>{t("pipe.elapsed", { time: formatDuration(elapsedMs) })}</span> : null}
      {running ? (
        remainingMs != null && etaClock ? (
          <span>{t("pipe.eta", { time: formatDuration(remainingMs), clock: etaClock })}</span>
        ) : (
          <span>{t("pipe.etaPending")}</span>
        )
      ) : null}
    </div>
  );
}

/**
 * Step node and label are MODULE-LEVEL components on purpose: defining them
 * inside OneClickPipeline would give them a new identity on every parent
 * render (which happens on each poll), making React remount them and restart
 * the spinner animation from 0° — the visible "stuttering" rotation.
 */
function StepNode({
  i,
  state,
  active,
  lastDoneIndex,
  doneCount,
}: {
  i: number;
  state: StepState;
  active: boolean;
  lastDoneIndex: number;
  doneCount: number;
}) {
  const Icon = STEP_ICONS[PIPELINE_STEPS[i].id] ?? Dna;
  return (
    <span
      className={cn(
        "relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border transition-transform duration-200",
        NODE_CLASS[state],
        active && state !== "running" && "ring-4 ring-accent/25",
        active && "scale-[1.06]"
      )}
    >
      {state === "running" ? (
        <>
          <span aria-hidden className="pipeline-halo absolute inset-0 rounded-2xl bg-accent/30" />
          <span aria-hidden className="pipeline-spin absolute inset-0">
            <svg viewBox="0 0 48 48" className="h-full w-full text-accent" fill="none">
              <circle
                cx="24"
                cy="24"
                r="21"
                stroke="currentColor"
                strokeOpacity="0.18"
                strokeWidth="2.5"
              />
              <circle
                cx="24"
                cy="24"
                r="21"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeDasharray="36 96"
                transform="rotate(-90 24 24)"
              />
            </svg>
          </span>
          <Icon className="relative z-10 h-5 w-5" strokeWidth={1.75} />
        </>
      ) : state === "done" ? (
        <Check className="animate-check-pop h-5 w-5" strokeWidth={2.75} />
      ) : state === "failed" ? (
        <X className="h-5 w-5" strokeWidth={2.5} />
      ) : state === "blocked" ? (
        <AlertTriangle className="h-5 w-5" strokeWidth={2.25} />
      ) : (
        <Icon className="h-5 w-5" strokeWidth={1.75} />
      )}
      {state === "done" && i === lastDoneIndex ? (
        <span
          key={doneCount}
          aria-hidden
          className="pipeline-ping pointer-events-none absolute inset-0 rounded-2xl bg-accent/50"
        />
      ) : null}
    </span>
  );
}

function StepLabel({ i, state, active }: { i: number; state: StepState; active: boolean }) {
  const { lang, t } = useI18n();
  return (
    <span className="flex min-w-0 flex-col items-center gap-1">
      <span
        className={cn(
          "w-full truncate text-center text-[11px] font-medium leading-tight transition-colors",
          active ? "text-foreground" : "text-muted-foreground"
        )}
        title={pick(PIPELINE_STEPS[i].label, lang)}
      >
        {pick(PIPELINE_STEPS[i].label, lang)}
      </span>
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium",
          CHIP_CLASS[state]
        )}
      >
        <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASS[state])} />
        {t(`pipe.state.${state}`)}
      </span>
    </span>
  );
}

export function OneClickPipeline({
  stages,
  context,
  running = false,
  startedAt = null,
  cancelling = false,
  onCancel,
}: {
  stages: StageResult[];
  context: Record<string, string | number>;
  running?: boolean;
  startedAt?: number | null;
  cancelling?: boolean;
  onCancel?: () => void;
}) {
  const { lang, t } = useI18n();
  const [active, setActive] = useState(0);
  const [consoleOpen, setConsoleOpen] = useState(false);

  useEffect(() => {
    if (!consoleOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setConsoleOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [consoleOpen]);

  const byStep = new Map(stages.map((s) => [s.step, s]));
  const stageFor = (id: string, aliases?: string[]) => {
    if (byStep.has(id)) return byStep.get(id);
    for (const alias of aliases ?? []) {
      if (byStep.has(alias)) return byStep.get(alias);
    }
    return undefined;
  };

  const count = PIPELINE_STEPS.length;
  const step = PIPELINE_STEPS[active];
  const stage = stageFor(step.id, step.aliases);
  const doneCount = PIPELINE_STEPS.filter((s) => stageFor(s.id, s.aliases)).length;
  const percent = Math.round((doneCount / count) * 100);
  const fraction = doneCount / count;
  const paramKeys = Object.keys(context);
  const runningIndex = running
    ? PIPELINE_STEPS.findIndex((s) => !stageFor(s.id, s.aliases))
    : -1;
  const activeIsRunning = runningIndex >= 0 && active === runningIndex;
  const lastDoneIndex = doneCount - 1;

  const stateOf = (i: number): StepState => {
    const s = PIPELINE_STEPS[i];
    const st = stageFor(s.id, s.aliases);
    if (st) {
      const value = (st.status || "").toUpperCase();
      if (value === "FAILED") return "failed";
      if (value === "BLOCKED") return "blocked";
      return "done";
    }
    if (running && i === runningIndex) return "running";
    return "pending";
  };

  let overall = "PENDING";
  if (stages.some((s) => s.status === "FAILED")) overall = "FAILED";
  else if (stages.some((s) => s.status === "BLOCKED")) overall = "BLOCKED";
  else if (running) overall = "RUNNING";
  else if (doneCount === count) overall = "PASS";

  const connectorState = (i: number): StepState => {
    const state = stateOf(i);
    const nextState = i < count - 1 ? stateOf(i + 1) : "pending";
    if (state === "done" && nextState === "done") return "done";
    if (running && i + 1 === runningIndex) return "running";
    return "pending";
  };

  return (
    // NB: deliberately NOT a backdrop-filter ("glass") surface — a large
    // blurred panel with live animations forces the compositor to re-sample
    // the backdrop every frame and stutters. An opaque card is smooth.
    <section className="animate-rise overflow-hidden rounded-[28px] border border-border bg-card [box-shadow:0_12px_40px_rgba(15,23,42,0.10)]">
      {/* header + progress */}
      <div className="space-y-3 border-b border-border/60 px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-start gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-accent/15 text-accent">
            <Info className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
              {pick(PIPELINE_TEXT.sectionTitle, lang)}
              <StatusBadge status={overall} />
            </h2>
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
              {pick(PIPELINE_TEXT.hint, lang)}
            </p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right">
              <div className="tabular text-2xl font-semibold leading-none tracking-tight">
                {percent}
                <span className="text-sm text-muted-foreground">%</span>
              </div>
              <div className="mt-0.5 text-[11px] tabular text-muted-foreground">
                {doneCount}/{count} {t("pipe.steps")}
              </div>
            </div>
            {onCancel && (running || cancelling) ? (
              <Button
                size="sm"
                variant="outline"
                onClick={onCancel}
                disabled={cancelling}
                className="shrink-0"
              >
                <Ban className="h-3.5 w-3.5" />
                {cancelling ? t("gen.cancelling") : t("gen.cancelRun")}
              </Button>
            ) : null}
          </div>
        </div>

        <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary/70">
          <div
            className="h-full w-full origin-left rounded-full bg-gradient-to-r from-accent to-accent/70 transition-transform duration-700 ease-out"
            style={{ transform: `scaleX(${percent / 100})` }}
          />
        </div>

        <TimeChips running={running} startedAt={startedAt} fraction={fraction} />
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        {/* horizontal stepper (>= sm) */}
        <div className="hidden items-start sm:flex">
          {PIPELINE_STEPS.map((s, i) => {
            const connector = connectorState(i);
            return (
              <Fragment key={s.id}>
                <button
                  type="button"
                  onClick={() => setActive(i)}
                  style={{ animationDelay: `${i * 60}ms` }}
                  className="pipeline-node-in flex w-[84px] shrink-0 flex-col items-center gap-2 rounded-2xl px-0.5 transition-transform hover:-translate-y-0.5"
                >
                  <StepNode
                    i={i}
                    state={stateOf(i)}
                    active={i === active}
                    lastDoneIndex={lastDoneIndex}
                    doneCount={doneCount}
                  />
                  <StepLabel i={i} state={stateOf(i)} active={i === active} />
                </button>
                {i < count - 1 ? (
                  <span className="relative mt-[23px] flex h-[3px] min-w-[10px] flex-1 items-center overflow-hidden rounded-full bg-border/70">
                    <span
                      className={cn(
                        "h-full w-full origin-left rounded-full bg-gradient-to-r from-accent to-accent/60 transition-transform duration-700 ease-out",
                        connector === "done" ? "scale-x-100" : "scale-x-0"
                      )}
                    />
                  </span>
                ) : null}
              </Fragment>
            );
          })}
        </div>

        {/* vertical timeline (< sm) */}
        <ol className="sm:hidden">
          {PIPELINE_STEPS.map((s, i) => {
            const connector = connectorState(i);
            return (
              <li key={s.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div style={{ animationDelay: `${i * 60}ms` }} className="pipeline-node-in">
                    <StepNode
                      i={i}
                      state={stateOf(i)}
                      active={i === active}
                      lastDoneIndex={lastDoneIndex}
                      doneCount={doneCount}
                    />
                  </div>
                  {i < count - 1 ? (
                    <span className="relative my-1 w-[3px] flex-1 overflow-hidden rounded-full bg-border/70">
                      <span
                        className={cn(
                          "block h-full w-full origin-top rounded-full bg-gradient-to-b from-accent to-accent/60 transition-transform duration-700 ease-out",
                          connector === "done" ? "scale-y-100" : "scale-y-0"
                        )}
                      />
                    </span>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => setActive(i)}
                  className="flex flex-1 items-start gap-2 pb-4 text-left"
                >
                  <StepLabel i={i} state={stateOf(i)} active={i === active} />
                </button>
              </li>
            );
          })}
        </ol>

        {/* selected step detail */}
        <div className="rounded-2xl border border-border/70 bg-secondary/20 p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold tracking-tight">
              {pick(step.label, lang)}
            </h3>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{pick(PIPELINE_TEXT.status, lang)}</span>
              <StatusBadge
                status={stage?.status ?? (activeIsRunning ? "RUNNING" : "PENDING")}
              />
            </div>
          </div>
          <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-muted-foreground">
            {pick(step.desc, lang)}
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="min-w-0 rounded-xl border border-border/70 bg-background/40 p-3">
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {pick(PIPELINE_TEXT.detail, lang)}
              </div>
              {stage?.detail ? (
                <div className="flex flex-wrap gap-1.5">
                  {String(stage.detail)
                    .split(" · ")
                    .filter(Boolean)
                    .map((part, index) => (
                      <span
                        key={index}
                        className="rounded-lg border border-border/70 bg-secondary/50 px-2 py-0.5 text-[12px] font-medium tabular"
                      >
                        {part}
                      </span>
                    ))}
                </div>
              ) : (
                <div className="text-[13px] text-muted-foreground">{t("common.none")}</div>
              )}
            </div>
            <div className="min-w-0 rounded-xl border border-border/70 bg-background/40 p-3">
              <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {pick(PIPELINE_TEXT.parameters, lang)}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {paramKeys.map((k) => (
                  <span
                    key={k}
                    className="rounded-full bg-secondary/70 px-2.5 py-0.5 text-[11px]"
                  >
                    <span className="text-muted-foreground">{t(k)} </span>
                    <span className="font-medium text-foreground">{context[k]}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* comparison */}
        <div className="space-y-3 border-t border-border/60 pt-5">
          <div className="space-y-1.5">
            <button
              type="button"
              onClick={() => setConsoleOpen(true)}
              title={t("pipe.consoleHint")}
              className="press -mx-2 block w-[calc(100%+1rem)] text-left sm:-mx-3 sm:w-[calc(100%+1.5rem)]"
            >
              <ComputeConsole
                stages={stages}
                running={running}
                startedAt={startedAt}
                provider={String(context["gen.provider"] ?? "mock")}
                annotationProvider={String(context["gen.annotationProvider"] ?? "mock")}
              />
            </button>
            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <h3 className="text-sm font-semibold tracking-tight">
                {pick(PIPELINE_TEXT.compareTitle, lang)}
              </h3>
              <span className="text-[11px] text-muted-foreground">
                {t("pipe.consoleHint")}
              </span>
            </div>
            <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">
              {pick(PIPELINE_TEXT.compareHint, lang)}
            </p>
          </div>
          <div className="overflow-x-auto rounded-2xl border border-border/70">
            <table className="w-full min-w-[720px] border-collapse text-left text-xs">
              <thead>
                <tr className="bg-secondary/50 text-muted-foreground">
                  <th className="px-4 py-2.5 font-semibold">
                    {pick(PIPELINE_TEXT.colDimension, lang)}
                  </th>
                  <th className="px-4 py-2.5 font-semibold">
                    {pick(PIPELINE_TEXT.colUs, lang)}
                  </th>
                  <th className="px-4 py-2.5 font-semibold">
                    {pick(PIPELINE_TEXT.colMainstream, lang)}
                  </th>
                  <th className="px-4 py-2.5 font-semibold">
                    {pick(PIPELINE_TEXT.colDiff, lang)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_ROWS.map((row, i) => (
                  <tr
                    key={i}
                    className={cn(
                      "border-t border-border/60 align-top",
                      i % 2 === 1 && "bg-secondary/20"
                    )}
                  >
                    <td className="px-4 py-3 font-semibold text-foreground">
                      {pick(row.dim, lang)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {pick(row.us, lang)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {pick(row.mainstream, lang)}
                    </td>
                    <td className="px-4 py-3 text-foreground/90">
                      {pick(row.diff, lang)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {consoleOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setConsoleOpen(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
        >
          <div
            onClick={(event) => event.stopPropagation()}
            className="relative w-[96vw] max-w-[1500px]"
          >
            <ComputeConsole
              stages={stages}
              running={running}
              startedAt={startedAt}
              provider={String(context["gen.provider"] ?? "mock")}
              annotationProvider={String(context["gen.annotationProvider"] ?? "mock")}
              fontSize={13}
              tall
            />
            <button
              type="button"
              onClick={() => setConsoleOpen(false)}
              aria-label={t("common.close")}
              className="press absolute -right-2 -top-2 flex h-9 w-9 items-center justify-center rounded-full border border-white/20 bg-black/60 text-white hover:bg-black/80"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
