#!/bin/bash

# Cleanup script for Serverless AI Pack project
# Removes temporary files, build artifacts, and cached data
#
# NOTE: This script does NOT destroy AWS infrastructure.
#       To destroy AWS resources, use: ./scripts/destroy-infrastructure.sh

set -e

echo "🧹 Starting cleanup..."

# Python cache and bytecode
echo "  → Removing Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type f -name "*.pyd" -delete 2>/dev/null || true

# Test artifacts
echo "  → Removing test artifacts..."
rm -rf .pytest_cache/ 2>/dev/null || true
rm -f .coverage 2>/dev/null || true
rm -rf htmlcov/ 2>/dev/null || true
rm -rf .tox/ 2>/dev/null || true
rm -rf .nox/ 2>/dev/null || true

# CDK build artifacts
echo "  → Removing CDK build artifacts..."
rm -rf cdk/cdk.out/ 2>/dev/null || true
rm -rf .cdk.staging/ 2>/dev/null || true
rm -f cdk.context.json 2>/dev/null || true

# OS-specific files
echo "  → Removing OS-specific files..."
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "Thumbs.db" -delete 2>/dev/null || true
find . -name "._*" -delete 2>/dev/null || true

# Temporary files
echo "  → Removing temporary files..."
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.log" -delete 2>/dev/null || true
find . -name "*.bak" -delete 2>/dev/null || true
find . -name "*.backup" -delete 2>/dev/null || true
find . -name "*~" -delete 2>/dev/null || true

# Architecture diagram temporary files
echo "  → Removing diagram temporary files..."
find . -name "*.drawio.dtmp" -delete 2>/dev/null || true
find . -name "*.drawio.bkp" -delete 2>/dev/null || true
find . -name "*.drawio~" -delete 2>/dev/null || true

# Docker artifacts (optional - uncomment if needed)
# echo "  → Removing Docker artifacts..."
# docker system prune -f 2>/dev/null || true

# Node modules (if any from CDK)
if [ -d "node_modules" ]; then
    echo "  → Removing node_modules..."
    rm -rf node_modules/
fi

# Egg info
echo "  → Removing egg-info directories..."
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

echo "✅ Cleanup complete!"
echo ""
echo "Note: Virtual environment (venv/) was NOT removed."
echo "      To remove it, run: rm -rf venv/"
