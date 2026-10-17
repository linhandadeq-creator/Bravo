"use client";

import { useEffect, useState } from "react";
import { ArrowRight, FlaskConical } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { fetchProjects, type Project } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function DashboardPage() {
  const { t } = useI18n();
  const [projects, setProjects] = useState<Project[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    fetchProjects()
      .then((data) => {
        setProjects(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  const projectCount = status === "loading" ? "—" : projects.length;

  return (
    <div className="space-y-8">
      <PageHeader
        title={t("page.dashboard.title")}
        description={t("page.dashboard.desc")}
      >
        <Button asChild size="sm" variant="outline">
          <Link href="/projects">
            {t("dash.manage")}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </PageHeader>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label={t("dash.stat.projects")} value={projectCount} />
        <StatCard label={t("dash.stat.analyses")} value={0} />
        <StatCard label={t("dash.stat.variants")} value={0} />
        <StatCard label={t("dash.stat.candidates")} value={0} />
      </section>

      <section className="rounded-lg border border-border">
        <div className="flex items-center justify-between border-b border-border/70 px-5 py-3.5">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold">{t("dash.recent")}</h2>
          </div>
          <Link
            href="/projects"
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {t("dash.viewAll")}
          </Link>
        </div>

        {status === "error" ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            {t("dash.apiError")}
          </div>
        ) : projects.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            {status === "loading" ? t("common.loading") : t("dash.noProjects")}
          </div>
        ) : (
          <ul className="divide-y divide-border/70">
            {projects.slice(0, 5).map((project) => (
              <li key={project.id}>
                <Link
                  href={`/projects/${project.id}`}
                  className="flex items-center justify-between px-5 py-3.5 transition-colors hover:bg-white/50"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">
                      {project.name}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {project.description ?? t("dash.noDescription")}
                    </div>
                  </div>
                  <span className="text-xs capitalize text-muted-foreground">
                    {project.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
