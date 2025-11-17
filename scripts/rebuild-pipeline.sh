#!/bin/bash

# Rebuild Pipeline Script
# Use this when pipeline code changes (Python files, dependencies)

echo "🔄 Rebuilding pipeline code..."

# Rebuild only Dagster container (where pipeline code lives)
echo "🔨 Rebuilding Dagster container..."
docker-compose build --no-cache dagster

# Restart Dagster service
echo "🚀 Restarting Dagster service..."
docker-compose up -d dagster

# Wait for Dagster to be ready
echo "⏳ Waiting for Dagster to start..."
sleep 15

# Check Dagster logs
echo "📋 Dagster logs:"
docker-compose logs --tail=10 dagster

echo "✅ Pipeline rebuild complete!"
echo ""
echo "Dagster UI: http://localhost:3000"