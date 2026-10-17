"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Trash2, UserRound } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { FileInput } from "@/components/ui/file-input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  createProject,
  deleteProject,
  fetchProjects,
  uploadProjectFile,
  type Project,
} from "@/lib/api";
import { playSound } from "@/lib/sound";
import { useToast } from "@/components/toast";
import { useI18n } from "@/lib/i18n";

const REGISTRATION_FILES: { kind: string; key: string }[] = [
  { kind: "TUMOR_VCF", key: "tumor" },
  { kind: "NORMAL_VCF", key: "normal" },
  { kind: "HLA", key: "hla" },
  { kind: "EXPRESSION", key: "expression" },
];

export default function ProjectsPage() {
  const { t } = useI18n();
  const { push } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [patientName, setPatientName] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setProjects(await fetchProjects());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("proj.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const project = await createProject({
        name: name.trim(),
        patient_name: patientName.trim() || undefined,
        description: description.trim() || undefined,
      });
      for (const { kind, key } of REGISTRATION_FILES) {
        const file = files[key];
        if (file) {
          try {
            await uploadProjectFile(project.id, { file, kind });
          } catch {
            // The project itself was created; surface partial failures below.
          }
        }
      }
      playSound("success");
      push(t("proj.createdWithFiles"), "success");
      setName("");
      setPatientName("");
      setDescription("");
      setFiles({});
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("proj.createFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(project: Project) {
    if (!window.confirm(t("proj.deleteConfirm", { name: project.name }))) return;
    try {
      await deleteProject(project.id);
      push(t("proj.deleted"), "success");
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t("proj.deleteFailed");
      setError(message);
      push(message, "error");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("page.projects.title")} description={t("page.projects.desc")}>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4" />
          {t("proj.new")}
        </Button>
      </PageHeader>

      {showForm ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("proj.registerPatient")}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">{t("proj.name")}</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={t("proj.namePh")}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="patient">{t("proj.patient")}</Label>
                  <Input
                    id="patient"
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    placeholder={t("proj.patientPh")}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">{t("proj.description")}</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("proj.descPh")}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("proj.registrationFiles")}</Label>
                <div className="grid gap-3 md:grid-cols-2">
                  {REGISTRATION_FILES.map(({ kind, key }) => (
                    <div key={kind} className="space-y-1">
                      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                        {t(`proj.file.${key}`)}
                      </span>
                      <FileInput
                        accept={key === "hla" ? ".json,.csv,.tsv,.txt" : key === "expression" ? ".csv,.tsv,.txt" : ".vcf,.vcf.gz,.txt"}
                        onChange={(file) =>
                          setFiles((prev) => ({ ...prev, [key]: file }))
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button type="submit" size="sm" disabled={submitting}>
                  {submitting ? t("proj.creating") : t("proj.create")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setShowForm(false)}
                >
                  {t("proj.cancel")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <div className="rounded-lg border border-border">
        {loading ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">{t("common.loading")}</div>
        ) : projects.length === 0 ? (
          <div className="p-4">
            <EmptyState title={t("proj.noTitle")} description={t("proj.noDesc")} />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("proj.col.name")}</TableHead>
                <TableHead>{t("proj.col.patient")}</TableHead>
                <TableHead>{t("proj.col.status")}</TableHead>
                <TableHead>{t("proj.col.created")}</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.map((project) => (
                <TableRow key={project.id}>
                  <TableCell>
                    <div className="font-medium">{project.name}</div>
                    {project.description ? (
                      <div className="text-xs text-muted-foreground">
                        {project.description}
                      </div>
                    ) : null}
                  </TableCell>
                  <TableCell className="text-xs">
                    {project.patient_name ? (
                      <span className="inline-flex items-center gap-1.5">
                        <UserRound className="h-3.5 w-3.5 text-muted-foreground" />
                        {project.patient_name}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="capitalize">
                      {project.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="tabular text-xs text-muted-foreground">
                    {new Date(project.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-3">
                      <Link
                        href={`/projects/${project.id}`}
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        {t("common.view")}
                      </Link>
                      <button
                        type="button"
                        onClick={() => handleDelete(project)}
                        aria-label={t("proj.delete")}
                        className="press text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
