// Persistence for the last one-click generation, so the result (including the
// vaccine sequence) survives module switches and page refreshes.

export interface OneClickPersisted {
  projectId?: string;
  startedAt?: number | null;
  jobId?: string | null;
  result?: unknown | null;
  liveStages?: unknown[] | null;
}

const KEY = "bravo.oneclick.last";

function defaultStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function loadOneClick(storage: Storage | null = defaultStorage()): OneClickPersisted | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as OneClickPersisted) : null;
  } catch {
    return null;
  }
}

export function saveOneClick(
  state: OneClickPersisted,
  storage: Storage | null = defaultStorage()
): boolean {
  if (!storage) return false;
  try {
    storage.setItem(KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function clearOneClick(storage: Storage | null = defaultStorage()): void {
  if (!storage) return;
  try {
    storage.removeItem(KEY);
  } catch {
    // ignore
  }
}

/**
 * A fresh, "empty" state must never overwrite a stored result: on mount the
 * persist effect can run before the restore effect's state is applied, which
 * would otherwise wipe the saved sequence.
 */
export function isEmptyState(state: OneClickPersisted): boolean {
  return !state.result && !state.jobId && !state.startedAt;
}

export function hasStoredResult(storage: Storage | null = defaultStorage()): boolean {
  const saved = loadOneClick(storage);
  return Boolean(saved?.result);
}
