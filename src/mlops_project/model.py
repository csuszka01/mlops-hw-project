from __future__ import annotations

from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
    explained_variance_score,  # CHANGED, added import
    max_error,  # CHANGED, added import
    mean_absolute_percentage_error,  # CHANGED, added import
    median_absolute_error,  # CHANGED, added import
)
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import Settings

MODEL_FAMILIES = ("hgb",)  # CHANGED, added


def build_model(family: str, hyperparams: dict, settings: Settings) -> Pipeline:  # CHANGED, new signature
    """Build an unfitted pipeline for `family` with `hyperparams`."""
    if family == "hgb":  # CHANGED, replaces the problem_type branches
        estimator = HistGradientBoostingRegressor(
            random_state=settings.random_seed,
            max_iter=settings.max_iter,
            **hyperparams,
        )
    else:
        raise ValueError(
            f"Unknown model family {family!r}; expected one of {MODEL_FAMILIES}."
        )

    preprocess = ColumnTransformer([
        ("num",
         make_pipeline(SimpleImputer(strategy="median"), StandardScaler()),
         make_column_selector(dtype_include="number")),
        ("cat",
         make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
         make_column_selector(dtype_exclude="number")),
    ])

    return Pipeline([("preprocess", preprocess), ("model", estimator)])


def evaluate_model(model: Pipeline, x_test, y_test, settings: Settings) -> dict:
    predictions = model.predict(x_test)
    if settings.problem_type == "classification":
        probabilities = model.predict_proba(x_test)[:, 1]
        return {
            "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
            "precision": round(float(precision_score(y_test, predictions, average="weighted", zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, predictions, average="weighted", zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, predictions, average="weighted", zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
            "per_class": classification_report(
                y_test, predictions, output_dict=True, zero_division=0
            ),
        }
    return {
        "rmse": round(float(root_mean_squared_error(y_test, predictions)), 4),
        "mae": round(float(mean_absolute_error(y_test, predictions)), 4),
        "r2": round(float(r2_score(y_test, predictions)), 4),
    }