# sentinel/classifier/model.py

import joblib
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
import numpy as np

from sentinel.classifier.features import extract_features, build_feature_matrix, FEATURE_COLUMNS
LABEL_ENCODING = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}

LABEL_DECODING = {v: k for k, v in LABEL_ENCODING.items()}

MODEL_PATH = Path("data/models/classifier.joblib")

def train(data_path: str = "data/processed/logs_labeled.csv") -> None:
    df = pd.read_csv(data_path)
    feature_matrix = build_feature_matrix(df)
    labels = df["severity_label"].map(LABEL_ENCODING)
    X_train, X_test, y_train, y_test = train_test_split(feature_matrix, labels, test_size=0.2, stratify=labels)
    sample_weights = compute_sample_weight("balanced", y=y_train)
    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        random_state=42,
        eval_metric="mlogloss",
        early_stopping_rounds=10, )

    model.fit(X_train, y_train, sample_weight=sample_weights, eval_set=[(X_test, y_test)], verbose=False)
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))
    # after classification_report
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    print(f"Macro F1: {macro_f1:.4f}")

    # save model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

def predict(log: dict) -> tuple[str, float]:
    model = joblib.load(MODEL_PATH)
    features = extract_features(log)
    X = pd.DataFrame([features])[FEATURE_COLUMNS]
    prediction = model.predict(X)[0]
    confidence = model.predict_proba(X)[0][prediction]
    return LABEL_DECODING[prediction], float(confidence)

if __name__ == "__main__":
    train()