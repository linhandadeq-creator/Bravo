# 一键生成用户模块 (Phase 9)

用户只上传相关文件，系统自动完成整条经验证的流程并生成 **mRNA 疫苗图纸**。

## 输入

| 文件 | 必填 | 说明 |
| ---- | ---- | ---- |
| 肿瘤 VCF | 是 | `.vcf` / `.vcf.gz` |
| 正常 VCF | 配对必需 | 缺失则 `BLOCKED` |
| HLA 文件 | 否 | JSON / CSV / TSV |
| 表达谱文件 | 否 | CSV / TSV |

参数：项目名称、参考基因组版本、预测提供方、抗原数量 Top N、构建格式、
`use_synthetic_context`（缺失 HLA/表达谱时是否用合成上下文，明确标注）、
`demo`（使用合成数据集端到端演示）。

## 自动流程

```
上传 → 质控 → 注释 → HLA → 表达谱 → 候选 → 预测 → 排序 → 构建 → 图纸 → 报告
```

## 输出

- **mRNA 图纸**：有序片段（[5PRIME] [ANTIGEN_001] [SPACER] … [3PRIME]）、模拟核酸序列、SVG 示意图。
- **构建报告**：完整 HTML 分析报告。
- 每个阶段的执行状态（PASS / INGESTED / BLOCKED …）。

## 接口

| Method | Path | 说明 |
| ------ | ---- | ---- |
| POST | `/api/one-click/generate` | 一键生成（multipart） |
| GET | `/api/constructs/{id}/blueprint?format=pdf\|svg\|html\|json` | 图纸（PDF 直接输出） |

## 原则

- **不伪造数据**：缺失正常 VCF / HLA / 表达谱一律明确报错 `BLOCKED`，绝不使用默认值替代。
- **可追溯**：沿用各阶段的 provenance 与验证。
- **安全声明**：图纸为基于模拟数据的研究示意图，不代表临床或治疗有效性，不可用于临床或人体。

## 测试

`tests/test_one_click.py` 覆盖：合成演示一键生成、缺正常样本 `BLOCKED`、缺 HLA `BLOCKED`、图纸三种格式。
