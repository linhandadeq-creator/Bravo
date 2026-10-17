#!/usr/bin/env python3
"""Train the 5' UTR translation-efficiency model on an MPRA dataset.

Input CSV must have a header with `sequence` and `value` columns (value = e.g.
log ribosome load / mean ribosome load from a public 5' UTR MPRA such as
Sample et al. 2019 / GEO GSM4084997). Fits ridge regression over the features
in ``app.blueprint.utr_model`` and writes ``storage/models/utr_model.json``.

Usage:  python scripts/train_utr_model.py <dataset.csv> [lambda] [--holdout 0.2]
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.blueprint.utr_model import features  # noqa: E402
from app.core.config import settings  # noqa: E402


def _load(path: Path) -> tuple[list[list[float]], list[float]]:
    import gzip

    X: list[list[float]] = []
    y: list[float] = []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", newline="") as handle:
        for row in csv.DictReader(handle):
            seq = (row.get("sequence") or "").strip().upper().replace("U", "T")
            raw = row.get("value")
            if not seq or raw is None or raw == "":
                continue
            try:
                y.append(float(raw))
            except ValueError:
                continue
            X.append(features(seq))
    return X, y


def _fit(Xa: np.ndarray, ya: np.ndarray, lam: float):
    mean = Xa.mean(axis=0)
    Xc = Xa - mean
    y_mean = ya.mean()
    yc = ya - y_mean
    y_std = yc.std() or 1.0
    yc = yc / y_std
    weights = np.linalg.solve(Xc.T @ Xc + lam * np.eye(Xc.shape[1]), Xc.T @ yc)
    return weights, mean, y_mean, y_std


def _r2(X_std: np.ndarray, y_true_std: np.ndarray, weights: np.ndarray) -> float:
    pred = X_std @ weights
    ss_res = float(((y_true_std - pred) ** 2).sum())
    ss_tot = float((y_true_std ** 2).sum()) or 1.0
    return 1.0 - ss_res / ss_tot


def main() -> None:
    argv = sys.argv[1:]
    holdout = 0.0
    lam = 1.0
    positional: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--holdout":
            holdout = float(argv[i + 1])
            i += 2
            continue
        positional.append(argv[i])
        i += 1
    if not positional:
        sys.exit("usage: train_utr_model.py <dataset.csv> [lambda] [--holdout 0.2]")
    path = Path(positional[0])
    if len(positional) > 1:
        lam = float(positional[1])

    X, y = _load(path)
    if len(X) < 50:
        sys.exit(f"need at least 50 samples, got {len(X)}")

    Xa = np.asarray(X, dtype=float)
    ya = np.asarray(y, dtype=float)
    n = len(Xa)

    test_r2 = None
    if holdout > 0:
        order = list(range(n))
        random.Random(20261016).shuffle(order)
        n_test = max(1, int(n * holdout))
        test_idx = set(order[:n_test])
        train_idx = [k for k in range(n) if k not in test_idx]
        Xtr, ytr = Xa[train_idx], ya[train_idx]
        Xte, yte = Xa[sorted(test_idx)], ya[sorted(test_idx)]
        weights, mean, y_mean, y_std = _fit(Xtr, ytr, lam)
        test_r2 = _r2((Xte - mean) / y_std, (yte - y_mean) / y_std, weights)
        n_train = len(train_idx)
    else:
        weights, mean, y_mean, y_std = _fit(Xa, ya, lam)
        n_train = n

    out = settings.storage_path / "models" / "utr_model.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "weights": weights.tolist(),
                "mean": mean.tolist(),
                "bias": float(-float((mean @ weights)) / y_std),
                "n": n_train,
                "y_mean": float(y_mean),
                "y_std": float(y_std),
            },
            indent=2,
        )
    )
    in_sample = _r2((Xa - mean) / y_std, (ya - y_mean) / y_std, weights)
    msg = f"trained on {n_train} samples · R²(in-sample)={in_sample:.3f}"
    if test_r2 is not None:
        msg += f" · R²(holdout)={test_r2:.3f}"
    print(msg + f" -> {out}")


if __name__ == "__main__":
    main()

