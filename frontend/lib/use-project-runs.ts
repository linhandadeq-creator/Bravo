"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchAnalysisRuns,
  fetchProjectFiles,
  fetchProjects,
  type AnalysisRun,
  type Project,
  type ProjectFile,
} from "@/lib/api";

export function useProjectRuns() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [runId, setRunId] = useState("");
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);

  const loadRuns = useCallback(async (pid: string, selectFirst = true) => {
    if (!pid) {
      setRuns([]);
      setRunId("");
      return;
    }
    const data = await fetchAnalysisRuns(pid);
    setRuns(data);
    setRunId((current) => {
      if (current && data.some((run) => run.id === current)) return current;
      return selectFirst ? data[0]?.id ?? "" : current;
    });
  }, []);

  const loadProjectFiles = useCallback(async (pid: string) => {
    if (!pid) {
      setProjectFiles([]);
      return;
    }
    try {
      setProjectFiles(await fetchProjectFiles(pid));
    } catch {
      setProjectFiles([]);
    }
  }, []);

  useEffect(() => {
    fetchProjects()
      .then((data) => {
        setProjects(data);
        if (data.length) setProjectId(data[0].id);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    void loadRuns(projectId);
    void loadProjectFiles(projectId);
  }, [projectId, loadRuns, loadProjectFiles]);

  return {
    projects,
    projectId,
    setProjectId,
    runs,
    runId,
    setRunId,
    projectFiles,
    loadProjectFiles,
    loadRuns,
    loading,
  };
}
