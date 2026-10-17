import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault(
    "STORAGE_DIR", tempfile.mkdtemp(prefix="neoantigen-test-storage-")
)

import app.models  # noqa: E402,F401  (register all models on Base.metadata)
from app.db.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.synthetic import generate_synthetic_dataset  # noqa: E402

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
@event.listens_for(engine, "connect")
def _enable_fk(dbapi_connection, _record):  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    # Background job workers use app.db.session.SessionLocal; point it at the
    # test engine so async jobs operate on the same in-memory database.
    import app.db.session as _dbs

    original = _dbs.SessionLocal
    _dbs.SessionLocal = TestingSessionLocal
    Base.metadata.create_all(bind=engine)
    yield
    _dbs.SessionLocal = original
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def synthetic_dataset(tmp_path):
    return generate_synthetic_dataset(tmp_path / "synthetic")


ANNOTATION_HEADER = "\n".join(
    [
        "##fileformat=VCFv4.2",
        "##reference=GRCh38",
        "##contig=<ID=chr1,length=248956422>",
        "##contig=<ID=chr2,length=242193529>",
        "##contig=<ID=chr9,length=138394717>",
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
    ]
)
ANNOTATION_RECORDS = [
    "chr1\t1003\t.\tA\tG\t60\tPASS\t.\tGT:DP:AF\t0/1:30:0.30",
    "chr1\t1008\t.\tG\tA\t60\tPASS\t.\tGT:DP:AF\t0/1:30:0.30",
    "chr2\t5003\t.\tC\tT\t60\tPASS\t.\tGT:DP:AF\t0/1:30:0.30",
    "chr9\t12345\t.\tA\tG\t60\tPASS\t.\tGT:DP:AF\t0/1:30:0.30",
]


def write_annotation_vcf(path, sample_name: str) -> None:
    content = ANNOTATION_HEADER
    content += f"\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample_name}\n"
    content += "\n".join(ANNOTATION_RECORDS) + "\n"
    path.write_text(content)


@pytest.fixture
def annotation_dataset(tmp_path):
    tumor = tmp_path / "annotation_tumor.vcf"
    normal = tmp_path / "annotation_normal.vcf"
    write_annotation_vcf(tumor, "TUMOR")
    write_annotation_vcf(normal, "NORMAL")
    return {"tumor": str(tumor), "normal": str(normal)}


@pytest.fixture
def annotated_run(client, annotation_dataset):
    project_id = client.post(
        "/api/projects", json={"name": "Annotation Fixture Project"}
    ).json()["id"]
    with open(annotation_dataset["tumor"], "rb") as tf, open(
        annotation_dataset["normal"], "rb"
    ) as nf:
        run = client.post(
            "/api/analysis-runs/upload",
            data={"project_id": project_id, "reference_build": "GRCh38"},
            files={
                "tumor_file": ("tumor.vcf", tf, "text/plain"),
                "normal_file": ("normal.vcf", nf, "text/plain"),
            },
        ).json()
    assert run["status"] == "PASS", run.get("error_message")
    client.post(f"/api/analysis-runs/{run['id']}/annotate", json={"provider": "mock"})
    return {"project_id": project_id, "run_id": run["id"]}
