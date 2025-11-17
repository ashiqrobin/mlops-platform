#!/bin/bash

# Build All Script
# Complete rebuild of infrastructure and pipeline from scratch

echo "🚀 Building entire MLOps platform from scratch..."

# Stop all services
echo "⏹️  Stopping all services..."
docker-compose down

# Clean up old containers and images
echo "🧹 Cleaning up old containers and images..."
docker-compose rm -f
docker system prune -f

# Build everything from scratch
echo "🔨 Building all services..."
docker-compose build --no-cache

# Start all services
echo "🚀 Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 45

# Check service status
echo "✅ Service status:"
docker-compose ps

echo "🎉 Complete build finished!"
echo ""
echo "Services available at:"
echo "- Dagster UI: http://localhost:3000"
echo "- MLflow UI: http://localhost:5000"
echo "- MinIO Console: http://localhost:9001"
echo "- Grafana: http://localhost:3030"
echo "- Prometheus: http://localhost:9090"