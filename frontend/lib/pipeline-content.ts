import type { Lang } from "@/lib/i18n";

export type Loc = { en: string } & Partial<Record<Lang, string>>;

export function pick(entry: Loc, lang: Lang): string {
  return entry[lang] ?? entry.en;
}

export type PipelineStep = {
  id: string;
  aliases?: string[];
  label: Loc;
  desc: Loc;
};

// Canonical one-click pipeline, in order.
export const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: "VCF_QC",
    label: {
      en: "QC",
      zh: "质控",
      ru: "QC",
      fr: "CQ",
      de: "QC",
    },
    desc: {
      en: "Parse the tumour/normal VCF, validate records, de-duplicate, normalize chromosomes and classify tumour-only vs germline (shared) variants.",
      zh: "解析肿瘤/正常 VCF，校验记录、去重、规范化染色体，并区分肿瘤特有与生殖系（共有）变异。",
      ru: "Разбор VCF опухоли/нормы, проверка записей, дедупликация, нормализация хромосом и классификация вариантов (только опухоль против зародышевых).",
      fr: "Analyse des VCF tumeur/normal, validation, déduplication, normalisation des chromosomes et classification tumeur seule vs germinal (partagé).",
      de: "Parsen der Tumor-/Normal-VCF, Validierung, Deduplizierung, Chromosomen-Normalisierung und Klassifikation Tumor vs. Keimbahn (geteilt).",
    },
  },
  {
    id: "ANNOTATION",
    aliases: ["ANN"],
    label: {
      en: "Annotation",
      zh: "注释",
      ru: "Аннотация",
      fr: "Annotation",
      de: "Annotation",
    },
    desc: {
      en: "Gene / transcript / consequence / HGVS via the selected provider (fully-offline Ensembl or Ensembl VEP). Builds the real mutant peptide used downstream.",
      zh: "通过所选提供方（完全离线 Ensembl 或 Ensembl VEP）得到基因/转录本/后果/HGVS，并构建下游使用的真实突变肽。",
      ru: "Ген / транскрипт / последствие / HGVS через выбранный провайдер (полностью офлайн Ensembl или Ensembl VEP). Строит реальный мутантный пептид.",
      fr: "Gène / transcrit / conséquence / HGVS via le fournisseur choisi (Ensembl hors-ligne ou Ensembl VEP). Construit le peptide mutant réel.",
      de: "Gen / Transkript / Konsequenz / HGVS über den gewählten Anbieter (voll offline Ensembl oder Ensembl VEP). Erzeugt das echte mutierte Peptid.",
    },
  },
  {
    id: "HLA",
    aliases: ["HLA_EXPRESSION"],
    label: {
      en: "HLA typing",
      zh: "HLA 分型",
      ru: "HLA-типирование",
      fr: "Typage HLA",
      de: "HLA-Typisierung",
    },
    desc: {
      en: "Class I / II alleles are normalized and validated; they determine which epitopes are predicted.",
      zh: "对 I/II 类等位基因进行标准化与校验，决定预测哪些表位。",
      ru: "Аллели I/II класса нормализуются и проверяются; они определяют, какие эпитопы предсказываются.",
      fr: "Les allèles classe I/II sont normalisés et validés ; ils déterminent les épitopes prédits.",
      de: "Klasse-I/II-Allele werden normalisiert und validiert; sie bestimmen die vorhergesagten Epitope.",
    },
  },
  {
    id: "EXPRESSION",
    aliases: ["HLA_EXPRESSION"],
    label: {
      en: "Expression",
      zh: "表达谱",
      ru: "Экспрессия",
      fr: "Expression",
      de: "Expression",
    },
    desc: {
      en: "Gene/transcript-level TPM matched to candidate genes. Missing expression blocks the pipeline — it is never fabricated.",
      zh: "基因/转录本层级 TPM 与候选基因匹配。缺失表达谱会阻断流程——绝不伪造。",
      ru: "TPM на уровне гена/транскрипта сопоставляется с генами-кандидатами. Отсутствие экспрессии блокирует конвейер — она не выдумывается.",
      fr: "TPM au niveau gène/transcrit associés aux gènes candidats. Une expression manquante bloque le pipeline — elle n'est jamais inventée.",
      de: "TPM auf Gen-/Transkriptebene, gemappt auf Kandidatengene. Fehlende Expression blockiert die Pipeline — sie wird nie erfunden.",
    },
  },
  {
    id: "NEOANTIGEN",
    aliases: ["NEO", "ENGINE"],
    label: {
      en: "Neoantigen engine",
      zh: "新抗原引擎",
      ru: "Движок неоантигенов",
      fr: "Moteur néoantigène",
      de: "Neoantigen-Engine",
    },
    desc: {
      en: "8–11mer epitope enumeration, MHC binding/presentation (Class I MHCflurry, Class II MHCnuggets), exact self-proteome filter, MS-evidence weighting and research ranking.",
      zh: "枚举 8–11mer 表位，MHC 结合/呈递预测（I 类 MHCflurry、II 类 MHCnuggets），自身蛋白组精确过滤，MS 证据加权与研究评分排序。",
      ru: "Перечисление эпитопов 8–11 aa, связывание/презентация MHC (класс I — MHCflurry, класс II — MHCnuggets), точный фильтр по протеому, учёт MS-данных и исследовательское ранжирование.",
      fr: "Énumération des épitopes 8–11 aa, liaison/présentation CMH (classe I MHCflurry, classe II MHCnuggets), filtre exact du protéome du soi, pondération MS et classement de recherche.",
      de: "8–11-mer-Epitop-Enumeration, MHC-Bindung/Präsentation (Klasse I MHCflurry, Klasse II MHCnuggets), exakter Selbst-Proteom-Filter, MS-Evidenz-Gewichtung und Forschungs-Ranking.",
    },
  },
  {
    id: "CONSTRUCT",
    label: {
      en: "Construct design",
      zh: "构建设计",
      ru: "Дизайн конструкции",
      fr: "Conception de construction",
      de: "Konstrukt-Design",
    },
    desc: {
      en: "Constraint hill-climb sequence design (human-preference codons) with 12 sequence-level QC checks, plus an in-silico production package (IVT/T7, primer, LNP, chemistry, release criteria). Research simulation.",
      zh: "约束式爬山序列设计（人偏好密码子）+ 12 项序列级 QC，并生成体外生产图纸包（IVT/T7、引物、LNP、化学、放行标准）。科研模拟。",
      ru: "Ограниченный hill-climb дизайн последовательности (человеческие кодоны) + 12 проверок QC и производственный пакет in-silico (IVT/T7, праймеры, LNP, химия, критерии выпуска). Симуляция.",
      fr: "Conception de séquence par hill-climbing sous contraintes (codons humains) + 12 contrôles CQ et un dossier de production in-silico (IVT/T7, amorces, LNP, chimie, critères de libération). Simulation.",
      de: "Constraint-Hill-Climb-Sequenzdesign (humane Codons) + 12 Sequenz-QC-Prüfungen und ein In-silico-Produktionspaket (IVT/T7, Primer, LNP, Chemie, Freigabekriterien). Simulation.",
    },
  },
  {
    id: "REPORT",
    label: {
      en: "Report",
      zh: "报告",
      ru: "Отчёт",
      fr: "Rapport",
      de: "Bericht",
    },
    desc: {
      en: "Aggregated research report (HTML / PDF / CSV) with full provenance and a methods-and-versions manifest.",
      zh: "汇总科研报告（HTML / PDF / CSV），含完整溯源与方法学/版本清单。",
      ru: "Сводный исследовательский отчёт (HTML / PDF / CSV) с полным происхождением и списком методов и версий.",
      fr: "Rapport de recherche agrégé (HTML / PDF / CSV) avec traçabilité complète et manifeste des méthodes et versions.",
      de: "Aggregierter Forschungsbericht (HTML / PDF / CSV) mit vollständiger Herkunft und Methoden-/Versionsmanifest.",
    },
  },
];

export const PIPELINE_TEXT: Record<string, Loc> = {
  sectionTitle: {
    en: "Visual pipeline",
    zh: "可视化流程",
    ru: "Визуальный конвейер",
    fr: "Pipeline visuel",
    de: "Visuelle Pipeline",
  },
  hint: {
    en: "Click any step to see its parameters and what it produced.",
    zh: "点击任一步骤查看其参数与产出。",
    ru: "Нажмите на любой шаг, чтобы увидеть его параметры и результат.",
    fr: "Cliquez sur une étape pour voir ses paramètres et son résultat.",
    de: "Klicken Sie auf einen Schritt, um Parameter und Ergebnis zu sehen.",
  },
  status: {
    en: "Status",
    zh: "状态",
    ru: "Статус",
    fr: "Statut",
    de: "Status",
  },
  detail: {
    en: "Output",
    zh: "产出",
    ru: "Результат",
    fr: "Sortie",
    de: "Ausgabe",
  },
  parameters: {
    en: "Parameters in effect",
    zh: "生效参数",
    ru: "Действующие параметры",
    fr: "Paramètres en vigueur",
    de: "Wirksame Parameter",
  },
  compareTitle: {
    en: "How this differs from mainstream mRNA synthesis",
    zh: "与本平台 / 主流 mRNA 序列合成的区别",
    ru: "Отличия от обычного синтеза mRNA",
    fr: "Différences avec la synthèse d'ARNm courante",
    de: "Unterschiede zur gängigen mRNA-Synthese",
  },
  compareHint: {
    en: "This platform produces in-silico research blueprints; mainstream commercial synthesis adds experimental design, wet-lab validation and GMP manufacturing.",
    zh: "本平台产出的是科研级别的计算机模拟图纸；主流商业 mRNA 合成增加了实验设计、湿实验验证与 GMP 生产。",
    ru: "Платформа создаёт исследовательские in-silico-планы; коммерческий синтез добавляет экспериментальный дизайн, валидацию в лаборатории и GMP-производство.",
    fr: "La plateforme produit des plans de recherche in-silico ; la synthèse commerciale ajoute la conception expérimentale, la validation en laboratoire et la fabrication GMP.",
    de: "Die Plattform erzeugt In-silico-Forschungspläne; kommerzielle Synthese ergänzt experimentelles Design, Nasslabor-Validierung und GMP-Fertigung.",
  },
  colDimension: { en: "Dimension", zh: "维度", ru: "Аспект", fr: "Dimension", de: "Dimension" },
  colUs: {
    en: "This platform (research simulation)",
    zh: "本平台（科研模拟）",
    ru: "Эта платформа (симуляция)",
    fr: "Cette plateforme (simulation)",
    de: "Diese Plattform (Simulation)",
  },
  colMainstream: {
    en: "Mainstream mRNA synthesis",
    zh: "主流 mRNA 合成",
    ru: "Обычный синтез mRNA",
    fr: "Synthèse d'ARNm courante",
    de: "Gängige mRNA-Synthese",
  },
  colDiff: { en: "Key difference", zh: "关键差异", ru: "Ключевое отличие", fr: "Différence clé", de: "Hauptunterschied" },
};

export type ComparisonRow = { dim: Loc; us: Loc; mainstream: Loc; diff: Loc };

export const COMPARISON_ROWS: ComparisonRow[] = [
  {
    dim: {
      en: "Codon optimisation",
      zh: "密码子优化",
      ru: "Оптимизация кодонов",
      fr: "Optimisation des codons",
      de: "Codon-Optimierung",
    },
    us: {
      en: "Human-preference codons, in-silico hill-climb + 12 sequence QC checks.",
      zh: "人偏好密码子，约束式爬山 + 12 项序列 QC。",
      ru: "Человеческие кодоны, in-silico hill-climb + 12 проверок QC.",
      fr: "Codons humains, hill-climbing in-silico + 12 contrôles CQ.",
      de: "Humane Codons, In-silico-Hill-Climb + 12 Sequenz-QC-Prüfungen.",
    },
    mainstream: {
      en: "Proprietary algorithms (CAI/tAI, mRNA secondary structure, UTR optimisation) validated by expression experiments.",
      zh: "专有算法（CAI/tAI、mRNA 二级结构、UTR 优化），通过表达实验验证。",
      ru: "Проприетарные алгоритмы (CAI/tAI, вторичная структура mRNA, UTR), подтверждённые экспериментами.",
      fr: "Algorithmes propriétaires (CAI/tAI, structure secondaire de l'ARNm, UTR) validés par des expériences.",
      de: "Proprietäre Algorithmen (CAI/tAI, mRNA-Sekundärstruktur, UTR), experimentell validiert.",
    },
    diff: {
      en: "We design and QC in-silico; mainstream adds experimental design validation.",
      zh: "本平台为计算机设计+QC；主流增加实验设计验证。",
      ru: "Мы проектируем и проверяем in-silico; мейнстрим добавляет экспериментальную валидацию.",
      fr: "Nous concevons et contrôlons in-silico ; le courant dominant ajoute une validation expérimentale.",
      de: "Wir entwerfen und prüfen in-silico; der Mainstream ergänzt experimentelle Validierung.",
    },
  },
  {
    dim: {
      en: "5' cap & 5' UTR",
      zh: "5' 帽与 5' UTR",
      ru: "5'-кэп и 5'-UTR",
      fr: "Coiffe 5' et 5' UTR",
      de: "5'-Cap & 5'-UTR",
    },
    us: {
      en: "Template Cap1 / T7 promoter parameters.",
      zh: "模板化的 Cap1 / T7 启动子参数。",
      ru: "Шаблонные параметры Cap1 / промотора T7.",
      fr: "Paramètres modèle Cap1 / promoteur T7.",
      de: "Vorlagenparameter Cap1 / T7-Promotor.",
    },
    mainstream: {
      en: "CleanCap / ARCA cap analogues and optimised 5' UTR sequences.",
      zh: "CleanCap / ARCA 帽类似物与优化 5' UTR 序列。",
      ru: "Аналоги кэпа CleanCap / ARCA и оптимизированные 5'-UTR.",
      fr: "Analogues de coiffe CleanCap / ARCA et 5' UTR optimisés.",
      de: "CleanCap-/ARCA-Cap-Analoga und optimierte 5'-UTR.",
    },
    diff: {
      en: "Template parameters, not a validated cap chemistry.",
      zh: "为模板参数，非经验证的加帽化学。",
      ru: "Шаблонные параметры, а не проверенная химия кэпа.",
      fr: "Paramètres modèle, pas une chimie de coiffe validée.",
      de: "Vorlagenparameter, keine validierte Cap-Chemie.",
    },
  },
  {
    dim: {
      en: "Nucleoside modification",
      zh: "核苷修饰",
      ru: "Модификация нуклеозидов",
      fr: "Modification des nucléosides",
      de: "Nukleosid-Modifikation",
    },
    us: {
      en: "Template m1Ψ / m5C options.",
      zh: "模板化的 m1Ψ / m5C 选项。",
      ru: "Шаблонные опции m1Ψ / m5C.",
      fr: "Options modèle m1Ψ / m5C.",
      de: "Vorlagenoptionen m1Ψ / m5C.",
    },
    mainstream: {
      en: "Experimentally validated modifications for immunogenicity and stability.",
      zh: "经实验验证的修饰，用于免疫原性与稳定性。",
      ru: "Экспериментально проверенные модификации для иммуногенности и стабильности.",
      fr: "Modifications validées pour l'immunogénicité et la stabilité.",
      de: "Experimentell validierte Modifikationen für Immunogenität und Stabilität.",
    },
    diff: {
      en: "Template only.",
      zh: "仅模板。",
      ru: "Только шаблон.",
      fr: "Modèle uniquement.",
      de: "Nur Vorlage.",
    },
  },
  {
    dim: {
      en: "3' UTR & poly(A)",
      zh: "3' UTR 与 poly(A)",
      ru: "3'-UTR и poly(A)",
      fr: "3' UTR et poly(A)",
      de: "3'-UTR & poly(A)",
    },
    us: {
      en: "Template 3' UTR / poly(A) tail.",
      zh: "模板化 3' UTR / poly(A) 尾。",
      ru: "Шаблонные 3'-UTR / хвост poly(A).",
      fr: "Modèle 3' UTR / queue poly(A).",
      de: "Vorlage 3'-UTR / poly(A)-Schwanz.",
    },
    mainstream: {
      en: "Optimised 3' UTR elements and tail-length control.",
      zh: "优化的 3' UTR 元件与尾长控制。",
      ru: "Оптимизированные элементы 3'-UTR и контроль длины хвоста.",
      fr: "Éléments 3' UTR optimisés et contrôle de la longueur de queue.",
      de: "Optimierte 3'-UTR-Elemente und Schwanzlängen-Kontrolle.",
    },
    diff: {
      en: "Template only.",
      zh: "仅模板。",
      ru: "Только шаблон.",
      fr: "Modèle uniquement.",
      de: "Nur Vorlage.",
    },
  },
  {
    dim: { en: "Production", zh: "生产", ru: "Производство", fr: "Production", de: "Produktion" },
    us: {
      en: "Simulated IVT / LNP blueprint (templates).",
      zh: "模拟的 IVT / LNP 图纸（模板）。",
      ru: "Смоделированный план IVT / LNP (шаблоны).",
      fr: "Plan IVT / LNP simulé (modèles).",
      de: "Simulierter IVT-/LNP-Plan (Vorlagen).",
    },
    mainstream: {
      en: "Actual IVT, purification (HPLC), LNP encapsulation, CMC and QC release.",
      zh: "实际 IVT、纯化（HPLC）、LNP 包封、CMC 与放行 QC。",
      ru: "Реальный IVT, очистка (HPLC), инкапсуляция LNP, CMC и выпуск QC.",
      fr: "IVT réel, purification (HPLC), encapsulation LNP, CMC et libération CQ.",
      de: "Echte IVT, Aufreinigung (HPLC), LNP-Verkapselung, CMC und QC-Freigabe.",
    },
    diff: {
      en: "We output research blueprints; mainstream produces physical material.",
      zh: "本平台输出科研图纸；主流产出实体材料。",
      ru: "Мы выдаём исследовательские планы; мейнстрим производит физический материал.",
      fr: "Nous produisons des plans de recherche ; le courant dominant produit du matériel physique.",
      de: "Wir liefern Forschungspläne; der Mainstream produziert physisches Material.",
    },
  },
  {
    dim: { en: "Validation", zh: "验证", ru: "Валидация", fr: "Validation", de: "Validierung" },
    us: {
      en: "Sequence/computational QC; no wet-lab.",
      zh: "序列/计算级 QC；无湿实验。",
      ru: "Последовательность/вычислительный QC; без лаборатории.",
      fr: "CQ de séquence/calcul ; pas de laboratoire.",
      de: "Sequenz-/Rechen-QC; kein Nasslabor.",
    },
    mainstream: {
      en: "In-vitro/in-vivo expression, immunogenicity, ELISpot / tetramer.",
      zh: "体外/体内表达、免疫原性、ELISpot / 四聚体。",
      ru: "Экспрессия in vitro/in vivo, иммуногенность, ELISpot / тетрамер.",
      fr: "Expression in vitro/in vivo, immunogénicité, ELISpot / tétramère.",
      de: "In-vitro-/In-vivo-Expression, Immunogenität, ELISpot / Tetramer.",
    },
    diff: {
      en: "No experimental validation here.",
      zh: "此平台不做实验验证。",
      ru: "Здесь нет экспериментальной валидации.",
      fr: "Aucune validation expérimentale ici.",
      de: "Keine experimentelle Validierung.",
    },
  },
  {
    dim: { en: "Compliance", zh: "合规", ru: "Соответствие", fr: "Conformité", de: "Konformität" },
    us: {
      en: "Research use only — not for clinical or human use.",
      zh: "仅科研使用——不用于临床或人体。",
      ru: "Только для исследований — не для клиники или человека.",
      fr: "Usage recherche uniquement — pas pour un usage clinique ou humain.",
      de: "Nur für Forschung — nicht für klinischen oder menschlichen Gebrauch.",
    },
    mainstream: {
      en: "GMP / IND / clinical-grade manufacturing.",
      zh: "GMP / IND / 临床级生产。",
      ru: "GMP / IND / производство клинического класса.",
      fr: "Fabrication GMP / IND / qualité clinique.",
      de: "GMP- / IND- / klinische Produktion.",
    },
    diff: {
      en: "Not a clinical or manufacturing record.",
      zh: "非临床或生产记录。",
      ru: "Не является клинической или производственной записью.",
      fr: "Ce n'est pas un enregistrement clinique ou de fabrication.",
      de: "Kein klinischer oder Produktionsdatensatz.",
    },
  },
];
