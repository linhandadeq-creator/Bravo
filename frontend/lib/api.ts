export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "";

export type Project = {
  id: string;
  name: string;
  patient_name: string | null;
  age: number | null;
  sex: string | null;
  cancer_type: string | null;
  stage: string | null;
  diagnosis: string | null;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ProjectFile = {
  id: string;
  project_id: string;
  kind: "TUMOR_VCF" | "NORMAL_VCF" | "HLA" | "EXPRESSION" | string;
  filename: string;
  file_size_bytes: number;
  input_hash: string | null;
  created_at: string;
};

export type ProjectNote = {
  id: string;
  project_id: string;
  content: string;
  created_at: string;
  updated_at: string;
};

export type ProjectReminder = {
  id: string;
  project_id: string;
  title: string;
  due_at: string | null;
  done: boolean;
  created_at: string;
  updated_at: string;
};

export type Sample = {
  id: string;
  project_id: string;
  name: string;
  sample_type: "TUMOR" | "NORMAL" | string;
  reference_build: string | null;
  original_filename: string | null;
  file_size_bytes: number | null;
  source: string;
  created_at: string;
};

export type QcCheck = {
  id: string;
  label: string;
  status: "pass" | "warn" | "fail" | string;
  detail: string;
};

export type SampleQc = {
  role: string;
  file_ok: boolean;
  format_ok: boolean;
  file_size_bytes: number;
  raw_variants: number;
  valid_variants: number;
  invalid_variants: number;
  duplicate_variants: number;
  unique_variants: number;
  malformed_records: number;
  missing_field_records: number;
  chromosome_normalizations: number;
  invalid_by_category: Record<string, number>;
  errors: string[];
  warnings: string[];
};

export type SomaticSummary = {
  TUMOR_ONLY: number;
  NORMAL_ONLY: number;
  SHARED: number;
  UNCERTAIN: number;
};

export type QcSummary = {
  status: string;
  reference_build: string | null;
  tumor_reference_build: string | null;
  normal_reference_build: string | null;
  raw_variants: number;
  valid_variants: number;
  invalid_variants: number;
  duplicate_variants: number;
  unique_variants: number;
  malformed_records: number;
  missing_field_records: number;
  chromosome_normalizations: number;
  tumor: SampleQc | null;
  normal: SampleQc | null;
  checks: QcCheck[];
  errors: string[];
  somatic?: SomaticSummary;
};

export type AnalysisRun = {
  id: string;
  project_id: string;
  tumor_sample_id: string | null;
  normal_sample_id: string | null;
  reference_build: string | null;
  status: "PASS" | "FAILED" | "BLOCKED" | string;
  mode: string;
  error_message: string | null;
  qc_summary: QcSummary | null;
  somatic_summary: SomaticSummary | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
  tumor_sample: Sample | null;
  normal_sample: Sample | null;
};

export type Variant = {
  id: string;
  analysis_run_id: string;
  sample_id: string | null;
  sample_role: "TUMOR" | "NORMAL" | string;
  line_number: number | null;
  chromosome: string | null;
  chromosome_normalized: string | null;
  chromosome_normalized_flag: boolean;
  position: number | null;
  reference: string | null;
  alternate: string | null;
  quality: number | null;
  filter: string | null;
  depth: number | null;
  allele_frequency: number | null;
  genotype: string | null;
  variant_type: string | null;
  record_id: string | null;
  is_valid: boolean;
  is_duplicate: boolean;
  is_malformed: boolean;
  invalid_reason: string | null;
  created_at: string;
};

export type SomaticCandidate = {
  id: string;
  analysis_run_id: string;
  chromosome: string;
  position: number;
  reference: string;
  alternate: string;
  classification: "TUMOR_ONLY" | "NORMAL_ONLY" | "SHARED" | "UNCERTAIN" | string;
  tumor_allele_frequency: number | null;
  normal_allele_frequency: number | null;
  tumor_depth: number | null;
  normal_depth: number | null;
  tumor_genotype: string | null;
  normal_genotype: string | null;
  note: string | null;
  created_at: string;
};

export const REFERENCE_BUILDS = ["GRCh38", "GRCh37"] as const;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export async function fetchProjects(): Promise<Project[]> {
  return request<Project[]>("/api/projects", { cache: "no-store" });
}

export async function fetchProject(id: string): Promise<Project> {
  return request<Project>(`/api/projects/${id}`, { cache: "no-store" });
}

export async function createProject(input: {
  name: string;
  patient_name?: string;
  age?: number | null;
  sex?: string;
  cancer_type?: string;
  stage?: string;
  diagnosis?: string;
  description?: string;
  status?: string;
}): Promise<Project> {
  return request<Project>("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function updateProject(
  id: string,
  input: {
    name?: string;
    patient_name?: string;
    age?: number | null;
    sex?: string;
    cancer_type?: string;
    stage?: string;
    diagnosis?: string;
    description?: string;
    status?: string;
  }
): Promise<Project> {
  return request<Project>(`/api/projects/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function deleteProject(id: string): Promise<void> {
  await request<void>(`/api/projects/${id}`, { method: "DELETE" });
}

export async function fetchProjectFiles(projectId: string): Promise<ProjectFile[]> {
  return request<ProjectFile[]>(`/api/projects/${projectId}/files`, { cache: "no-store" });
}

export async function uploadProjectFile(
  projectId: string,
  input: { file: File; kind: string }
): Promise<ProjectFile> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("kind", input.kind);
  return request<ProjectFile>(`/api/projects/${projectId}/files`, {
    method: "POST",
    body: form,
  });
}

export function projectFileDownloadUrl(projectId: string, fileId: string): string {
  return `${API_URL}/api/projects/${projectId}/files/${fileId}`;
}

export async function fetchProjectFileContent(
  projectId: string,
  fileId: string
): Promise<string> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/files/${fileId}`);
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.text();
}

export async function deleteProjectFile(projectId: string, fileId: string): Promise<void> {
  await request<void>(`/api/projects/${projectId}/files/${fileId}`, { method: "DELETE" });
}

export async function fetchProjectNotes(projectId: string): Promise<ProjectNote[]> {
  return request<ProjectNote[]>(`/api/projects/${projectId}/notes`, { cache: "no-store" });
}

export async function createProjectNote(projectId: string, content: string): Promise<ProjectNote> {
  return request<ProjectNote>(`/api/projects/${projectId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function deleteProjectNote(projectId: string, noteId: string): Promise<void> {
  await request<void>(`/api/projects/${projectId}/notes/${noteId}`, { method: "DELETE" });
}

export async function fetchProjectReminders(projectId: string): Promise<ProjectReminder[]> {
  return request<ProjectReminder[]>(`/api/projects/${projectId}/reminders`, {
    cache: "no-store",
  });
}

export async function createProjectReminder(
  projectId: string,
  input: { title: string; due_at?: string | null }
): Promise<ProjectReminder> {
  return request<ProjectReminder>(`/api/projects/${projectId}/reminders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function updateProjectReminder(
  projectId: string,
  reminderId: string,
  input: { title?: string; due_at?: string | null; done?: boolean }
): Promise<ProjectReminder> {
  return request<ProjectReminder>(`/api/projects/${projectId}/reminders/${reminderId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function deleteProjectReminder(
  projectId: string,
  reminderId: string
): Promise<void> {
  await request<void>(`/api/projects/${projectId}/reminders/${reminderId}`, {
    method: "DELETE",
  });
}

export async function analyzeHla(runId: string): Promise<HlaStatus & { profiles?: HLAProfile[]; action?: string }> {
  return request<HlaStatus & { profiles?: HLAProfile[]; action?: string }>(
    `/api/analysis-runs/${runId}/hla/analyze`,
    { method: "POST" }
  );
}

export async function analyzeExpression(
  runId: string
): Promise<ExpressionStatus & { top_expressed?: ExpressionRecord[]; action?: string }> {
  return request<ExpressionStatus & { top_expressed?: ExpressionRecord[]; action?: string }>(
    `/api/analysis-runs/${runId}/expression/analyze`,
    { method: "POST" }
  );
}

export async function fetchAnalysisRuns(projectId?: string): Promise<AnalysisRun[]> {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request<AnalysisRun[]>(`/api/analysis-runs${query}`, { cache: "no-store" });
}

export async function fetchAnalysisRun(id: string): Promise<AnalysisRun> {
  return request<AnalysisRun>(`/api/analysis-runs/${id}`, { cache: "no-store" });
}

export async function runSyntheticAnalysis(
  projectId: string,
  referenceBuild?: string
): Promise<AnalysisRun> {
  return request<AnalysisRun>("/api/analysis-runs/synthetic", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, reference_build: referenceBuild }),
  });
}

export async function uploadAnalysis(input: {
  projectId: string;
  tumorFile: File;
  normalFile?: File | null;
  referenceBuild?: string;
  tumorReferenceBuild?: string;
  normalReferenceBuild?: string;
  tumorName?: string;
  normalName?: string;
}): Promise<AnalysisRun> {
  const form = new FormData();
  form.append("project_id", input.projectId);
  if (input.referenceBuild) form.append("reference_build", input.referenceBuild);
  if (input.tumorReferenceBuild)
    form.append("tumor_reference_build", input.tumorReferenceBuild);
  if (input.normalReferenceBuild)
    form.append("normal_reference_build", input.normalReferenceBuild);
  if (input.tumorName) form.append("tumor_name", input.tumorName);
  if (input.normalName) form.append("normal_name", input.normalName);
  form.append("tumor_file", input.tumorFile);
  if (input.normalFile) form.append("normal_file", input.normalFile);

  return request<AnalysisRun>("/api/analysis-runs/upload", {
    method: "POST",
    body: form,
  });
}

export async function fetchRunVariants(
  runId: string,
  options: { role?: string; validOnly?: boolean; includeDuplicates?: boolean } = {}
): Promise<Variant[]> {
  const params = new URLSearchParams();
  if (options.role) params.set("role", options.role);
  if (options.validOnly) params.set("valid_only", "true");
  if (options.includeDuplicates === false) params.set("include_duplicates", "false");
  const query = params.toString();
  return request<Variant[]>(
    `/api/analysis-runs/${runId}/variants${query ? `?${query}` : ""}`,
    { cache: "no-store" }
  );
}

export async function fetchSomaticCandidates(
  runId: string,
  classification?: string
): Promise<SomaticCandidate[]> {
  const query = classification
    ? `?classification=${encodeURIComponent(classification)}`
    : "";
  return request<SomaticCandidate[]>(
    `/api/analysis-runs/${runId}/somatic-candidates${query}`,
    { cache: "no-store" }
  );
}

export type Provider = {
  name: string;
  provider: string;
  provider_version: string;
  reference_build: string;
  annotation_version: string;
  transcript_source: string;
  description: string | null;
  available: boolean;
};

export type CompatibilityCheck = {
  id: string;
  label: string;
  status: string;
  detail: string;
};

export type AnnotationRun = {
  id: string;
  analysis_run_id: string;
  provider: string;
  provider_version: string | null;
  reference_build: string | null;
  annotation_version: string | null;
  transcript_source: string | null;
  status: "ANNOTATED" | "PARTIAL" | "FAILED" | "UNAVAILABLE" | string;
  variant_count: number;
  annotated_count: number;
  partial_count: number;
  failed_count: number;
  parameters: Record<string, unknown> | null;
  compatibility: { ok: boolean; checks: CompatibilityCheck[] } | null;
  input_hash: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type Annotation = {
  id: string;
  annotation_run_id: string;
  variant_id: string | null;
  analysis_run_id: string;
  status: string;
  consequence: string | null;
  impact: string | null;
  gene: string | null;
  gene_id: string | null;
  transcript: string | null;
  transcript_id: string | null;
  protein_change: string | null;
  cds_position: number | null;
  protein_position: number | null;
  mutated_peptide?: string | null;
  known_variants?: string[] | null;
  clinical_significance?: string | null;
  hgvs_c?: string | null;
  hgvs_p?: string | null;
  failed_reason: string | null;
  provider: string | null;
  provider_version: string | null;
  reference_build: string | null;
  annotation_version: string | null;
  transcript_source: string | null;
  parameters: Record<string, unknown> | null;
  input_hash: string | null;
  annotation_timestamp: string | null;
  created_at: string;
};

export type AnnotatedVariant = {
  variant_id: string;
  sample_role: string;
  chromosome: string | null;
  position: number | null;
  reference: string | null;
  alternate: string | null;
  variant_type: string | null;
  status: string | null;
  gene: string | null;
  gene_id: string | null;
  transcript: string | null;
  transcript_id: string | null;
  consequence: string | null;
  impact: string | null;
  protein_change: string | null;
  cds_position: number | null;
  protein_position: number | null;
};

export type VariantDetail = {
  variant: Variant;
  tumor_evidence: Variant | null;
  normal_evidence: Variant | null;
  annotation: Annotation | null;
  annotation_run: AnnotationRun | null;
};

export type FilterConfig = {
  project_id: string;
  allowed_consequences: string[];
};

export async function fetchProviders(): Promise<Provider[]> {
  return request<Provider[]>("/api/annotation/providers", { cache: "no-store" });
}

export async function fetchConsequences(): Promise<string[]> {
  return request<string[]>("/api/annotation/consequences", { cache: "no-store" });
}

export async function annotateRun(
  runId: string,
  provider: string,
  parameters?: Record<string, unknown>
): Promise<AnnotationRun> {
  return request<AnnotationRun>(`/api/analysis-runs/${runId}/annotate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, parameters }),
  });
}

export async function fetchAnnotationRun(
  runId: string
): Promise<AnnotationRun | null> {
  return request<AnnotationRun | null>(`/api/analysis-runs/${runId}/annotation`, {
    cache: "no-store",
  });
}

export async function fetchAnnotatedVariants(
  runId: string,
  allowed?: string[]
): Promise<AnnotatedVariant[]> {
  const query = allowed ? `?allowed=${encodeURIComponent(allowed.join(","))}` : "";
  return request<AnnotatedVariant[]>(
    `/api/analysis-runs/${runId}/annotated-variants${query}`,
    { cache: "no-store" }
  );
}

export async function fetchNeoantigenInput(
  runId: string
): Promise<AnnotatedVariant[]> {
  return request<AnnotatedVariant[]>(
    `/api/analysis-runs/${runId}/neoantigen-input`,
    { cache: "no-store" }
  );
}

export async function fetchVariantDetail(
  runId: string,
  variantId: string
): Promise<VariantDetail> {
  return request<VariantDetail>(
    `/api/analysis-runs/${runId}/variants/${variantId}`,
    { cache: "no-store" }
  );
}

export async function fetchFilterConfig(
  projectId: string
): Promise<FilterConfig> {
  return request<FilterConfig>(`/api/projects/${projectId}/annotation-filter`, {
    cache: "no-store",
  });
}

export async function updateFilterConfig(
  projectId: string,
  allowedConsequences: string[]
): Promise<FilterConfig> {
  return request<FilterConfig>(`/api/projects/${projectId}/annotation-filter`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ allowed_consequences: allowedConsequences }),
  });
}

export type HLAProfile = {
  id: string;
  analysis_run_id: string;
  allele: string | null;
  allele_raw: string | null;
  allele_class: string | null;
  locus: string | null;
  source: string | null;
  method: string | null;
  confidence: number | null;
  version: string | null;
  is_valid: boolean;
  is_duplicate: boolean;
  invalid_reason: string | null;
  normalization_method: string | null;
  input_hash: string | null;
  timestamp: string | null;
  created_at: string;
};

export type HlaStatus = {
  status: string;
  total: number;
  valid: number;
  invalid: number;
  duplicate: number;
  class_i: number;
  class_ii: number;
  normalization_method: string;
  normalization_version: string;
  message: string;
};

export type ExpressionRecord = {
  id: string;
  analysis_run_id: string;
  level: string;
  gene_id: string | null;
  gene_symbol: string | null;
  transcript_id: string | null;
  expression_value: number | null;
  unit: string | null;
  source: string | null;
  raw_gene_id: string | null;
  raw_transcript_id: string | null;
  gene_id_changed: boolean;
  transcript_id_changed: boolean;
  gene_id_resolved: boolean;
  is_valid: boolean;
  invalid_reason: string | null;
  normalization_method: string | null;
  input_hash: string | null;
  version: string | null;
  timestamp: string | null;
  created_at: string;
};

export type ExpressionStatus = {
  status: string;
  total: number;
  valid: number;
  invalid: number;
  gene_level: number;
  transcript_level: number;
  normalized_identifiers: number;
  normalization_method: string;
  normalization_version: string;
  message: string;
};

export type IntegrationStatus = {
  analysis_run_id: string;
  status: string;
  hla: HlaStatus;
  expression: ExpressionStatus;
  annotated_genes: string[];
  expressed_genes: string[];
  linked_genes: string[];
  genes_without_expression: string[];
  checks: { id: string; label: string; status: string; detail: string }[];
};

export type SyntheticIntegration = {
  analysis_run_id: string;
  status: string;
  hla_status: string;
  expression_status: string;
  linked_genes: string[];
};

export async function fetchHla(runId: string): Promise<HLAProfile[]> {
  return request<HLAProfile[]>(`/api/analysis-runs/${runId}/hla`, {
    cache: "no-store",
  });
}

export async function fetchHlaStatus(runId: string): Promise<HlaStatus> {
  return request<HlaStatus>(`/api/analysis-runs/${runId}/hla/status`, {
    cache: "no-store",
  });
}

export async function uploadHla(
  runId: string,
  input: {
    file: File;
    fmt?: string;
    source?: string;
    method?: string;
    version?: string;
  }
): Promise<HlaStatus> {
  const form = new FormData();
  form.append("file", input.file);
  if (input.fmt) form.append("fmt", input.fmt);
  if (input.source) form.append("source", input.source);
  if (input.method) form.append("method", input.method);
  if (input.version) form.append("version", input.version);
  return request<HlaStatus>(`/api/analysis-runs/${runId}/hla/upload`, {
    method: "POST",
    body: form,
  });
}

export async function addHlaManual(
  runId: string,
  input: {
    alleles: Record<string, unknown>[];
    source?: string;
    method?: string;
    version?: string;
  }
): Promise<HlaStatus> {
  return request<HlaStatus>(`/api/analysis-runs/${runId}/hla`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function fetchExpression(
  runId: string
): Promise<ExpressionRecord[]> {
  return request<ExpressionRecord[]>(`/api/analysis-runs/${runId}/expression`, {
    cache: "no-store",
  });
}

export async function fetchExpressionStatus(
  runId: string
): Promise<ExpressionStatus> {
  return request<ExpressionStatus>(
    `/api/analysis-runs/${runId}/expression/status`,
    { cache: "no-store" }
  );
}

export async function uploadExpression(
  runId: string,
  input: {
    file: File;
    fmt?: string;
    source?: string;
    version?: string;
    unit?: string;
  }
): Promise<ExpressionStatus> {
  const form = new FormData();
  form.append("file", input.file);
  if (input.fmt) form.append("fmt", input.fmt);
  if (input.source) form.append("source", input.source);
  if (input.version) form.append("version", input.version);
  if (input.unit) form.append("unit", input.unit);
  return request<ExpressionStatus>(
    `/api/analysis-runs/${runId}/expression/upload`,
    { method: "POST", body: form }
  );
}

export async function addExpressionManual(
  runId: string,
  input: {
    records: Record<string, unknown>[];
    source?: string;
    version?: string;
    unit?: string;
  }
): Promise<ExpressionStatus> {
  return request<ExpressionStatus>(`/api/analysis-runs/${runId}/expression`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export type PopulationCoverage = {
  run_id?: string;
  overall_coverage: number;
  loci_covered: string[];
  per_locus: Record<
    string,
    { coverage: number; alleles: { allele: string; frequency: number }[] }
  >;
  note: string;
};

export async function fetchPopulationCoverage(
  runId: string
): Promise<PopulationCoverage> {
  return request<PopulationCoverage>(
    `/api/analysis-runs/${runId}/population-coverage`,
    { cache: "no-store" }
  );
}

export async function fetchIntegrationStatus(
  runId: string
): Promise<IntegrationStatus> {
  return request<IntegrationStatus>(
    `/api/analysis-runs/${runId}/integration-status`,
    { cache: "no-store" }
  );
}

export async function fetchReadiness(
  runId: string
): Promise<IntegrationStatus> {
  return request<IntegrationStatus>(
    `/api/analysis-runs/${runId}/neoantigen-readiness`,
    { cache: "no-store" }
  );
}

export async function runSyntheticIntegration(
  projectId: string
): Promise<SyntheticIntegration> {
  return request<SyntheticIntegration>(
    `/api/projects/${projectId}/synthetic-integration`,
    { method: "POST" }
  );
}

export type PredictionProvider = {
  name: string;
  provider_name: string;
  provider_version: string;
  is_mock: boolean;
  supported_hla: string[];
  status: "MOCK" | "AVAILABLE" | "UNAVAILABLE" | "FAILED" | string;
  description: string;
};

export type PredictionResult = {
  id: string;
  candidate_id: string;
  hla: string | null;
  prediction_value: number | null;
  metric_name: string | null;
  provider: string | null;
  provider_version: string | null;
  status: string | null;
  input_hash: string | null;
  detail: Record<string, unknown> | null;
  timestamp: string | null;
};

export type ExpressionEvidence = {
  matched?: boolean;
  gene_symbol?: string | null;
  expression_value?: number | null;
  unit?: string | null;
  source?: string | null;
  status?: string | null;
};

export type MutationEvidence = {
  classification?: string | null;
  tumor_allele_frequency?: number | null;
  normal_allele_frequency?: number | null;
  tumor_depth?: number | null;
  normal_depth?: number | null;
  quality?: number | null;
  filter?: string | null;
  variant_type?: string | null;
};

export type RankingEvidence = {
  components?: Record<string, number>;
  weights?: Record<string, number>;
  version?: string;
  disclaimer?: string;
};

export type NeoantigenCandidate = {
  id: string;
  analysis_run_id: string;
  variant_id: string | null;
  gene: string | null;
  gene_id: string | null;
  transcript: string | null;
  transcript_id: string | null;
  protein_change: string | null;
  consequence: string | null;
  impact: string | null;
  peptide_representation: string;
  peptide_sequence: string | null;
  hla_allele: string | null;
  hla_class: string | null;
  expression_evidence: ExpressionEvidence | null;
  mutation_evidence: MutationEvidence | null;
  prediction_status: string;
  status: string;
  ranking_score: number | null;
  ranking_evidence: RankingEvidence | null;
  ranking_configuration_id: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type CandidateDetail = {
  candidate: NeoantigenCandidate;
  variant: Variant | null;
  annotation: Annotation | null;
  predictions: PredictionResult[];
  provider: string | null;
  provider_version: string | null;
  provider_is_mock: boolean;
  disclaimer: string;
};

export type RankingConfig = {
  id: string;
  project_id: string;
  name: string;
  weights: Record<string, number>;
  version: string;
  disclaimer: string;
};

export type NeoantigenRunSummary = {
  generated: number;
  rejected: number;
  prediction: {
    provider: string;
    provider_status: string;
    is_mock: boolean;
    predicted: number;
    unavailable: number;
  };
  ranking: {
    ranking_configuration_id: string;
    weights: Record<string, number>;
    version: string;
    ranked: number;
    disclaimer: string;
  };
};

export async function fetchPredictionProviders(): Promise<PredictionProvider[]> {
  return request<PredictionProvider[]>("/api/prediction/providers", {
    cache: "no-store",
  });
}

export async function runNeoantigenEngine(
  runId: string,
  input: { provider?: string; weights?: Record<string, number> }
): Promise<NeoantigenRunSummary> {
  return request<NeoantigenRunSummary>(
    `/api/analysis-runs/${runId}/neoantigen/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
}

export async function fetchNeoantigenCandidates(
  runId: string,
  params: {
    status?: string;
    predictionStatus?: string;
    search?: string;
    minScore?: number;
    sort?: string;
  } = {}
): Promise<NeoantigenCandidate[]> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.predictionStatus) search.set("prediction_status", params.predictionStatus);
  if (params.search) search.set("search", params.search);
  if (params.minScore !== undefined) search.set("min_score", String(params.minScore));
  if (params.sort) search.set("sort", params.sort);
  const query = search.toString();
  return request<NeoantigenCandidate[]>(
    `/api/analysis-runs/${runId}/neoantigen-candidates${query ? `?${query}` : ""}`,
    { cache: "no-store" }
  );
}

export async function fetchCandidateDetail(
  candidateId: string
): Promise<CandidateDetail> {
  return request<CandidateDetail>(`/api/neoantigen-candidates/${candidateId}`, {
    cache: "no-store",
  });
}

export async function fetchRankingConfig(
  projectId: string
): Promise<RankingConfig> {
  return request<RankingConfig>(`/api/projects/${projectId}/ranking-config`, {
    cache: "no-store",
  });
}

export async function updateRankingConfig(
  projectId: string,
  weights: Record<string, number>
): Promise<RankingConfig> {
  return request<RankingConfig>(`/api/projects/${projectId}/ranking-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weights }),
  });
}

export type ConstructCheck = {
  id: string;
  label: string;
  status: string;
  detail: string;
};

export type ConstructItem = {
  position: number;
  label: string;
  candidate_id: string | null;
  spacer: string | null;
  selected_by: string | null;
  selected_at: string | null;
  candidate_version: string | null;
};

export type ConstructQc = {
  status: string;
  candidate_count: number;
  checks: ConstructCheck[];
  traceability: { candidate_id: string; ok: boolean; steps: { step: string; id: string | null; label: string | null; ok: boolean }[] }[];
  errors: string[];
};

export type SimulationConstruct = {
  id: string;
  analysis_run_id: string;
  name: string;
  simulation_format: string;
  status: "DRAFT" | "VALIDATED_SIMULATION" | "INVALID" | "LOCKED" | string;
  candidate_ids: string[] | null;
  ordering: { position: number; label: string; spacer: string | null }[] | null;
  construct_representation: string | null;
  sequence: string | null;
  selected_by: string | null;
  selected_at: string | null;
  candidate_version: string | null;
  qc_summary: ConstructQc | null;
  validation: ConstructQc | null;
  simulation_output: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  items: ConstructItem[];
};

export async function fetchConstructs(
  runId: string
): Promise<SimulationConstruct[]> {
  return request<SimulationConstruct[]>(`/api/analysis-runs/${runId}/constructs`, {
    cache: "no-store",
  });
}

export async function createConstruct(
  runId: string,
  input: { candidate_ids: string[]; selected_by?: string; simulation_format?: string }
): Promise<SimulationConstruct> {
  return request<SimulationConstruct>(`/api/analysis-runs/${runId}/constructs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function updateConstructSelection(
  constructId: string,
  input: { candidate_ids: string[]; selected_by?: string }
): Promise<SimulationConstruct> {
  return request<SimulationConstruct>(`/api/constructs/${constructId}/selection`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function validateConstruct(
  constructId: string
): Promise<SimulationConstruct> {
  return request<SimulationConstruct>(`/api/constructs/${constructId}/validate`, {
    method: "POST",
  });
}

export async function lockConstruct(
  constructId: string
): Promise<SimulationConstruct> {
  return request<SimulationConstruct>(`/api/constructs/${constructId}/lock`, {
    method: "POST",
  });
}

export function constructExportUrl(constructId: string, format: string): string {
  return `${API_URL}/api/constructs/${constructId}/export?format=${format}`;
}

export type PipelineStage = {
  step: string;
  status: string;
  detail: string | null;
};

export type BlueprintSegment = {
  index: number;
  type: "5PRIME" | "3PRIME" | "ANTIGEN" | "SPACER" | string;
  label: string;
  title?: string;
  gene?: string | null;
  protein_change?: string | null;
  hla_allele?: string | null;
  peptide_sequence?: string | null;
};

export type OneClickResult = {
  status: "SUCCESS" | "BLOCKED" | "FAILED" | string;
  message: string;
  project_id: string;
  analysis_run_id: string | null;
  construct_id: string | null;
  report_id: string | null;
  candidate_count: number;
  stages: PipelineStage[];
  blueprint: {
    construct_id: string;
    status: string;
    simulation_format: string;
    construct_representation: string | null;
    sequence: string | null;
    sequence_length: number;
    candidate_count: number;
    segments: BlueprintSegment[];
    sequence_qc?: {
      status: string;
      manufacturability_score: number;
      metrics: Record<string, unknown>;
    } | null;
    production_ready?: boolean;
    disclaimer: string;
  } | null;
  report_formats: string[];
  disclaimer: string;
};

export type OneClickJob = {
  id: string;
  status: "QUEUED" | "RUNNING" | "SUCCESS" | "BLOCKED" | "FAILED" | "CANCELLED";
  stages: PipelineStage[];
  result: OneClickResult | null;
  error: string | null;
  cancel_requested: boolean;
};

export async function createOneClickJob(form: FormData): Promise<OneClickJob> {
  return request<OneClickJob>("/api/one-click/jobs", { method: "POST", body: form });
}

export function createOneClickJobWithProgress(
  form: FormData,
  onProgress: (percent: number) => void
): Promise<OneClickJob> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/one-click/jobs`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as OneClickJob);
        } catch {
          reject(new Error("Malformed response"));
        }
      } else {
        let detail = `Request failed (${xhr.status})`;
        try {
          detail = JSON.parse(xhr.responseText).detail ?? detail;
        } catch {
          /* ignore */
        }
        reject(new Error(detail));
      }
    };
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(form);
  });
}

export async function fetchOneClickJob(id: string): Promise<OneClickJob> {
  return request<OneClickJob>(`/api/one-click/jobs/${id}`, { cache: "no-store" });
}

export async function cancelOneClickJob(id: string): Promise<OneClickJob> {
  return request<OneClickJob>(`/api/one-click/jobs/${id}/cancel`, { method: "POST" });
}

export async function generateOneClick(form: FormData): Promise<OneClickResult> {
  const res = await fetch(`${API_URL}/api/one-click/generate`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = `请求失败（${res.status}）`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
}

export function blueprintUrl(constructId: string, format = "svg"): string {
  return `${API_URL}/api/constructs/${constructId}/blueprint?format=${format}`;
}

export function productionPackageUrl(
  constructId: string,
  format = "json"
): string {
  return `${API_URL}/api/constructs/${constructId}/production-package?format=${format}`;
}

export function worklistUrl(constructId: string): string {
  return `${API_URL}/api/constructs/${constructId}/worklist`;
}

export type ValidationCase = {
  id: string;
  category: string;
  step: string;
  name: string;
  expected_result: unknown;
  actual_result: unknown;
  status: "PASS" | "FAIL" | "WARNING" | string;
  critical: boolean;
  detail: string | null;
  created_at: string;
};

export type AuditLogEntry = {
  id: string;
  step: string;
  timestamp: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  provider: string | null;
  version: string | null;
  parameters: Record<string, unknown> | null;
  status: string;
  error: string | null;
};

export type ValidationReport = {
  id: string;
  dataset_id: string | null;
  software_version: string;
  status: "VALIDATED_SOFTWARE_BUILD" | "NOT_VALIDATED" | string;
  total_tests: number;
  passed: number;
  failed: number;
  warnings: number;
  pipeline_health: { stage: string; status: string; tests: number }[] | null;
  category_summary:
    | Record<string, { total: number; passed: number; failed: number; warnings: number }>
    | null;
  reproducibility: {
    status: string;
    random_seed: number | null;
    deterministic: boolean;
    details: Record<string, boolean>;
  } | null;
  disclaimer: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  cases?: ValidationCase[];
  audit_logs?: AuditLogEntry[];
};

export type ValidationDataset = {
  id: string;
  name: string;
  description: string | null;
  reference_build: string | null;
  created_at: string;
};

export async function runFullValidation(): Promise<ValidationReport> {
  return request<ValidationReport>("/api/validation/run", { method: "POST" });
}

export async function fetchValidationReports(): Promise<ValidationReport[]> {
  return request<ValidationReport[]>("/api/validation/reports", {
    cache: "no-store",
  });
}

export async function fetchValidationReport(
  reportId: string
): Promise<ValidationReport> {
  return request<ValidationReport>(`/api/validation/reports/${reportId}`, {
    cache: "no-store",
  });
}

export async function fetchValidationDatasets(): Promise<ValidationDataset[]> {
  return request<ValidationDataset[]>("/api/validation/datasets", {
    cache: "no-store",
  });
}

export type Report = {
  id: string;
  analysis_run_id: string;
  project_id: string;
  title: string;
  format: "json" | "markdown" | "html" | "csv" | string;
  status: string;
  summary: Record<string, unknown> | null;
  software_version: string;
  generated_by: string | null;
  created_at: string;
  content?: string | null;
};

export async function generateReport(
  runId: string,
  input: { format: string; generated_by?: string }
): Promise<Report> {
  return request<Report>(`/api/analysis-runs/${runId}/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function fetchReports(params: {
  projectId?: string;
  runId?: string;
}): Promise<Report[]> {
  const search = new URLSearchParams();
  if (params.projectId) search.set("project_id", params.projectId);
  if (params.runId) search.set("analysis_run_id", params.runId);
  const query = search.toString();
  return request<Report[]>(`/api/reports${query ? `?${query}` : ""}`, {
    cache: "no-store",
  });
}

export async function fetchReport(reportId: string): Promise<Report> {
  return request<Report>(`/api/reports/${reportId}`, { cache: "no-store" });
}

export function reportDownloadUrl(reportId: string): string {
  return `${API_URL}/api/reports/${reportId}/download`;
}

export function runReportUrl(runId: string, format: string): string {
  return `${API_URL}/api/analysis-runs/${runId}/report?format=${format}`;
}

// ---- Database viewer / maintenance -----------------------------------------

export type DatabaseOverview = {
  engine: string;
  database_file: string | null;
  file_size_bytes: number;
  wal_size_bytes: number;
  journal_mode: string | null;
  table_count: number;
  total_rows: number;
};

export type DatabaseTable = { name: string; rows: number };

export type DatabaseTableRows = {
  name: string;
  columns: string[];
  primary_key: string[];
  total: number;
  limit: number;
  offset: number;
  rows: Record<string, unknown>[];
};

export async function fetchDatabaseOverview(): Promise<DatabaseOverview> {
  return request<DatabaseOverview>("/api/database/overview", { cache: "no-store" });
}

export async function fetchDatabaseTables(): Promise<DatabaseTable[]> {
  return request<DatabaseTable[]>("/api/database/tables", { cache: "no-store" });
}

export async function fetchDatabaseTableRows(
  table: string,
  limit = 50,
  offset = 0
): Promise<DatabaseTableRows> {
  return request<DatabaseTableRows>(
    `/api/database/tables/${encodeURIComponent(table)}?limit=${limit}&offset=${offset}`,
    { cache: "no-store" }
  );
}

export async function deleteDatabaseRows(
  table: string,
  ids: string[]
): Promise<{ table: string; deleted: number }> {
  return request<{ table: string; deleted: number }>(
    `/api/database/tables/${encodeURIComponent(table)}/delete`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    }
  );
}

export async function clearDatabaseTable(
  table: string
): Promise<{ table: string; deleted: number }> {
  return request<{ table: string; deleted: number }>(
    `/api/database/tables/${encodeURIComponent(table)}/clear`,
    { method: "POST" }
  );
}
