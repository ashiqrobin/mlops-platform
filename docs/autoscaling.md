# Autoscaling & Scaling Plan

This document captures how the local stack would evolve into an autoscaled production deployment on AWS.

## Compute Layers

1. **Dagster Orchestrator**
   - Run Dagster on ECS/Fargate behind an Application Load Balancer (ALB).
   - Configure `aws_appautoscaling_target` for the ECS service with step-scaling policies (CPU and queue depth).
   - Use CloudWatch Metrics:
     - `ECSServiceAverageCPUUtilization` > 65% for 5 minutes ⇒ scale out by +1 task.
     - Dagster run queue depth (`dagster_runs_in_queue` via custom metric) > 10 for 5 minutes ⇒ scale out by +1 task.
   - Minimum 1 task (dev), maximum 5 tasks (prod).

2. **MLflow Tracking Server**
   - Deploy on ECS with Fargate or on EC2 ASG.
   - Auto scale based on `ApplicationELBRequestCountPerTarget` and CPU.
   - When using EC2, attach an Auto Scaling Group (ASG) with target tracking at 60% CPU.

3. **Training/Inference Jobs**
   - Triggered via Dagster to run on AWS Batch / ECS RunTask.
   - Configure Batch compute environments with managed scaling (desired vCPUs target 80%).
   - Future: integrate with EKS Managed Node Groups for GPU workloads; use Cluster Autoscaler + Karpenter to bring nodes on demand.

## Storage Layers

1. **Postgres (metadata)**
   - Use Amazon Aurora Serverless v2 with auto-scaling capacity units based on CPU/connection limits.
2. **MinIO → Amazon S3**
   - Replace MinIO with S3; use S3 Intelligent-Tiering for cost-optimized scaling.

## Network & Multi-Account Strategy

- VPC per environment (dev/staging/prod) with shared services account for observability.
- Private subnets for ECS tasks; expose Dagster/MLflow via ALB + AWS WAF.
- Use AWS Transit Gateway or VPC Peering for cross-account data access.

## Terraform Stubs to Extend

The existing `infrastructure/terraform/main.tf` can be extended with:

```hcl
resource "aws_ecs_service" "dagster" {
  name            = "${local.project}-dagster"
  cluster         = aws_ecs_cluster.mlops.id
  desired_count   = 1
  launch_type     = "FARGATE"
  task_definition = aws_ecs_task_definition.dagster.arn
  network_configuration {
    subnets         = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    assign_public_ip = true
    security_groups = [aws_security_group.dagster.id]
  }
}

resource "aws_appautoscaling_target" "dagster" {
  max_capacity       = 5
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.mlops.name}/${aws_ecs_service.dagster.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}
```

Add scaling policies for CPU and SQS queue depth (if Dagster run requests are delivered via SQS).

## Monitoring & Alerting

- Use Prometheus in AWS (Amazon Managed Service for Prometheus) or CloudWatch Container Insights.
- Scale Prometheus scrapers via HPA when running on EKS.
- Alert examples:
  - Dagster queue depth > threshold for 10 minutes.
  - MLflow p95 latency > 2s.
  - Drift monitor missing metrics for 15 minutes (already defined locally).

## CI/CD & Rollout

- Bake Docker images in CI, push to ECR.
- Terraform deploys infrastructure per environment.
- Use blue/green ECS deployments via CodeDeploy for Dagster/MLflow to minimize downtime.

This plan satisfies the “design for autoscaling” requirement by outlining concrete AWS services, scaling signals, and Terraform constructs to implement them.
