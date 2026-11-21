"""The data contracts: `RawMeasurements` guards ingestion, `ModelInput` guards the model.

    batch file --> [RawMeasurements] --> 0 -> NA --> [ModelInput] --> Pipeline
"""

from __future__ import annotations

from typing import Optional

import pandera.pandas as pa
from pandera.typing.pandas import Series

from .data import FEATURE_COLUMNS, TARGET_COLUMN

# CHANGED, no column here uses 0 as "not measured", so the tuple is empty.
# to_nullable and sentinel_counts in validation.py then do nothing.
SENTINEL_COLUMNS: tuple[str, ...] = ()

# CHANGED, upper bounds taken from the maximums in DATA_DICTIONARY.md
MAX_VISIBILITY = 15000.0
MAX_CONGESTION = 100.0
MAX_RESPONSE_TIME = 1000.0


class RawMeasurements(pa.DataFrameModel):
    """What an arriving batch may look like. Zeros are allowed here (`ge=0`)."""

    Hour: Series[int] = pa.Field(ge=0, le=23, nullable=False)
    Month: Series[int] = pa.Field(ge=1, le=12, nullable=False)
    Area_Type: Series[str] = pa.Field(isin=["Urban", "Suburban", "Rural"], nullable=False)
    Road_Type: Series[str] = pa.Field(
        isin=["Interstate", "Arterial", "Collector", "Local"], nullable=False
    )
    Intersection_Type: Series[str] = pa.Field(
        isin=["4-Way", "T-Junction", "Roundabout", "None"], nullable=False
    )
    Road_Condition: Series[str] = pa.Field(
        isin=["Dry", "Wet", "Snowy", "Icy", "Standing Water"], nullable=False
    )
    Weather: Series[str] = pa.Field(isin=["clear", "rain", "snow", "fog"], nullable=False)
    Visibility_m: Series[float] = pa.Field(gt=0, le=MAX_VISIBILITY, nullable=True)
    Congestion_Index: Series[float] = pa.Field(gt=0, le=MAX_CONGESTION, nullable=False)
    Dispatch_Priority: Series[str] = pa.Field(
        isin=["Standard", "Medium", "High"], nullable=False
    )
    Actual_Response_Time_min: Series[float] = pa.Field(
        gt=0, le=MAX_RESPONSE_TIME, nullable=False
    )

    # CHANGED, lowercases Weather before the check, as you wanted
    @pa.parser("Weather")
    def normalize_weather(cls, series):
        return series.str.strip().str.lower()


    class Config:
        name = "RawMeasurements"
        coerce = True
        strict = True
        unique_column_names = True

    @pa.dataframe_check(name="no_duplicate_rows")
    def no_duplicate_rows(cls, frame) -> bool:
        """A duplicated row inflates both the training set and the test metrics."""
        return not frame.duplicated().any()


class ModelInput(pa.DataFrameModel):
    """What the model may see, in training and in serving.

    `strict` rejects extra columns and `ordered` rejects reordered ones.
    """

    # CHANGED, all fields replaced, the declaration order is the contract
    Hour: Series[int] = pa.Field(ge=0, le=23, nullable=False)
    Month: Series[int] = pa.Field(ge=1, le=12, nullable=False)
    Area_Type: Series[str] = pa.Field(isin=["Urban", "Suburban", "Rural"], nullable=False)
    Road_Type: Series[str] = pa.Field(
        isin=["Interstate", "Arterial", "Collector", "Local"], nullable=False
    )
    Intersection_Type: Series[str] = pa.Field(
        isin=["4-Way", "T-Junction", "Roundabout", "None"], nullable=False
    )
    Road_Condition: Series[str] = pa.Field(
        isin=["Dry", "Wet", "Snowy", "Icy", "Standing Water"], nullable=False
    )
    Weather: Series[str] = pa.Field(isin=["clear", "rain", "snow", "fog"], nullable=False)
    Visibility_m: Series[float] = pa.Field(gt=0, le=MAX_VISIBILITY, nullable=True)
    Congestion_Index: Series[float] = pa.Field(gt=0, le=MAX_CONGESTION, nullable=False)
    Dispatch_Priority: Series[str] = pa.Field(
        isin=["Standard", "Medium", "High"], nullable=False
    )
    Actual_Response_Time_min: Series[float] = pa.Field(
        gt=0, le=MAX_RESPONSE_TIME, nullable=False
    )

    # CHANGED, the same Weather normalization as in RawMeasurements
    @pa.parser("Weather")
    def normalize_weather(cls, series):
        return series.str.strip().str.lower()

    class Config:
        name = "ModelInput"
        coerce = True
        strict = True
        ordered = True


class PredictionInput(ModelInput):
    """`ModelInput` minus the label, what a serving request carries."""

    # `Optional` marks the column as allowed to be absent.
    # CHANGED, was outcome with isin=[0, 1]
    Actual_Response_Time_min: Optional[Series[float]] = pa.Field(
        gt=0, le=MAX_RESPONSE_TIME, nullable=True
    )

    class Config:
        name = "PredictionInput"
        coerce = True
        strict = True
        # A JSON request has no column order; `inference.payload_to_frame` sets one.
        ordered = False


# The column order `ModelInput` enforces.
MODEL_INPUT_COLUMNS = list(FEATURE_COLUMNS) + [TARGET_COLUMN]

# Fail at import time if the schema and `MODEL_INPUT_COLUMNS` disagree on the order.
# Skipped while `ModelInput` is incomplete.
_declared = list(ModelInput.to_schema().columns)
if set(_declared) == set(MODEL_INPUT_COLUMNS):
    assert _declared == MODEL_INPUT_COLUMNS, (
        "ModelInput declares the right columns in the wrong order; it must match "
        "FEATURE_COLUMNS + TARGET_COLUMN in data.py.\n"
        f"  schema : {_declared}\n"
        f"  data.py: {MODEL_INPUT_COLUMNS}"
    )

# Bump when a rule changes. It is logged on the MLflow run.
SCHEMA_VERSION = "1.0.0"
