from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROBLEM_TYPES = ("classification", "regression")
SLICE_KINDS = ("bins", "category", "missing_flag")


@dataclass(frozen=True)
class Settings:
    """Project configuration.

    Hyperparameters come from params.yaml so that DVC can record them.
    Wiring such as paths and column names comes from .env.
    """

    data_path: Path = Path("data/dataset.csv")
    target_column: str = "Actual_Response_Time_min"
    problem_type: str = "regression"
    test_size: float = 0.2
    random_seed: int = 42
    model_family: str = "hgb"
    learning_rate: float = 0.05
    max_iter: int = 300
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 50
    l2_regularization: float = 1.0
    slice_specs: dict = field(default_factory=dict)
    acceptance: dict = field(default_factory=dict)
    project_root: Path = field(default_factory=lambda: Path("."))
    measurements_path: Path = Path("data/measurements.csv")
    raw_dir: Path = Path("data/raw")
    quality_dir: Path = Path("data/quality")
    processed_dir: Path = Path("data/processed")
    models_dir: Path = Path("models")
    metrics_path: Path = Path("metrics/metrics.json")
    run_id_path: Path = Path("models/mlflow_run_id.json")
    validation_report_path: Path = Path("reports/validation.json")
    gate_report_path: Path = Path("reports/gate.json")
    slices_path: Path = Path("metrics/slices.json")
    baseline_path: Path = Path("metrics/baseline.json")
    mlflow_tracking_uri: str = "http://127.0.0.1:5500"
    prefect_api_url: str = "http://127.0.0.1:5520/api"
    mlflow_experiment_name: str = "ambulance-response-time"
    registered_model_name: str = "ambulance-response-regressor"
    model_alias: str = "staging"
    champion_alias: str = "champion"
    model_owner: str = "unknown"
    dvc_remote_name: str = "storage"
    dvc_bucket: str = "dvc-storage"
    dvc_remote_path: str = "dvcstore"


def load_params(project_root: Path) -> dict:
    """Read params.yaml. Returns an empty dict if it is absent."""
    params_file = project_root / "params.yaml"
    if not params_file.exists():
        return {}
    return yaml.safe_load(params_file.read_text()) or {}


def load_settings(project_root: Path | None = None) -> Settings:
    base_path = project_root or Path(__file__).resolve().parents[2]
    load_dotenv(base_path / ".env")
    params = load_params(base_path)
    prepare = params.get("prepare") or {}
    train = params.get("train") or {}
    evaluation = params.get("evaluation") or {}
    acceptance = params.get("acceptance") or {}

    settings = Settings(
        project_root=base_path,
        data_path=base_path / os.getenv("DATA_PATH", "data/dataset.csv"),
        target_column=os.getenv("TARGET_COLUMN", "Actual_Response_Time_min"),
        problem_type=os.getenv("PROBLEM_TYPE", "regression").strip().lower(),
        test_size=float(prepare.get("test_size", 0.2)),
        random_seed=int(params.get("random_seed", 42)),
        model_family=str(train.get("family", "hgb")),
        learning_rate=float(train.get("learning_rate", 0.05)),
        max_iter=int(train.get("max_iter", 300)),
        max_leaf_nodes=int(train.get("max_leaf_nodes", 15)),
        min_samples_leaf=int(train.get("min_samples_leaf", 50)),
        l2_regularization=float(train.get("l2_regularization", 1.0)),
        slice_specs=dict(evaluation.get("slices") or {}),
        acceptance=dict(acceptance),
        measurements_path=base_path / os.getenv("MEASUREMENTS_PATH", "data/measurements.csv"),
        raw_dir=base_path / "data/raw",
        quality_dir=base_path / "data/quality",
        processed_dir=base_path / "data/processed",
        models_dir=base_path / "models",
        metrics_path=base_path / "metrics/metrics.json",
        run_id_path=base_path / "models/mlflow_run_id.json",
        validation_report_path=base_path / "reports/validation.json",
        gate_report_path=base_path / "reports/gate.json",
        slices_path=base_path / "metrics/slices.json",
        baseline_path=base_path / "metrics/baseline.json",
        mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5500"),
        prefect_api_url=os.getenv("PREFECT_API_URL", "http://127.0.0.1:5520/api"),
        mlflow_experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME", "ambulance-response-time"),
        registered_model_name=os.getenv("MLFLOW_REGISTERED_MODEL_NAME", "ambulance-response-regressor"),
        model_alias=os.getenv("MLFLOW_MODEL_ALIAS", "staging"),
        champion_alias=os.getenv("MLFLOW_CHAMPION_ALIAS", "champion"),
        model_owner=os.getenv("MLFLOW_MODEL_OWNER", "unknown"),
        dvc_remote_name=os.getenv("DVC_REMOTE_NAME", "storage"),
        dvc_bucket=os.getenv("DVC_BUCKET", "dvc-storage"),
        dvc_remote_path=os.getenv("DVC_REMOTE_PATH", "dvcstore"),
    )
    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    if settings.problem_type not in PROBLEM_TYPES:
        raise ValueError(f"PROBLEM_TYPE must be one of {PROBLEM_TYPES}.")
    if not 0.0 < settings.test_size < 1.0:
        raise ValueError("prepare.test_size in params.yaml must be between 0 and 1.")
    if settings.learning_rate <= 0:
        raise ValueError("train.learning_rate in params.yaml must be greater than 0.")
    if settings.max_iter < 1:
        raise ValueError("train.max_iter in params.yaml must be at least 1.")
    if settings.max_leaf_nodes < 2:
        raise ValueError("train.max_leaf_nodes in params.yaml must be at least 2.")
    if settings.min_samples_leaf < 1:
        raise ValueError("train.min_samples_leaf in params.yaml must be at least 1.")
    if settings.l2_regularization < 0:
        raise ValueError("train.l2_regularization in params.yaml must be 0 or greater.")
    if settings.prefect_api_url and not settings.prefect_api_url.startswith("http"):
        raise ValueError("PREFECT_API_URL must start with http:// or https://")
    _validate_slices(settings.slice_specs)


def _validate_slices(specs: dict) -> None:
    for name, spec in (specs or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(f"evaluation.slices.{name} must be a mapping.")
        if "column" not in spec:
            raise ValueError(f"evaluation.slices.{name} must name a `column`.")
        kind = spec.get("kind", "bins")
        if kind not in SLICE_KINDS:
            raise ValueError(
                f"evaluation.slices.{name}.kind must be one of {SLICE_KINDS}; "
                f"got {kind!r}."
            )
        if kind == "bins":
            edges = spec.get("bins")
            labels = spec.get("labels")
            if not edges or len(edges) < 2:
                raise ValueError(
                    f"evaluation.slices.{name}.bins needs at least two edges."
                )
            if list(edges) != sorted(edges):
                raise ValueError(
                    f"evaluation.slices.{name}.bins must be in ascending order."
                )
            if not labels or len(labels) != len(edges) - 1:
                raise ValueError(
                    f"evaluation.slices.{name} declares {len(edges) - 1} bin(s) "
                    f"but {len(labels or [])} label(s); they must match."
                )