import hashlib
import json
import os
import tempfile
import uuid

import boto3
import mlflow
import pandas as pd
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
RUN_ROLE = os.getenv("RUN_ROLE", "analyst")
DATA_BUCKET = os.getenv("DATA_BUCKET")
DATA_PATH = "/opt/dagster/app/data/sample_data.csv"
AUDIT_BUCKET = os.getenv("AUDIT_BUCKET") or DATA_BUCKET
AUDIT_LOG_PREFIX = os.getenv("AUDIT_LOG_PREFIX", "governance/audit/")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_ENDPOINT = os.getenv("MLFLOW_S3_ENDPOINT_URL")


def _role_set(raw_value: str | None, fallback: str) -> set[str]:
    source = raw_value if raw_value else fallback
    return {role.strip() for role in source.split(",") if role.strip()}


ALLOWED_STAGING_ROLES = _role_set(
    os.getenv("ALLOWED_STAGING_ROLES"), "ml_platform_engineer,ml_platform_admin"
)
ALLOWED_PROD_ROLES = _role_set(
    os.getenv("ALLOWED_PROD_ROLES"), "ml_platform_admin,security_officer"
)

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

_AUDIT_S3_CLIENT = boto3.client(
    "s3",
    region_name=AWS_REGION,
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def log_audit_event(step: str, status: str, **metadata) -> None:
    record = {
        "timestamp": pd.Timestamp.utcnow().isoformat(),
        "owner": RUN_OWNER,
        "role": RUN_ROLE,
        "environment": ENVIRONMENT,
        "step": step,
        "status": status,
        "details": json.dumps(metadata or {}, default=str),
    }
    if not AUDIT_BUCKET:
        raise RuntimeError("AUDIT_BUCKET must be configured for audit logging")
    safe_timestamp = (
        record["timestamp"].replace(":", "-").replace("+", "-").replace("T", "_")
    )
    key = f"{AUDIT_LOG_PREFIX}{safe_timestamp}-{step}-{uuid.uuid4().hex}.json"
    _AUDIT_S3_CLIENT.put_object(
        Bucket=AUDIT_BUCKET,
        Key=key,
        Body=json.dumps(record).encode("utf-8"),
        ContentType="application/json",
    )


def enforce_environment_guardrails(step: str) -> None:
    env = ENVIRONMENT.lower()
    allowed_roles: set[str] | None = None
    if env == "staging":
        allowed_roles = ALLOWED_STAGING_ROLES
    elif env == "prod":
        allowed_roles = ALLOWED_PROD_ROLES

    if allowed_roles and RUN_ROLE not in allowed_roles:
        log_audit_event(
            step,
            "blocked",
            reason="insufficient role permissions",
            required_roles=",".join(sorted(allowed_roles)),
        )
        raise PermissionError(
            f"Role '{RUN_ROLE}' is not authorized to run in {ENVIRONMENT}."
        )


@op(required_resource_keys={"s3"})
def ingest_data(context):
    df = pd.read_csv(DATA_PATH)
    key = "raw/sample_data.csv"
    context.resources.s3.put_object(
        Bucket=DATA_BUCKET, Key=key, Body=open(DATA_PATH, "rb").read()
    )
    data_hash = hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()
    log_audit_event(
        "ingest_data",
        "success",
        dataset_key=key,
        data_hash=data_hash,
        rows=len(df),
    )
    return df, data_hash, key


@op
def validate_data(context, inputs):
    df, _, _ = inputs
    if df.isnull().any().any() or len(df) == 0:
        log_audit_event(
            "validate_data",
            "failure",
            reason="nulls_detected_or_empty_dataset",
            rows=len(df),
        )
        raise ValueError("Validation failed")
    log_audit_event("validate_data", "success", rows=len(df))
    return inputs


@op
def train_model(context, inputs):
    df, data_hash, s3_key = inputs
    enforce_environment_guardrails("train_model")
    with mlflow.start_run(run_name=f"training-{ENVIRONMENT}"):
        mlflow.log_param("owner", RUN_OWNER)
        mlflow.log_param("environment", ENVIRONMENT)
        mlflow.log_param("dataset_s3_key", s3_key)
        mlflow.log_param("dataset_hash", data_hash)
        mlflow.log_param("row_count", len(df))
        mlflow.log_metric("mock_accuracy", 0.95)

        model = {"coef": [0.1, 0.2]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
            json.dump(model, f)
            f.flush()
            mlflow.log_artifact(f.name, "model")

        run_id = mlflow.active_run().info.run_id
        model_uri = f"runs:/{run_id}/model"
        registered = mlflow.register_model(model_uri, "CreditRiskModel")
        log_audit_event(
            "train_model",
            "success",
            run_id=run_id,
            model_version=registered.version,
            dataset_hash=data_hash,
        )
        return registered.version, data_hash


@op
def register_with_governance(context, inputs):
    version, data_hash = inputs
    client = MlflowClient()
    client.set_model_version_tag(
        "CreditRiskModel", version, "approval_state", "pending_staging"
    )
    client.set_model_version_tag("CreditRiskModel", version, "data_hash", data_hash)
    client.set_model_version_tag("CreditRiskModel", version, "audit_owner", RUN_OWNER)
    client.set_model_version_tag("CreditRiskModel", version, "audit_env", ENVIRONMENT)
    client.set_model_version_tag(
        "CreditRiskModel", version, "audit_timestamp", pd.Timestamp.now().isoformat()
    )

    if ENVIRONMENT != "dev":
        client.set_model_version_tag(
            "CreditRiskModel", version, "deployment_blocked", "true"
        )

    log_audit_event(
        "register_with_governance",
        "success",
        model_version=version,
        approval="pending_staging",
    )
    yield AssetMaterialization(
        asset_key=AssetKey(["models", "CreditRiskModel"]),
        metadata={"version": version, "approval": "pending_staging"},
    )
    context.log.info(f"Registered model version {version} with governance tags")
    yield Output(version)


@job(
    resource_defs={
        "s3": s3_resource.configured(
            {
                "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "endpoint_url": os.getenv("MLFLOW_S3_ENDPOINT_URL"),
                "region_name": "us-east-1",
            }
        )
    }
)
def ml_training_pipeline():
    data = ingest_data()
    validated = validate_data(data)
    model_info = train_model(validated)
    register_with_governance(model_info)


ml_training_schedule = ScheduleDefinition(
    job=ml_training_pipeline, cron_schedule="0 */6 * * *", name="ml_training_schedule"
)


@repository
def mlops_repo():
    return [ml_training_pipeline, ml_training_schedule]
