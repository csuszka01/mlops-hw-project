from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import Settings

FEATURE_COLUMNS = [
    "Hour",
    "Month",
    "Area_Type",
    "Road_Type",
    "Intersection_Type",
    "Road_Condition",
    "Weather",
    "Visibility_m",
    "Congestion_Index",
    "Dispatch_Priority",
]
TARGET_COLUMN = "Actual_Response_Time_min"

def load_dataframe(settings: Settings) -> pd.DataFrame:
    """Load your dataset CSV (set DATA_PATH in .env)."""
    if not settings.data_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {settings.data_path}\n"
            "Place your dataset under data/ and set DATA_PATH in .env."
        )
    return pd.read_csv(
        settings.data_path,
        keep_default_na=False,  # keeps "None" in Intersection_Type as text
        na_values=[""],         # empty cells such as Visibility_m stay missing
    )


def build_dataset(settings: Settings, frame: pd.DataFrame | None = None):
    """Split into train/test. Stratifies on the target for classification."""
    frame = load_dataframe(settings) if frame is None else frame
    if settings.target_column not in frame.columns:
        raise KeyError(
            f"Target column '{settings.target_column}' not in data "
            f"(columns: {list(frame.columns)}). Set TARGET_COLUMN in .env."
        )
    features = frame.drop(columns=[settings.target_column])
    labels = frame[settings.target_column]
    stratify = labels if settings.problem_type == "classification" else None
    return train_test_split(
        features,
        labels,
        test_size=settings.test_size,
        random_state=settings.random_seed,
        stratify=stratify,
    )

# pipeline.py imports it
def load_measurements(path) -> pd.DataFrame:
    """Load a measurement CSV. Keeps the text value None in Intersection_Type."""
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


# pipeline.py imports it
def split_measurements(frame: pd.DataFrame, settings: Settings) -> tuple:
    """Split a measurement frame into two frames with all columns."""
    if settings.target_column not in frame.columns:
        raise KeyError(f"Target column '{settings.target_column}' not in data.")
    return train_test_split(
        frame,
        test_size=settings.test_size,
        random_state=settings.random_seed,
    )