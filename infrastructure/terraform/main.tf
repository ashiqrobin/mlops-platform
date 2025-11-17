terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  description = "AWS region to deploy the MLOps platform"
  type        = string
  default     = "us-east-1"
}

locals {
  project = "mlops-platform"
}

# Networking ---------------------------------------------------------------

resource "aws_vpc" "mlops" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "${local.project}-vpc" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.mlops.id
  cidr_block              = "10.20.1.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true
  tags = { Name = "${local.project}-public-a" }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.mlops.id
  cidr_block              = "10.20.2.0/24"
  availability_zone       = "${var.region}b"
  map_public_ip_on_launch = true
  tags = { Name = "${local.project}-public-b" }
}

# Storage & metadata ------------------------------------------------------

resource "aws_s3_bucket" "artifact" {
  bucket = "${local.project}-artifacts"
  acl    = "private"
}

resource "aws_s3_bucket" "data" {
  bucket = "${local.project}-data"
  acl    = "private"
}

resource "aws_rds_cluster" "mlflow" {
  cluster_identifier   = "${local.project}-mlflow"
  engine               = "aurora-postgresql"
  master_username      = "mlops_user"
  master_password      = "ChangeMe123!"
  skip_final_snapshot  = true
  vpc_security_group_ids = []  # fill with SG once defined
}

# IAM / compute placeholders ---------------------------------------------

resource "aws_iam_role" "dagster" {
  name = "${local.project}-dagster-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "dagster_policy" {
  role   = aws_iam_role.dagster.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:*"],
        Resource = [aws_s3_bucket.artifact.arn, "${aws_s3_bucket.artifact.arn}/*", aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["rds:*"],
        Resource = "*"
      }
    ]
  })
}

resource "aws_ecs_cluster" "mlops" {
  name = "${local.project}-ecs"
}

resource "aws_cloudwatch_log_group" "dagster" {
  name              = "/aws/mlops/${local.project}/dagster"
  retention_in_days = 7
}

output "vpc_id" {
  value = aws_vpc.mlops.id
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifact.bucket
}

output "data_bucket" {
  value = aws_s3_bucket.data.bucket
}
