#!/bin/bash

# Rebuild Infrastructure Script
# Use this when infrastructure changes (docker-compose.yml, .env, Dockerfiles)

echo "🔄 Rebuilding entire infrastructure..."

# Stop all services
echo "⏹️  Stopping all services..."
docker-compose down

# Remove old images to force rebuild
echo "🗑️  Removing old images..."
docker-compose build --no-cache

# Start all services
echo "🚀 Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Check service status
echo "✅ Service status:"
docker-compose ps

echo "🎉 Infrastructure rebuild complete!"
echo ""
echo "Services available at:"
echo "- Dagster UI: http://localhost:3000"
echo "- MLflow UI: http://localhost:5000"
echo "- MinIO Console: http://localhost:9001"
echo "- Grafana: http://localhost:3030"
echo "- Prometheus: http://localhost:9090"