#!/bin/bash

# Decommission Infrastructure Script
# Completely tear down the MLOps platform and clean up resources

echo "🛑 Decommissioning MLOps platform..."

# Stop all services
echo "⏹️  Stopping all services..."
docker-compose down

# Remove containers
echo "🗑️  Removing containers..."
docker-compose rm -f

# Remove images
echo "🗑️  Removing images..."
docker-compose down --rmi all

# Remove volumes (WARNING: This deletes all data!)
echo "⚠️  Removing volumes (all data will be lost)..."
docker-compose down --volumes

# Clean up orphaned containers and networks
echo "🧹 Cleaning up orphaned resources..."
docker system prune -f
docker volume prune -f
docker network prune -f

echo "✅ Decommission complete!"
echo ""
echo "All services stopped and resources cleaned up."
echo "To rebuild, run: ./scripts/build-all.sh"