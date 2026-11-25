"""Smoke tests that run WITHOUT your dataset (synthetic data), so the template is
green the moment you create it. Replace/extend these as your project grows."""
from __future__ import annotations

import numpy as np
import pandas as pd

from mlops_project.config import Settings
from mlops_project.data import build_dataset
from mlops_project.model import build_model, evaluate_model
from mlops_project.pipeline import _hyperparams



def test_regression_pipeline_trains():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(120, 3))
    df = pd.DataFrame(x, columns=["a", "b", "c"])
    df["target"] = 2 * x[:, 0] - x[:, 1] + rng.normal(scale=0.1, size=120)
    settings = Settings(problem_type="regression", test_size=0.25, random_seed=1, target_column="target")
    x_tr, x_te, y_tr, y_te = build_dataset(settings, frame=df)
    model = build_model(settings.model_family, _hyperparams(settings), settings)
    model.fit(x_tr, y_tr)
    metrics = evaluate_model(model, x_te, y_te, settings)
    assert {"rmse", "mae", "r2"} <= set(metrics)
