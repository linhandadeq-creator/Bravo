"use client";

import { useCallback, useEffect, useState } from "react";
import { Database as DatabaseIcon, RefreshCw, Trash2 } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/toast";
import {
  clearDatabaseTable,
  deleteDatabaseRows,
  fetchDatabaseOverview,
  fetchDatabaseTableRows,
  fetchDatabaseTables,
  type DatabaseOverview,
  type DatabaseTable,
  type DatabaseTableRows,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const PAGE_SIZE = 50;

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function cell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function DatabasePage() {
  const { t } = useI18n();
  const { push } = useToast();

  const [overview, setOverview] = useState<DatabaseOverview | null>(null);
  const [tables, setTables] = useState<DatabaseTable[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [data, setData] = useState<DatabaseTableRows | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    const [ov, tl] = await Promise.all([fetchDatabaseOverview(), fetchDatabaseTables()]);
    setOverview(ov);
    setTables(tl);
  }, []);

  const loadTable = useCallback(async (name: string, off: number) => {
    if (!name) {
      setData(null);
      return;
    }
    const rows = await fetchDatabaseTableRows(name, PAGE_SIZE, off);
    setData(rows);
    setChecked(new Set());
  }, []);

  useEffect(() => {
    loadOverview().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load database")
    );
  }, [loadOverview]);

  useEffect(() => {
    if (selected) void loadTable(selected, offset);
  }, [selected, offset, loadTable]);

  async function refresh() {
    setBusy(true);
    try {
      await loadOverview();
      if (selected) await loadTable(selected, offset);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh");
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (!data) return;
    const pk = data.primary_key[0];
    if (!pk) return;
    const ids = data.rows.map((row) => String(row[pk]));
    setChecked((prev) => (prev.size === ids.length ? new Set() : new Set(ids)));
  }

  async function deleteSelected() {
    if (!data || checked.size === 0) return;
    if (!window.confirm(t("db.deleteConfirm", { n: checked.size }))) return;
    setBusy(true);
    try {
      const result = await deleteDatabaseRows(data.name, [...checked]);
      push(t("db.deleted", { n: result.deleted }), "success");
      await loadOverview();
      await loadTable(selected, offset);
    } catch (err) {
      push(err instanceof Error ? err.message : "Delete failed", "error");
    } finally {
      setBusy(false);
    }
  }

  async function clearTable() {
    if (!data) return;
    if (!window.confirm(t("db.clearConfirm", { name: data.name, n: data.total }))) return;
    setBusy(true);
    try {
      const result = await clearDatabaseTable(data.name);
      push(t("db.cleared", { n: result.deleted }), "success");
      setOffset(0);
      await loadOverview();
      await loadTable(selected, 0);
    } catch (err) {
      push(err instanceof Error ? err.message : "Clear failed", "error");
    } finally {
      setBusy(false);
    }
  }

  const pk = data?.primary_key[0];
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const page = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-6">
      <PageHeader title={t("page.database.title")} description={t("page.database.desc")}>
        <Button size="sm" variant="outline" onClick={refresh} disabled={busy}>
          <RefreshCw className="h-4 w-4" />
          {t("db.refresh")}
        </Button>
      </PageHeader>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <section className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-3 lg:grid-cols-6">
        {[
          { label: t("db.engine"), value: overview?.engine ?? "—" },
          { label: t("db.journal"), value: overview?.journal_mode ?? "—" },
          { label: t("db.fileSize"), value: overview ? humanSize(overview.file_size_bytes) : "—" },
          { label: t("db.wal"), value: overview ? humanSize(overview.wal_size_bytes) : "—" },
          { label: t("db.tables"), value: overview?.table_count ?? "—" },
          { label: t("db.totalRows"), value: overview?.total_rows?.toLocaleString() ?? "—" },
        ].map((item) => (
          <div key={item.label} className="bg-background px-4 py-3">
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
              {item.label}
            </div>
            <div className="mt-0.5 tabular text-sm">{item.value}</div>
          </div>
        ))}
      </section>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <Card className="lg:max-h-[70vh] lg:overflow-y-auto">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DatabaseIcon className="h-4 w-4 text-muted-foreground" />
              {t("db.tables")}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-2">
            <ul className="space-y-0.5">
              {tables.map((table) => (
                <li key={table.name}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelected(table.name);
                      setOffset(0);
                    }}
                    className={
                      "flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left text-[13px] transition-colors " +
                      (selected === table.name
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground")
                    }
                  >
                    <span className="truncate font-medium">{table.name}</span>
                    <span className="tabular text-[11px]">{table.rows.toLocaleString()}</span>
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          {!data ? (
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              {t("db.selectTable")}
            </CardContent>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
                <h2 className="text-sm font-semibold">
                  <span className="font-mono">{data.name}</span>{" "}
                  <span className="text-muted-foreground">
                    · {t("db.records", { n: data.total.toLocaleString() })}
                  </span>
                </h2>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={toggleAll}
                    disabled={!pk || data.rows.length === 0}
                  >
                    {t("db.selectAll")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={deleteSelected}
                    disabled={busy || checked.size === 0}
                  >
                    <Trash2 className="h-4 w-4" />
                    {t("db.deleteSelected", { n: checked.size })}
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={clearTable}
                    disabled={busy || data.total === 0}
                  >
                    {t("db.clearTable")}
                  </Button>
                </div>
              </div>

              <div className="overflow-x-auto">
                {data.rows.length === 0 ? (
                  <div className="px-5 py-8 text-sm text-muted-foreground">{t("db.empty")}</div>
                ) : (
                  <table className="w-full border-collapse text-xs">
                    <thead>
                      <tr>
                        {pk ? <th className="w-8 px-3 py-2" /> : null}
                        {data.columns.map((col) => (
                          <th
                            key={col}
                            className="whitespace-nowrap border-b border-border px-3 py-2 text-left font-medium text-muted-foreground"
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.rows.map((row, index) => {
                        const id = pk ? String(row[pk]) : String(index);
                        return (
                          <tr key={id} className="border-b border-border/60 last:border-0">
                            {pk ? (
                              <td className="px-3 py-1.5 align-middle">
                                <input
                                  type="checkbox"
                                  checked={checked.has(id)}
                                  onChange={() => toggle(id)}
                                  className="h-3.5 w-3.5 accent-[rgb(0,122,255)]"
                                />
                              </td>
                            ) : null}
                            {data.columns.map((col) => (
                              <td
                                key={col}
                                className="max-w-[280px] truncate px-3 py-1.5 align-top font-mono"
                                title={cell(row[col])}
                              >
                                {cell(row[col])}
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="flex items-center justify-between gap-2 border-t border-border px-5 py-3 text-xs text-muted-foreground">
                <span>{t("db.pageInfo", { page, pages })}</span>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    disabled={offset === 0}
                  >
                    {t("db.prev")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setOffset(offset + PAGE_SIZE)}
                    disabled={offset + PAGE_SIZE >= data.total}
                  >
                    {t("db.next")}
                  </Button>
                </div>
              </div>
            </>
          )}
        </Card>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-xs text-destructive">
        <Badge variant="secondary" className="shrink-0">
          !
        </Badge>
        {t("db.danger")}
      </div>
    </div>
  );
}
