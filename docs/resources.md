# Resource download status

What each external resource is for, where it comes from, and its current state
on this installation. Licensing matters: the platform never bundles or
silently substitutes restricted resources.

## Shipped / already downloaded

| Resource | Purpose | Size |
|---|---|---|
| Ensembl 112 / 87 GTF + CDS + index | offline annotation (GRCh38/GRCh37) | ~677 MB |
| VEP REST cache (GRCh38) | rehearsal/annotation cache | 105 MB |
| UniProt reviewed proteome + 9-mer index | self-similarity filter | ~100 MB |
| MHCflurry 2.3.14 models (`models_class1_presentation`) | Class I presentation | ~189 MB |
| IEDB MS ligands (`iedb_ms_ligands.csv.bz2`) | real immunopeptidome evidence | 2 MB (400 k pairs) |
| MixMHCpred 3.0 (repo + `lib/`) | Class I binding | ~111 MB |
| PRIME 2.1 (repo + `PerRank` models) | immunogenicity (TCR-facing) | ~20 MB |
| 5' UTR MPRA (GEO GSM4084997 via ProtRNA `data_mrl.zip`) | UTR training | 15 MB (106 k sequences) |
| HLA allele frequencies (curated) | population coverage | 60 KB (3 245 alleles) |

## Downloadable free (action available)

| Resource | Purpose | Source | Size |
|---|---|---|---|
| ClinVar VCF GRCh38 | variant evidence | `ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz` | ~190 MB |
| IEDB weekly benchmark | presentation benchmark | `datasets.iedb.org` (⚠️ unreachable here) or `scripts/build_real_benchmark.py` fallback | — |
| GATK bundle (af-only-gnomad, Mutect2 PoN) + GRCh38 FASTA | upstream BAM→VCF | Broad/GATK resource bundle | ~30–50 GB |
| STAR/HISAT2 + GRCh38 index | RNA quantification upstream | public | ~30 GB |
| HLA Ligand Atlas | immunopeptidome training | hla-ligand-atlas.org | GB-scale |
| gnomAD VCF (local) | offline population filtering | gnomAD | ~100 GB+ |

## License-gated (user must accept/download)

| Resource | License |
|---|---|
| NetMHCpan 4.2 / NetMHCIIpan 4.3 | DTU free academic (`sw_request` form) |
| NetChop 3.1 | DTU free academic (`sw_request` form) |
| COSMIC | commercial subscription |
| ANNOVAR | academic registration |

## Unreachable from this network

`datasets.iedb.org`, `allelefrequencies.net` (AFND), `web.archive.org`,
GitHub **release assets** CDN (`release-assets.githubusercontent.com`). Work-
arounds used: IEDB **query API** (`query-api.iedb.org`) for MS ligands; Zenodo
for the MPRA table; `codeload.github.com` tarballs for source repos.
