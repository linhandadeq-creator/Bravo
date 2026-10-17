"use client";

let audioContext: AudioContext | null = null;

const STORAGE_KEY = "bravo.sound";

export function soundEnabled(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(STORAGE_KEY) !== "0";
}

export function setSoundEnabled(enabled: boolean): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
}

function context(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!audioContext) audioContext = new Ctor();
  return audioContext;
}

function tone(
  freqStart: number,
  freqEnd: number,
  duration: number,
  gainValue: number,
  type: OscillatorType = "sine",
  when = 0
): void {
  const ctx = context();
  if (!ctx) return;
  const now = ctx.currentTime + when;
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(freqStart, now);
  oscillator.frequency.exponentialRampToValueAtTime(Math.max(1, freqEnd), now + duration);
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(gainValue, now + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
  oscillator.connect(gain).connect(ctx.destination);
  oscillator.start(now);
  oscillator.stop(now + duration + 0.02);
}

export type SoundName = "click" | "select" | "upload" | "success" | "error" | "nav" | "chime";

export function playSound(name: SoundName): void {
  if (!soundEnabled()) return;
  try {
    switch (name) {
      case "click":
        tone(880, 660, 0.06, 0.05, "sine");
        break;
      case "select":
        tone(520, 780, 0.09, 0.06, "sine");
        break;
      case "nav":
        tone(660, 880, 0.07, 0.05, "sine");
        break;
      case "upload":
        tone(440, 880, 0.16, 0.07, "sine");
        break;
      case "success":
        tone(660, 660, 0.09, 0.08, "sine");
        tone(880, 880, 0.1, 0.08, "sine", 0.09);
        tone(1320, 1320, 0.16, 0.06, "sine", 0.18);
        break;
      case "chime":
        tone(1568, 1568, 0.12, 0.05, "sine");
        break;
      case "error":
        tone(330, 220, 0.16, 0.07, "triangle");
        break;
    }
  } catch {
    // Audio is decorative — never break the UI for it.
  }
}

export function playClickIfEnabled(): void {
  playSound("click");
}
