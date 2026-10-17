from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Bravo"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = (
        "postgresql+psycopg2://neoantigen:neoantigen@postgres:5432/neoantigen"
    )

    REDIS_URL: str = "redis://redis:6379/0"

    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Optional bearer/API-key token. When empty, authentication is disabled
    # (local/desktop default). When set, all /api/* routes require the token via
    # "Authorization: Bearer <token>" or "X-API-Key: <token>".
    API_TOKEN: str = ""

    # Simple per-client rate limit (requests per minute). 0 disables it.
    RATE_LIMIT_PER_MINUTE: int = 0

    # Directory (relative to the backend working directory) where uploaded and
    # generated VCF files are stored.
    STORAGE_DIR: str = "storage"

    # SQLite only: how long a connection waits for a competing writer before
    # raising "database is locked" (milliseconds). Applied as the sqlite3
    # connect timeout and PRAGMA busy_timeout.
    SQLITE_BUSY_TIMEOUT_MS: int = 30000

    # SQLite only: enable WAL journaling (better reader/writer concurrency on
    # a local filesystem). WAL does not remove SQLite's single-writer limit;
    # it only lets readers proceed while one writer holds the lock.
    SQLITE_WAL: bool = True

    # Maximum accepted upload size (bytes) for streamed uploads — tumour/normal
    # VCFs and project files are streamed straight to disk. Realistic human
    # paired tumour/normal VCFs are ~5–50 MB for exomes and ~0.5–3 GiB
    # uncompressed for whole-genome (50–400 MiB gzipped), so the default covers
    # WGS while staying bounded. Default 3 GiB.
    MAX_UPLOAD_BYTES: int = 3 * 1024 * 1024 * 1024

    # Maximum size (bytes) for uploads read fully into memory (HLA typing and
    # expression tables). Kept intentionally small so a large text upload can
    # never exhaust memory. Default 64 MiB.
    MAX_TEXT_UPLOAD_BYTES: int = 64 * 1024 * 1024

    # Path to a human reference proteome FASTA (e.g. UniProt reviewed). When set,
    # candidate peptides matching the self proteome are filtered out (off-target
    # self-similarity safety check).
    HUMAN_PROTEOME_FASTA: str = ""

    # Directory holding fully-offline annotation data (Ensembl GTF + CDS FASTA)
    # per reference build. Empty = <STORAGE_DIR>/reference. The offline annotator
    # needs no network at runtime.
    OFFLINE_REFERENCE_DIR: str = ""

    # Optional local clinically-associated variants VCF (Ensembl/ClinVar) used by
    # the offline annotator for rsIDs + clinical significance. Empty = auto-detect
    # <reference>/<build>/homo_sapiens_clinically_associated.vcf.gz.
    CLINVAR_VCF: str = ""

    # MS / measured-ligand evidence source (e.g. MHCflurry/ IEDB training data,
    # .csv.bz2). When empty, auto-detects the MHCflurry bundled training data.
    EVIDENCE_MS_TRAINING: str = ""

    # Standalone ClinVar evidence VCF (bgzipped + tabix-indexed, e.g. the NCBI
    # weekly release). Empty = auto-detect <STORAGE_DIR>/evidence/clinvar/.
    CLINVAR_EVIDENCE_VCF: str = ""

    # Class II predictor (MHCnuggets) isolated runtime. Empty = auto-detect the
    # project's .venv-mhcii (Keras 2 / TF 2.15) environment.
    MHCNUGGETS_PYTHON: str = ""
    MHCNUGGETS_RUNNER: str = ""

    # Licensed predictors (used only if a binary/runtime is provided). When
    # empty the corresponding provider reports UNAVAILABLE.
    NETMHCPAN_BIN: str = ""
    NETMHCIIPAN_BIN: str = ""

    # PRIME 2.1 immunogenicity predictor (TCR-facing). PRIME_DIR points at a
    # local PRIME installation (the ``PRIME`` tool and its ``lib`` models);
    # it requires MixMHCpred v3 (MIXMHCPRED_TOOL). The runner is executed
    # with PRIME_PYTHON when set.
    PRIME_DIR: str = ""
    PRIME_PYTHON: str = ""
    PRIME_RUNNER: str = ""

    # MixMHCpred v3 Class I binding predictor (official GfellerLab tool).
    # MIXMHCPRED_TOOL points at the ``MixMHCpred`` executable; the runner
    # executes it with MIXMHCPRED_PYTHON (a Python with numpy/pandas/scipy).
    MIXMHCPRED_PYTHON: str = ""
    MIXMHCPRED_RUNNER: str = ""
    MIXMHCPRED_TOOL: str = ""

    # NetChop proteasomal-cleavage predictor (processing chain). NETCHOP_DIR
    # points at a local NetChop 3.1 installation (contains the netchop binary).
    NETCHOP_DIR: str = ""
    NETCHOP_RUNNER: str = ""

    # Upstream somatic-calling toolchain (optional). Empty = status reports the
    # stage as unavailable; the platform then only accepts pre-called VCFs.
    SOMATIC_BWA_BIN: str = ""
    SOMATIC_GATK_BIN: str = ""
    SOMATIC_REFERENCE_FASTA: str = ""

    # Optional HLA allele frequency CSV (allele,frequency) for population
    # coverage; empty = curated illustrative subset.
    HLA_FREQUENCIES_CSV: str = ""

    # QC thresholds. A shared variant is only classified as confidently SHARED
    # when the normal sample provides enough evidence.
    MIN_DEPTH_FOR_CONFIDENT: int = 10
    MIN_ALLELE_FREQUENCY_FOR_CONFIDENT: float = 0.05

    # Annotation defaults. The allowed consequences are seed values only; the
    # effective filter is user-editable per project and never hardcoded.
    ANNOTATION_DEFAULT_PROVIDER: str = "mock"
    ALLOWED_CONSEQUENCES: str = "missense,frameshift,stop_gained"

    @property
    def storage_path(self) -> Path:
        return Path(self.STORAGE_DIR).resolve()

    @property
    def offline_reference_path(self) -> Path:
        base = self.OFFLINE_REFERENCE_DIR or str(self.storage_path / "reference")
        return Path(base).resolve()

    @property
    def default_allowed_consequences(self) -> list[str]:
        return [item.strip() for item in self.ALLOWED_CONSEQUENCES.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
