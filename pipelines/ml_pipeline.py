import os
import hashlib
import pandas as pd
import mlflow
from mlflow.tracking import MlflowClient
from dagster import (
    AssetKey,
    AssetMaterialization,
    Output,
    ScheduleDefinition,
    job,
    op,
    repository,
)
from dagster_aws.s3 import s3_resource

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
RUN_OWNER = os.getenv("RUN_OWNER", "unknown")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
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
    with mlflow.start_run(run_name=f"training-{ENVIRONMENT}"):
        mlflow.log_param("owner", RUN_OWNER)
        mlflow.log_param("environment", ENVIRONMENT)
        mlflow.log_param("dataset_s3_key", s3_key)
        mlflow.log_param("dataset_hash", data_hash)
        mlflow.log_param("row_count", len(df))
        mlflow.log_metric("mock_accuracy", 0.95)

        import json
        import tempfile

        model = {"coef": [0.1, 0.2]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
            json.dump(model, f)
            f.flush()
            mlflow.log_artifact(f.name, "model")

        model_uri = f"runs:/{mlflow.active_run().info.run_id}/model"
        registered = mlflow.register_model(model_uri, "CreditRiskModel")
        return registered.version, data_hash

@op
def register_with_governance(context, inputs):
    version, data_hash = inputs
    client = MlflowClient()
    client.set_model_version_tag("CreditRiskModel", version, "approval_state", "pending_staging")
    client.set_model_version_tag("CreditRiskModel", version, "data_hash", data_hash)
    client.set_model_version_tag("CreditRiskModel", version, "audit_owner", RUN_OWNER)
    client.set_model_version_tag("CreditRiskModel", version, "audit_env", ENVIRONMENT)
    client.set_model_version_tag("CreditRiskModel", version, "audit_timestamp", pd.Timestamp.now().isoformat())

    if ENVIRONMENT != "dev":
        client.set_model_version_tag("CreditRiskModel", version, "deployment_blocked", "true")

    yield AssetMaterialization(
        asset_key=AssetKey(["models", "CreditRiskModel"]),
        metadata={"version": version, "approval": "pending_staging"},
    )
    context.log.info(f"Registered model version {version} with governance tags")
    yield Output(version)

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
    model_info = train_model(validated)
    register_with_governance(model_info)

ml_training_schedule = ScheduleDefinition(
    job=ml_training_pipeline,
    cron_schedule="0 */6 * * *",
    name="ml_training_schedule"
)

@repository
def mlops_repo():
    return [ml_training_pipeline, ml_training_schedule]
