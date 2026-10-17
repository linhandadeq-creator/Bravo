import type { Lang } from "@/lib/i18n";

export type { Lang };

type Pair = { zh: string; en: string };

export const CHECK_LABELS: Record<string, Pair> = {
  file_integrity: { zh: "文件完整性", en: "File integrity" },
  vcf_format: { zh: "VCF 格式", en: "VCF format" },
  malformed_records: { zh: "畸形记录", en: "Malformed records" },
  missing_required_fields: { zh: "缺失必填字段", en: "Missing required fields" },
  chromosome: { zh: "染色体", en: "Chromosome" },
  position: { zh: "位置", en: "Position" },
  ref_alt: { zh: "REF / ALT", en: "REF / ALT" },
  duplicates: { zh: "重复变异", en: "Duplicate variants" },
  reference_build: { zh: "参考基因组版本", en: "Reference build" },
  normal_present: { zh: "正常样本", en: "Normal sample" },
  vcf_build: { zh: "VCF 参考版本", en: "VCF reference build" },
  annotation_version: { zh: "注释版本", en: "Annotation version" },
  transcript_source: { zh: "转录本数据库", en: "Transcript database" },
  hla: { zh: "HLA", en: "HLA" },
  expression: { zh: "表达谱", en: "Expression" },
  candidate_exists: { zh: "候选存在", en: "Candidate exists" },
  duplicate_candidates: { zh: "无重复候选", en: "No duplicates" },
  same_analysis_run: { zh: "归属当前分析", en: "Same analysis run" },
  hla_information: { zh: "HLA 信息", en: "HLA information" },
  prediction_status: { zh: "预测状态", en: "Prediction status" },
  ranking_status: { zh: "排序状态", en: "Ranking status" },
  missing_data: { zh: "缺失数据", en: "Missing data" },
  provenance: { zh: "完整溯源", en: "Complete provenance" },
  construct_ordering: { zh: "构建顺序", en: "Construct ordering" },
  candidate_selection: { zh: "候选选择", en: "Candidate selection" },
};

export const CATEGORY_LABELS: Record<string, Pair> = {
  INPUT_VALIDATION: { zh: "输入验证", en: "Input validation" },
  BIOLOGICAL_DATA_INTEGRATION: { zh: "生物学数据整合", en: "Biological data integration" },
  PIPELINE_VALIDATION: { zh: "流程验证", en: "Pipeline validation" },
  PROVENANCE_VALIDATION: { zh: "溯源验证", en: "Provenance validation" },
  REPRODUCIBILITY: { zh: "可复现性", en: "Reproducibility" },
  CONSTRUCT_VALIDATION: { zh: "构建验证", en: "Construct validation" },
};

export const STAGE_LABELS: Record<string, Pair> = {
  VCF_QC: { zh: "VCF 质控", en: "VCF QC" },
  SOMATIC: { zh: "肿瘤/正常", en: "Tumour/normal" },
  ANNOTATION: { zh: "注释", en: "Annotation" },
  HLA: { zh: "HLA", en: "HLA" },
  EXPRESSION: { zh: "表达谱", en: "Expression" },
  CANDIDATE: { zh: "候选生成", en: "Candidate generation" },
  PREDICTION: { zh: "预测", en: "Prediction" },
  RANKING: { zh: "排序", en: "Ranking" },
  CONSTRUCT: { zh: "构建模拟", en: "Construct" },
};

export const CASE_NAME_LABELS: Record<string, Pair> = {
  "Malformed VCF record detected": { zh: "检测到畸形 VCF 记录", en: "Malformed VCF record detected" },
  "Missing required field detected": { zh: "检测到缺失必填字段", en: "Missing required field detected" },
  "Invalid allele detected": { zh: "检测到无效等位基因", en: "Invalid allele detected" },
  "Reference build mismatch rejected": { zh: "拒绝参考基因组版本不一致", en: "Reference build mismatch rejected" },
  "QC status": { zh: "质控状态", en: "QC status" },
  "Raw variant counts": { zh: "原始变异计数", en: "Raw variant counts" },
  "No invalid variants": { zh: "无无效变异", en: "No invalid variants" },
  "Tumor/normal classification": { zh: "肿瘤/正常分类", en: "Tumour/normal classification" },
  "Annotation mapping": { zh: "注释映射", en: "Annotation mapping" },
  "Annotation reproducible": { zh: "注释可复现", en: "Annotation reproducible" },
  "HLA normalization": { zh: "HLA 标准化", en: "HLA normalization" },
  "Expression mapping": { zh: "表达谱映射", en: "Expression mapping" },
  "Annotated genes have expression": { zh: "注释基因存在表达", en: "Annotated genes have expression" },
  "Candidate generation": { zh: "候选生成", en: "Candidate generation" },
  "Expected protein changes": { zh: "预期蛋白改变", en: "Expected protein changes" },
  "Prediction provider status": { zh: "预测提供方状态", en: "Prediction provider status" },
  "Ranking status": { zh: "排序状态", en: "Ranking status" },
  "Ranking behavior": { zh: "排序行为", en: "Ranking behavior" },
  "Construct representation": { zh: "构建表示", en: "Construct representation" },
  "Construct status": { zh: "构建状态", en: "Construct status" },
  "Construct ordering": { zh: "构建顺序", en: "Construct ordering" },
  "Construct traceability": { zh: "构建可追溯性", en: "Construct traceability" },
  "Production sections generated": { zh: "生成生产章节", en: "Production sections generated" },
  "Candidate identities reproducible": { zh: "候选身份可复现", en: "Candidate identities reproducible" },
  "Prediction results reproducible": { zh: "预测结果可复现", en: "Prediction results reproducible" },
  "Ranking reproducible": { zh: "排序可复现", en: "Ranking reproducible" },
  "Construct reproducible": { zh: "构建可复现", en: "Construct reproducible" },
  "Annotation provenance present": { zh: "注释溯源完整", en: "Annotation provenance present" },
  "Prediction provenance present": { zh: "预测溯源完整", en: "Prediction provenance present" },
  "Ranking configuration recorded": { zh: "已记录排序配置", en: "Ranking configuration recorded" },
  "Run provenance present": { zh: "分析运行溯源完整", en: "Run provenance present" },
};

export const CONSEQUENCE_LABELS: Record<string, Pair> = {
  missense: { zh: "错义", en: "Missense" },
  frameshift: { zh: "移码", en: "Frameshift" },
  stop_gained: { zh: "获得终止", en: "Stop gained" },
  stop_lost: { zh: "丢失终止", en: "Stop lost" },
  start_lost: { zh: "丢失起始", en: "Start lost" },
  splice_related: { zh: "剪接相关", en: "Splice related" },
  inframe_insertion: { zh: "框内插入", en: "Inframe insertion" },
  inframe_deletion: { zh: "框内缺失", en: "Inframe deletion" },
  synonymous: { zh: "同义", en: "Synonymous" },
  unknown: { zh: "未知", en: "Unknown" },
};

export const IMPACT_LABELS: Record<string, Pair> = {
  HIGH: { zh: "高", en: "High" },
  MODERATE: { zh: "中", en: "Moderate" },
  LOW: { zh: "低", en: "Low" },
  MODIFIER: { zh: "修饰", en: "Modifier" },
};

export const PROVIDER_LABELS: Record<string, Pair> = {
  mock: { zh: "模拟提供方", en: "Mock provider" },
  mhcflurry: { zh: "MHCflurry 2.3 — I 类呈递", en: "MHCflurry 2.3 — Class I Presentation" },
  mhcnuggets: { zh: "MHCnuggets 2.4 — II 类结合", en: "MHCnuggets 2.4 — Class II Binding" },
  panel: { zh: "联合面板 — I 类 + II 类", en: "Panel — Class I + Class II" },
  consensus: { zh: "多预测器共识", en: "Multi-predictor consensus" },
  netmhcpan: { zh: "NetMHCpan — I 类（需授权）", en: "NetMHCpan — Class I (licensed)" },
  netmhciipan: { zh: "NetMHCIIpan — II 类（需授权）", en: "NetMHCIIpan — Class II (licensed)" },
  vep: { zh: "Ensembl VEP（REST，真实注释）", en: "Ensembl VEP (REST, real annotation)" },
  snpeff: { zh: "SnpEff（预留）", en: "SnpEff (reserved)" },
  annovar: { zh: "ANNOVAR（预留）", en: "ANNOVAR (reserved)" },
  external: { zh: "真实提供方适配器", en: "Real provider adapter" },
};

export const MODE_LABELS: Record<string, Pair> = {
  UPLOAD: { zh: "上传", en: "Upload" },
  SYNTHETIC: { zh: "合成", en: "Synthetic" },
};

export function label(
  groups: Record<string, Pair>,
  key: string | null | undefined,
  lang: Lang = "en"
): string {
  if (!key) return "—";
  const entry = groups[key];
  // Pairs only define zh/en; other languages fall back to English.
  if (entry) return entry[lang === "zh" ? "zh" : "en"];
  return key.replace(/_/g, " ");
}
