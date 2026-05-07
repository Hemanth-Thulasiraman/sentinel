# sentinel/classifier/features.py
import pandas as pd
from datetime import datetime

SERVICE_ENCODING = {
    "auth-service": 0,
    "payment-service": 1,
    "nginx": 2,
    "database": 3,
    "api-gateway": 4,
    "user-service": 5,
}


FEATURE_COLUMNS = [
    "message_length",
    "service_encoded",
    "is_weekend",
    # NOT hour_of_day — EDA showed 0.009 correlation
]

def extract_features(log: dict) -> dict:
    timestamp = log["timestamp"]
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    
    service_encoded = SERVICE_ENCODING.get(log["service_name"], -1)
    message_length = len(log["message"])
    is_weekend = int(timestamp.weekday() >= 5)

    return {
        "message_length": message_length,
        "service_encoded": service_encoded,
        "is_weekend": is_weekend,
    }
 
def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms the full training dataframe into a feature matrix.
    Called once during training.
    """
    features = df.apply(
        lambda row: extract_features(row.to_dict()), axis=1
    )
    return pd.DataFrame(features.tolist())[FEATURE_COLUMNS]
