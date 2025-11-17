import os
import pandas as pd
import mlflow
import hashlib
from dagster import job, op, repository, ScheduleDefinition
from dagster_aws.s3 import s3_resource

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
DATA_BUCKET = os.getenv("DATA_BUCKET")
DATA_PATH = "/opt/dagster/app/data/sample_data.csv"

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

@op(required_resource_keys={"s3"})
def ingest_data(context):
    df = pd.read_csv(DATA_PATH)
    key = "raw/sample_data.csv"
    context.resources.s3.put_object(Bucket=DATA_BUCKET, Key=key, Body=open(DATA_PATH, "rb").read())
    data_hash = hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()
    return df, data_hash, key

@op
def validate_data(context, inputs):
    df, _, _ = inputs
    if df.isnull().any().any() or len(df) == 0:
        raise ValueError("Validation failed")
    return inputs

@op
def train_model(context, inputs):
    df, data_hash, s3_key = inputs
    with mlflow.start_run():
        mlflow.log_param("dataset_s3_key", s3_key)
        mlflow.log_param("dataset_hash", data_hash)
        mlflow.log_metric("mock_accuracy", 0.95)

        import json, tempfile
        model = {"coef": [0.1, 0.2]}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
            json.dump(model, f)
            f.flush()
            mlflow.log_artifact(f.name, "model")

        model_uri = f"runs:/{mlflow.active_run().info.run_id}/model"
        registered = mlflow.register_model(model_uri, "CreditRiskModel")
        return registered.version

@op
def register_model(context, version):
    context.log.info(f"Model registered: v{version}")

@job(resource_defs={
    "s3": s3_resource.configured({
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "endpoint_url": os.getenv("MLFLOW_S3_ENDPOINT_URL"),
        "region_name": "us-east-1"
    })
})
def ml_training_pipeline():
    data = ingest_data()
    validated = validate_data(data)
    version = train_model(validated)
    register_model(version)

ml_training_schedule = ScheduleDefinition(
    job=ml_training_pipeline,
    cron_schedule="0 */6 * * *",
    name="ml_training_schedule"
)

@repository
def mlops_repo():
    return [ml_training_pipeline, ml_training_schedule]
