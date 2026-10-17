"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Bell,
  CheckCircle2,
  Circle,
  Download,
  FileText,
  FlaskConical,
  NotebookPen,
  Plus,
  Trash2,
  UserRound,
} from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileInput } from "@/components/ui/file-input";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { FILE_KIND_LABELS } from "@/components/project-files-panel";
import {
  blueprintUrl,
  constructExportUrl,
  createProjectNote,
  createProjectReminder,
  deleteProjectFile,
  deleteProjectNote,
  deleteProjectReminder,
  fetchAnalysisRuns,
  fetchConstructs,
  fetchProject,
  fetchProjectFiles,
  fetchProjectNotes,
  fetchProjectReminders,
  fetchReports,
  projectFileDownloadUrl,
  reportDownloadUrl,
  runReportUrl,
  updateProject,
  updateProjectReminder,
  uploadProjectFile,
  type AnalysisRun,
  type Project,
  type ProjectFile,
  type ProjectNote,
  type ProjectReminder,
  type Report,
  type SimulationConstruct,
} from "@/lib/api";
import { useToast } from "@/components/toast";
import { useI18n } from "@/lib/i18n";

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ProjectDetailPage() {
  const { t } = useI18n();
  const { push } = useToast();
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [notes, setNotes] = useState<ProjectNote[]>([]);
  const [reminders, setReminders] = useState<ProjectReminder[]>([]);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [constructs, setConstructs] = useState<SimulationConstruct[]>([]);

  const [patientName, setPatientName] = useState("");
  const [caseInfo, setCaseInfo] = useState({
    age: "",
    sex: "",
    cancer_type: "",
    stage: "",
    diagnosis: "",
  });
  const [newFile, setNewFile] = useState<File | null>(null);
  const [fileKind, setFileKind] = useState("TUMOR_VCF");
  const [noteDraft, setNoteDraft] = useState("");
  const [reminderTitle, setReminderTitle] = useState("");
  const [reminderDue, setReminderDue] = useState("");

  const loadAll = useCallback(async () => {
    if (!params?.id) return;
    const [proj, fileRows, noteRows, reminderRows, runRows, reportRows] =
      await Promise.all([
        fetchProject(params.id),
        fetchProjectFiles(params.id),
        fetchProjectNotes(params.id),
        fetchProjectReminders(params.id),
        fetchAnalysisRuns(params.id),
        fetchReports({ projectId: params.id }),
      ]);
    setProject(proj);
    setPatientName(proj.patient_name ?? "");
    setCaseInfo({
      age: proj.age != null ? String(proj.age) : "",
      sex: proj.sex ?? "",
      cancer_type: proj.cancer_type ?? "",
      stage: proj.stage ?? "",
      diagnosis: proj.diagnosis ?? "",
    });
    setFiles(fileRows);
    setNotes(noteRows);
    setReminders(reminderRows);
    setRuns(runRows);
    setReports(reportRows);
    if (runRows.length) {
      try {
        setConstructs(await fetchConstructs(runRows[0].id));
      } catch {
        setConstructs([]);
      }
    } else {
      setConstructs([]);
    }
  }, [params?.id]);

  useEffect(() => {
    loadAll().catch((err) =>
      setError(err instanceof Error ? err.message : t("pd.notFound"))
    );
  }, [loadAll, t]);

  async function handleSavePatient() {
    if (!project) return;
    setBusy(true);
    try {
      await updateProject(project.id, {
        patient_name: patientName.trim() || undefined,
        age: caseInfo.age.trim() ? Number(caseInfo.age) : undefined,
        sex: caseInfo.sex.trim() || undefined,
        cancer_type: caseInfo.cancer_type.trim() || undefined,
        stage: caseInfo.stage.trim() || undefined,
        diagnosis: caseInfo.diagnosis.trim() || undefined,
      });
      push(t("pd.patientSaved"), "success");
      await loadAll();
    } catch (err) {
      push(err instanceof Error ? err.message : t("pd.saveFailed"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleUploadFile(event: React.FormEvent) {
    event.preventDefault();
    if (!project || !newFile) return;
    setBusy(true);
    try {
      await uploadProjectFile(project.id, { file: newFile, kind: fileKind });
      setNewFile(null);
      push(t("pd.fileAdded"), "success");
      await loadAll();
    } catch (err) {
      push(err instanceof Error ? err.message : t("pd.saveFailed"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteFile(file: ProjectFile) {
    if (!project || !window.confirm(t("pd.fileDeleteConfirm", { name: file.filename }))) return;
    try {
      await deleteProjectFile(project.id, file.id);
      push(t("pd.fileDeleted"), "success");
      await loadAll();
    } catch (err) {
      push(err instanceof Error ? err.message : t("pd.saveFailed"), "error");
    }
  }

  async function handleAddNote() {
    if (!project || !noteDraft.trim()) return;
    try {
      await createProjectNote(project.id, noteDraft.trim());
      setNoteDraft("");
      push(t("pd.noteAdded"), "success");
      await loadAll();
    } catch (err) {
      push(err instanceof Error ? err.message : t("pd.saveFailed"), "error");
    }
  }

  async function handleDeleteNote(note: ProjectNote) {
    if (!project) return;
    try {
      await deleteProjectNote(project.id, note.id);
      await loadAll();
    } catch (err) {
      push(err instanceof Error ? err.message : t("pd.saveFailed"), "error");
    }
  }

  async function handleAddReminder() {
    if (!project || !reminderTitle.trim()) return;
    try {
      await createProjectReminder(project.id, {
        title: reminderTitle.trim(),
        due_at: reminderDue ? new Date(reminderDue).toISOString() : null,
      });
      setReminderTitle("");
      setReminderDue("");
      push(t("pd.reminderAdded"), "success");
      await loadAll();
    } catch (err) {
      push(err instanceof Error ? err.message : t("pd.saveFailed"), "error");
    }
  }

  async function handleToggleReminder(reminder: ProjectReminder) {
    if (!project) return;
    try {
      await updateProjectReminder(project.id, reminder.id, { done: !reminder.done });
      await loadAll();
    } catch (err) {
      push(err instanceof Error ? err.message : t("pd.saveFailed"), "error");
    }
  }

  async function handleDeleteReminder(reminder: ProjectReminder) {
    if (!project) return;
    try {
      await deleteProjectReminder(project.id, reminder.id);
      await loadAll();
    } catch (err) {
      push(err instanceof Error ? err.message : t("pd.saveFailed"), "error");
    }
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!project) {
    return <div className="text-sm text-muted-foreground">{t("common.loading")}</div>;
  }

  const openReminders = reminders.filter((r) => !r.done).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title={project.name}
        description={project.description ?? undefined}
      >
        <Button asChild size="sm" variant="outline">
          <Link href="/projects">
            <ArrowLeft className="h-4 w-4" />
            {t("nav.projects")}
          </Link>
        </Button>
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {/* patient + registration files */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserRound className="h-4 w-4 text-muted-foreground" />
                {t("pd.patientInfo")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="patient">{t("proj.patient")}</Label>
                  <Input
                    id="patient"
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    placeholder={t("proj.patientPh")}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="age">{t("pd.age")}</Label>
                    <Input
                      id="age"
                      type="number"
                      min={0}
                      max={150}
                      value={caseInfo.age}
                      onChange={(e) => setCaseInfo({ ...caseInfo, age: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="sex">{t("pd.sex")}</Label>
                    <Input
                      id="sex"
                      value={caseInfo.sex}
                      onChange={(e) => setCaseInfo({ ...caseInfo, sex: e.target.value })}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cancer">{t("pd.cancerType")}</Label>
                  <Input
                    id="cancer"
                    value={caseInfo.cancer_type}
                    onChange={(e) => setCaseInfo({ ...caseInfo, cancer_type: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="stage">{t("pd.stage")}</Label>
                  <Input
                    id="stage"
                    value={caseInfo.stage}
                    onChange={(e) => setCaseInfo({ ...caseInfo, stage: e.target.value })}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="diagnosis">{t("pd.diagnosis")}</Label>
                  <Textarea
                    id="diagnosis"
                    rows={2}
                    value={caseInfo.diagnosis}
                    onChange={(e) => setCaseInfo({ ...caseInfo, diagnosis: e.target.value })}
                  />
                </div>
                <div className="flex items-end">
                  <Button size="sm" disabled={busy} onClick={handleSavePatient}>
                    {t("pd.savePatient")}
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                <Label>{t("pd.registrationFiles")}</Label>
                <form onSubmit={handleUploadFile} className="space-y-3">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-1.5">
                      <Select value={fileKind} onChange={(e) => setFileKind(e.target.value)}>
                        <option value="TUMOR_VCF">{t("pf.kindTumorVcf")}</option>
                        <option value="NORMAL_VCF">{t("pf.kindNormalVcf")}</option>
                        <option value="HLA">{t("pf.kindHla")}</option>
                        <option value="EXPRESSION">{t("pf.kindExpression")}</option>
                      </Select>
                    </div>
                    <div>
                      <FileInput
                        accept=".vcf,.vcf.gz,.csv,.tsv,.json,.txt"
                        onChange={setNewFile}
                      />
                    </div>
                  </div>
                  <Button type="submit" size="sm" disabled={busy || !newFile}>
                    <Plus className="h-4 w-4" />
                    {t("pd.addFile")}
                  </Button>
                </form>
              </div>

              <ul className="divide-y divide-border rounded-lg border border-border">
                {files.length === 0 ? (
                  <li className="px-4 py-6 text-center text-xs text-muted-foreground">
                    {t("pd.noFiles")}
                  </li>
                ) : (
                  files.map((file) => (
                    <li
                      key={file.id}
                      className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5"
                    >
                      <div className="flex min-w-0 items-center gap-2.5">
                        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <div className="min-w-0">
                          <div className="truncate text-[13px] font-medium">{file.filename}</div>
                          <div className="text-[11px] text-muted-foreground">
                            {t(FILE_KIND_LABELS[file.kind] ?? "pf.kindOther")} ·{" "}
                            {humanSize(file.file_size_bytes)}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <a
                          href={projectFileDownloadUrl(project.id, file.id)}
                          className="press text-muted-foreground hover:text-foreground"
                          aria-label={t("pd.downloadFile")}
                        >
                          <Download className="h-4 w-4" />
                        </a>
                        <button
                          type="button"
                          onClick={() => handleDeleteFile(file)}
                          aria-label={t("proj.delete")}
                          className="press text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </li>
                  ))
                )}
              </ul>
            </CardContent>
          </Card>

          {/* notes */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <NotebookPen className="h-4 w-4 text-muted-foreground" />
                {t("pd.notes")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Textarea
                  value={noteDraft}
                  onChange={(e) => setNoteDraft(e.target.value)}
                  placeholder={t("pd.notePh")}
                  rows={3}
                />
                <Button size="sm" onClick={handleAddNote} disabled={!noteDraft.trim()}>
                  <Plus className="h-4 w-4" />
                  {t("pd.addNote")}
                </Button>
              </div>
              <ul className="space-y-2">
                {notes.map((note) => (
                  <li
                    key={note.id}
                    className="flex items-start justify-between gap-3 rounded-lg border border-border px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="whitespace-pre-wrap text-[13px]">{note.content}</div>
                      <div className="mt-1 text-[11px] text-muted-foreground">
                        {new Date(note.created_at).toLocaleString()}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteNote(note)}
                      aria-label={t("proj.delete")}
                      className="press shrink-0 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* reminders */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-4 w-4 text-muted-foreground" />
                {t("pd.reminders")}
                {openReminders > 0 ? (
                  <Badge variant="secondary" className="tabular">
                    {openReminders}
                  </Badge>
                ) : null}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Input
                  value={reminderTitle}
                  onChange={(e) => setReminderTitle(e.target.value)}
                  placeholder={t("pd.reminderPh")}
                />
                <Input
                  type="datetime-local"
                  value={reminderDue}
                  onChange={(e) => setReminderDue(e.target.value)}
                  className="tabular text-xs"
                />
                <Button size="sm" onClick={handleAddReminder} disabled={!reminderTitle.trim()}>
                  <Plus className="h-4 w-4" />
                  {t("pd.addReminder")}
                </Button>
              </div>
              <ul className="space-y-2">
                {reminders.map((reminder) => (
                  <li
                    key={reminder.id}
                    className="flex items-start justify-between gap-2 rounded-lg border border-border px-3 py-2.5"
                  >
                    <button
                      type="button"
                      onClick={() => handleToggleReminder(reminder)}
                      className="flex min-w-0 flex-1 items-start gap-2 text-left"
                    >
                      {reminder.done ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                      ) : (
                        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      )}
                      <span className="min-w-0">
                        <span
                          className={
                            "block text-[13px] " +
                            (reminder.done ? "text-muted-foreground line-through" : "")
                          }
                        >
                          {reminder.title}
                        </span>
                        {reminder.due_at ? (
                          <span className="block text-[11px] tabular text-muted-foreground">
                            {new Date(reminder.due_at).toLocaleString()}
                          </span>
                        ) : null}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteReminder(reminder)}
                      aria-label={t("proj.delete")}
                      className="press shrink-0 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-border bg-border">
            <div className="bg-background p-4">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("pd.id")}
              </dt>
              <dd className="mt-1 break-all font-mono text-xs">{project.id}</dd>
            </div>
            <div className="bg-background p-4">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("pd.status")}
              </dt>
              <dd className="mt-1">
                <Badge variant="secondary" className="capitalize">
                  {project.status}
                </Badge>
              </dd>
            </div>
            <div className="bg-background p-4">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("pd.files")}
              </dt>
              <dd className="mt-1 text-sm tabular">{files.length}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* generation records & files */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-muted-foreground" />
            {t("pd.generations")}
            <Badge variant="secondary" className="tabular">
              {runs.length}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {runs.length === 0 ? (
            <p className="text-xs text-muted-foreground">{t("pd.noGenerations")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="px-3 py-2 font-medium">{t("pd.col.time")}</th>
                    <th className="px-3 py-2 font-medium">{t("pd.col.mode")}</th>
                    <th className="px-3 py-2 font-medium">{t("pd.col.status")}</th>
                    <th className="px-3 py-2 font-medium">{t("pd.col.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.slice(0, 10).map((run) => (
                    <tr key={run.id} className="border-t border-border/60">
                      <td className="px-3 py-2 tabular">
                        {new Date(run.created_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">{run.mode}</td>
                      <td className="px-3 py-2">
                        <Badge variant="secondary">{run.status}</Badge>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-2">
                          <Link
                            href={`/variants/${run.id}`}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            {t("pd.openVariants")}
                          </Link>
                          <a
                            href={runReportUrl(run.id, "pdf")}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            PDF
                          </a>
                          <a
                            href={runReportUrl(run.id, "html")}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            HTML
                          </a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {reports.length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("pd.savedReports")}
              </h3>
              <ul className="space-y-1.5">
                {reports.slice(0, 10).map((report) => (
                  <li
                    key={report.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2"
                  >
                    <span className="min-w-0 truncate text-[13px]">
                      <span className="font-medium">{report.title}</span>{" "}
                      <span className="text-muted-foreground">
                        · {report.format} · {new Date(report.created_at).toLocaleString()}
                      </span>
                    </span>
                    <a
                      href={reportDownloadUrl(report.id)}
                      className="press inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                    >
                      <Download className="h-3.5 w-3.5" />
                      {t("pd.download")}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {constructs.length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("pd.constructFiles")}
              </h3>
              <ul className="space-y-1.5">
                {constructs.slice(0, 5).map((construct) => (
                  <li
                    key={construct.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-xs"
                  >
                    <span className="font-mono">
                      {construct.id.slice(0, 8)} · {construct.simulation_format} ·{" "}
                      {construct.status}
                    </span>
                    <span className="flex flex-wrap gap-2">
                      <a href={blueprintUrl(construct.id, "svg")} className="hover:text-foreground">
                        SVG
                      </a>
                      <a href={blueprintUrl(construct.id, "pdf")} className="hover:text-foreground">
                        PDF
                      </a>
                      <a
                        href={constructExportUrl(construct.id, "report")}
                        className="hover:text-foreground"
                      >
                        {t("pd.report")}
                      </a>
                      <a
                        href={constructExportUrl(construct.id, "json")}
                        className="hover:text-foreground"
                      >
                        JSON
                      </a>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
