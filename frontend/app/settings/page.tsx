"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Image as ImageIcon, RotateCcw } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { useTheme, type Theme } from "@/components/theme-provider";
import { GlassSegmented } from "@/components/ui/segmented";
import { Button } from "@/components/ui/button";
import { FileInput } from "@/components/ui/file-input";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useI18n, type Lang } from "@/lib/i18n";
import { playSound, setSoundEnabled, soundEnabled } from "@/lib/sound";
import {
  enterFullscreen,
  exitFullscreen,
  fullscreenSupported,
  isFullscreen,
  setFullscreenPref,
  subscribeFullscreenChange,
} from "@/lib/fullscreen";
import {
  applyPrefs,
  loadPrefs,
  resetPrefs,
  savePrefs,
  type BackdropPref,
  type FontSizePref,
} from "@/lib/ui-preferences";
import { useToast } from "@/components/toast";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

const MAX_CUSTOM_IMAGE_BYTES = 3 * 1024 * 1024;

export default function SettingsPage() {
  const { lang, setLang, t } = useI18n();
  const { theme, setTheme } = useTheme();
  const { push } = useToast();
  const [sound, setSound] = useState(soundEnabled());
  const [prefs, setPrefs] = useState(loadPrefs());
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenReady, setFullscreenReady] = useState(false);

  useEffect(() => {
    applyPrefs(prefs);
  }, [prefs]);

  useEffect(() => {
    setFullscreen(isFullscreen());
    setFullscreenReady(fullscreenSupported());
    return subscribeFullscreenChange(() => setFullscreen(isFullscreen()));
  }, []);

  const appearanceOptions: { value: Theme; label: string }[] = [
    { value: "light", label: t("settings.light") },
    { value: "dark", label: t("settings.dark") },
    { value: "system", label: t("settings.system") },
  ];

  const options: { value: Lang; label: string }[] = [
    { value: "en", label: t("settings.english") },
    { value: "zh", label: t("settings.chinese") },
    { value: "ru", label: t("settings.russian") },
    { value: "fr", label: t("settings.french") },
    { value: "de", label: t("settings.german") },
  ];

  const soundOptions: { value: string; label: string }[] = [
    { value: "on", label: t("settings.sound.on") },
    { value: "off", label: t("settings.sound.off") },
  ];

  const fullscreenOptions: { value: string; label: string }[] = [
    { value: "on", label: t("settings.fullscreen.on") },
    { value: "off", label: t("settings.fullscreen.off") },
  ];

  const fontOptions: { value: FontSizePref; label: string }[] = [
    { value: "sm", label: t("settings.font.small") },
    { value: "md", label: t("settings.font.medium") },
    { value: "lg", label: t("settings.font.large") },
  ];

  const backdropOptions: { value: BackdropPref; label: string }[] = [
    { value: "photo", label: t("settings.backdrop.photo") },
    { value: "gradient", label: t("settings.backdrop.gradient") },
    { value: "solid", label: t("settings.backdrop.solid") },
    { value: "custom", label: t("settings.backdrop.custom") },
  ];

  function update(next: Partial<typeof prefs>) {
    const merged = { ...prefs, ...next };
    setPrefs(merged);
    savePrefs(merged);
    playSound("select");
  }

  function handleCustomImage(file: File | null) {
    if (!file) return;
    if (file.size > MAX_CUSTOM_IMAGE_BYTES) {
      push(t("settings.backdrop.customTooLarge"), "error");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const data = typeof reader.result === "string" ? reader.result : null;
      if (!data) return;
      update({ backdrop: "custom", customImage: data });
      push(t("settings.backdrop.customApplied"), "success");
    };
    reader.readAsDataURL(file);
  }

  function handleReset() {
    const defaults = resetPrefs();
    setPrefs(defaults);
    playSound("success");
    push(t("settings.resetDone"), "success");
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("page.settings.title")} description={t("page.settings.desc")}>
        <Button size="sm" variant="outline" onClick={handleReset}>
          <RotateCcw className="h-4 w-4" />
          {t("settings.reset")}
        </Button>
      </PageHeader>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.sound.title")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <p className="text-xs text-muted-foreground">{t("settings.sound.desc")}</p>
          <GlassSegmented
            options={soundOptions}
            value={sound ? "on" : "off"}
            onChange={(value) => {
              const enabled = value === "on";
              setSound(enabled);
              setSoundEnabled(enabled);
              if (enabled) playSound("success");
            }}
          />
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.font.title")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <p className="text-xs text-muted-foreground">{t("settings.font.desc")}</p>
          <GlassSegmented
            options={fontOptions}
            value={prefs.fontSize}
            onChange={(value) => update({ fontSize: value })}
          />
          <div className="text-[11px] text-muted-foreground">
            {t("settings.font.preview")}
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.backdrop.title")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <p className="text-xs text-muted-foreground">{t("settings.backdrop.desc")}</p>
          <GlassSegmented
            options={backdropOptions}
            value={prefs.backdrop}
            onChange={(value) => update({ backdrop: value })}
          />
          {prefs.backdrop === "custom" ? (
            <div className="space-y-3">
              <div className="max-w-md space-y-2">
                <Label>{t("settings.backdrop.customUpload")}</Label>
                <FileInput accept="image/*" onChange={handleCustomImage} />
              </div>
              {prefs.customImage ? (
                <div className="flex items-center gap-3">
                  <Image
                    src={prefs.customImage}
                    alt=""
                    width={96}
                    height={56}
                    unoptimized
                    className="h-14 w-24 rounded-lg border border-border object-cover"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      update({ backdrop: "photo", customImage: null })
                    }
                  >
                    <ImageIcon className="h-4 w-4" />
                    {t("settings.backdrop.customRemove")}
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.blur.title")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <p className="text-xs text-muted-foreground">{t("settings.blur.desc")}</p>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={prefs.blur}
              onChange={(e) => update({ blur: Number(e.target.value) })}
              className="h-2 w-full max-w-md cursor-pointer accent-[rgb(0,122,255)]"
              aria-label={t("settings.blur.title")}
            />
            <span className="tabular text-xs text-muted-foreground">{prefs.blur}</span>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.language")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <p className="text-xs text-muted-foreground">{t("settings.language.desc")}</p>
          <div className="flex flex-wrap gap-2">
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setLang(option.value)}
                className={
                  "rounded-md border px-4 py-2 text-sm font-medium transition-colors " +
                  (lang === option.value
                    ? "border-foreground bg-secondary text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground")
                }
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.appearance")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <p className="text-xs text-muted-foreground">
            {t("settings.appearance.desc")}
          </p>
          <GlassSegmented
            options={appearanceOptions}
            value={theme}
            onChange={setTheme}
          />
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.fullscreen.title")}</h2>
        </div>
        <div className="space-y-4 p-5">
          <p className="text-xs text-muted-foreground">
            {t("settings.fullscreen.desc")}
          </p>
          <GlassSegmented
            options={fullscreenOptions}
            value={fullscreen ? "on" : "off"}
            onChange={async (value) => {
              if (value === "on") {
                const ok = await enterFullscreen();
                setFullscreenPref(ok);
                if (!ok) push(t("settings.fullscreen.denied"), "error");
              } else {
                await exitFullscreen();
                setFullscreenPref(false);
              }
            }}
          />
          {!fullscreenReady ? (
            <p className="text-xs text-muted-foreground">
              {t("settings.fullscreen.unsupported")}
            </p>
          ) : null}
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.api")}</h2>
        </div>
        <div className="max-w-xl space-y-2 p-5">
          <Label htmlFor="api-url">API endpoint</Label>
          <Input id="api-url" value={API_URL} readOnly className="font-mono text-xs" />
          <p className="text-xs text-muted-foreground">{t("settings.api.desc")}</p>
        </div>
      </section>

      <section className="rounded-lg border border-border">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">{t("settings.about")}</h2>
        </div>
        <div className="space-y-1 p-5 text-xs text-muted-foreground">
          <div className="text-sm font-semibold tracking-[0.12em] text-foreground">
            Bravo
          </div>
          <div>{t("settings.about.text")}</div>
        </div>
      </section>
    </div>
  );
}
