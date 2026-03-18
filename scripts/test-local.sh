#!/bin/bash
set -e

echo "🧪 Running Local Tests..."
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Unit Tests
echo -e "${BLUE}1. Running Unit Tests${NC}"
pytest tests/test_agent_unit.py tests/test_orchestrator.py -v --tb=short

echo ""
echo -e "${GREEN}✓ Unit tests passed${NC}"
echo ""

# 2. Test with coverage
echo -e "${BLUE}2. Running Tests with Coverage${NC}"
pytest tests/test_agent_unit.py tests/test_orchestrator.py --cov=lambda --cov-report=term-missing --cov-report=html

echo ""
echo -e "${GREEN}✓ Coverage report generated in htmlcov/index.html${NC}"
echo ""

# 3. Type checking (optional)
if command -v mypy &> /dev/null; then
    echo -e "${BLUE}3. Running Type Checks${NC}"
    mypy lambda/ --ignore-missing-imports || true
    echo ""
fi

echo -e "${GREEN}✅ All local tests completed!${NC}"
