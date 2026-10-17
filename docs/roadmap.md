# 科研化路线图与缺口清单

本文档区分**已实现（软件侧）**与**需外部资源（无法仅靠代码补齐）**。

## 已实现并验证

| 能力 | 说明 |
| ---- | ---- |
| 真实注释 | Ensembl **VEP REST**（GRCh38/37），真实基因/转录本/后果/HGVSp，release=116，带重试 |
| 完全离线注释 | **本地 Ensembl GTF + CDS**（release 112，GRCh38）自算基因/转录本/后果/蛋白变化/突变肽，运行时**零网络**，可在 Ensembl 故障时使用（提供方 `offline`） |
| 真实肽段 | 从 Ensembl 参考 CDS 翻译生成突变上下文（≤11aa） |
| 肽段枚举 | 8–11mer 全窗口，MHCflurry 逐个预测取最优（`detail.n_windows`） |
| 真实 I 类预测 | **MHCflurry 2.3** presentation（binding/processing/presentation + 版本） |
| 自身蛋白 off-target 过滤 | **UniProt 人类参考蛋白组**（20,652 蛋白 / 10.4M 9-mer 索引）→ 自身肽段标记并剔除 |
| mRNA 构建 | 人类偏好密码子优化、SVG/PDF/HTML 图纸、报告 |
| 可复现性 | `GET /api/system/manifest`（工具/包版本、提供方、self-filter 状态）；报告内嵌《方法学与版本》 |
| 生产图纸引擎 | 约束式序列设计 + 12 项序列级 QC/放行 + IVT/引物/LNP/化学/放行图纸包 + 实验工作单 |
| Class II 预测 | **MHCnuggets 2.4**（隔离 Keras-2 环境，子进程）；联合面板 I+II |
| 人群 HLA 覆盖率 | 等位基因并集近似（`/population-coverage`）；频率表可用 `HLA_FREQUENCIES_CSV` 覆盖 |
| MS 证据加权 | 排序引入 `ms_evidence` 分量（MHCflurry/IEDB 配体数据） |
| 已知/临床变异证据 | 经 VEP `colocated_variants` 捕获 ClinVar/COSMIC ID 与临床意义，写入注解（`known_variants`/`clinical_significance`）并带 VEP 响应缓存 |
| 提供方默认 | 一键生成默认注释用 mock（VEP 可选），避免 Ensembl 临时故障阻塞 |
| QC/HLA/表达/排序/报告/验证 | 前序阶段能力保留 |

启动 self-filter：把人类蛋白组 FASTA 路径写入 `backend/.env` 的
`HUMAN_PROTEOME_FASTA`（示例：UniProt `UP000005640_9606.fasta`）。

## 需外部资源（当前无法仅靠代码补齐）

| 缺口 | 需要什么 |
| ---- | -------- |
| 原始数据 → 体细胞 calling | 比对(BWA-MEM2)、Mutect2/Strelka2、PoN、gnomAD 过滤、纯度/倍性(FACETS/PURPLE)、污染 QC；GRCh38 参考(~3GB) + conda/docker |
| 离线注释/人群库 | 本地 VEP + cache 或离线 DB；gnomAD/COSMIC/ClinVar 本地库；ANNOVAR(授权) |
| 人群特异 HLA 频率 | 接入 AFND 等真实人群频率（现为精选示例表） |
| 质谱免疫肽组证据（全量） | IEDB / HLA Ligand Atlas 等完整数据库（现用 MHCflurry 附带公开 MS 数据） |
| HLA 分型 / RNA 定量 | OptiType/HLA-LA/arcasHLA、Salmon/kallisto/RSEM（需二进制/conda） |
| 多工具一致性 | 安装更多预测器做共识投票 |
| 工作流/规模/隐私 | Nextflow/Snakemake + 容器 + 队列 + 对象存储 + GPU + GDPR/HIPAA |
| 基准与湿实验 | TESLA/NCI/HiTIDE 基准、ELISpot/四聚体/质谱验证 |
| mRNA 生产级设计 | CAI/二级结构优化、UTR/信号肽、m5C/Ψ、LNP、CMC/GMP |
| 监管 | IBC/IRB/知情同意、IND/临床试验 |

## 建议顺序

1. 用真实 UniProt proteome 打开 self-filter（**已完成**）。
2. Class II：优先 NetMHCIIpan 授权；或专门建一个 Keras 2/TF 兼容 venv 运行 MHCnuggets（作为子进程提供方）。
3. 上游：在具备 conda/docker 的机器接入 BAM→体细胞管线。
4. 离线注释库 + 工作流引擎 + 基准集。
5. 湿实验与 GMP/监管。
