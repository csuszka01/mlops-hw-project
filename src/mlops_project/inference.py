"""Validate one prediction request against the contract, then predict."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from .data import FEATURE_COLUMNS
from .schemas import PredictionInput
from .validation import to_nullable, validate_frame


def payload_to_frame(payload: dict) -> pd.DataFrame:
    """One request dict as a one-row DataFrame, known columns first in model order."""
    frame = pd.DataFrame([payload])
    known = [column for column in FEATURE_COLUMNS if column in frame.columns]
    extra = [column for column in frame.columns if column not in FEATURE_COLUMNS]
    return frame[known + extra]


def validate_payload(payload: dict) -> dict:
    """Validate one request against `PredictionInput` and return the report."""
    frame = payload_to_frame(payload)
    return validate_frame(frame, PredictionInput, source="request payload")


def predict_one(payload: dict, model_path: Path) -> dict:
    """Validate, then predict.

    Returns the validation report and, only for a legal payload, the prediction
    and its probability. A rejected request never reaches the model.
    """
    report = validate_payload(payload)
    result: dict = {"report": report, "prediction": None}

    # `not report` is an empty report, from a `validate_frame` not written yet.
    if not report or not report["passed"]:
        return result

    if not model_path.exists():
        raise FileNotFoundError(
            f"{model_path.name} is missing. Run `make repro` to train a model first."
        )

    model = joblib.load(model_path)
    frame = to_nullable(payload_to_frame(payload))[list(FEATURE_COLUMNS)]

    # CHANGED, the float64 cast is removed, the model pipeline imputes and encodes by column type
    result["prediction"] = round(float(model.predict(frame)[0]), 2)  # CHANGED, minutes, was int
    return result


def load_payload(source: str) -> dict:
    """A payload from a JSON string or a path to a JSON file."""
    path = Path(source)
    if path.exists():
        return json.loads(path.read_text())
    return json.loads(source)


# A legal request, the first row of the dataset without the target.  # CHANGED, whole block
EXAMPLE_PAYLOAD = {
    "Hour": 14,
    "Month": 5,
    "Area_Type": "Urban",
    "Road_Type": "Interstate",
    "Intersection_Type": "None",
    "Road_Condition": "Dry",
    "Weather": "Clear",
    "Visibility_m": 9540.8,
    "Congestion_Index": 82.3,
    "Dispatch_Priority": "Standard",
}

# The same request with an impossible hour.
ILLEGAL_PAYLOAD = {**EXAMPLE_PAYLOAD, "Hour": 99}

# `Visibility_m` and `Congestion_Index` swapped, the congestion value is above 100.
SWAPPED_PAYLOAD = {**EXAMPLE_PAYLOAD, "Visibility_m": 82.3, "Congestion_Index": 9540.8}

INCOMPLETE_PAYLOAD = {
    key: value for key, value in EXAMPLE_PAYLOAD.items() if key != "Visibility_m"
}
