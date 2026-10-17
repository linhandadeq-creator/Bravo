"use client";

import { useRef, useState } from "react";
import { CircleAlert, Paperclip, UploadCloud } from "lucide-react";

import { playSound } from "@/lib/sound";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileInput({
  id,
  accept,
  onChange,
  validate,
  className,
}: {
  id?: string;
  accept?: string;
  onChange: (file: File | null) => void;
  validate?: (file: File) => string | null;
  className?: string;
}) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [size, setSize] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function accept_file(file: File | null) {
    if (!file) {
      setName("");
      setSize(null);
      setError(null);
      onChange(null);
      return;
    }
    const problem = validate ? validate(file) : null;
    if (problem) {
      playSound("error");
      setError(problem);
      setName("");
      setSize(null);
      onChange(null);
      return;
    }
    playSound("select");
    setError(null);
    setName(file.name);
    setSize(file.size);
    onChange(file);
  }

  return (
    <div className={cn("space-y-1", className)}>
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(event) => accept_file(event.target.files?.[0] ?? null)}
      />
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          accept_file(event.dataTransfer.files?.[0] ?? null);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer items-center gap-3 rounded-2xl border border-dashed px-4 py-3 text-[13px] transition-colors",
          dragging ? "border-accent bg-accent/5" : "border-border hover:bg-secondary/40",
          error && "border-destructive/50"
        )}
      >
        <span className="lg-1 lg-edge flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-muted-foreground">
          {dragging ? (
            <UploadCloud className="h-4 w-4 text-accent" />
          ) : (
            <Paperclip className="h-4 w-4" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium text-foreground">
            {name || t("common.chooseFile")}
          </span>
          <span className="block truncate text-[11px] text-muted-foreground">
            {name ? humanSize(size ?? 0) : t("common.dropHint")}
          </span>
        </span>
      </div>
      {error ? (
        <div className="flex items-center gap-1.5 text-[11px] text-destructive">
          <CircleAlert className="h-3.5 w-3.5" />
          {error}
        </div>
      ) : null}
    </div>
  );
}
