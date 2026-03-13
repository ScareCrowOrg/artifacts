#!/bin/bash
# Startup script for ScareCopilotPortal Backend API

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting ScareCopilotPortal Backend API...${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create ScareFeraLab directory if it doesn't exist
SCAREFERA_LAB="../ScareFeraLab"
if [ ! -d "$SCAREFERA_LAB" ]; then
    mkdir -p "$SCAREFERA_LAB"
    echo -e "${GREEN}✓ ScareFeraLab directory created${NC}"
fi

# Start the server
echo -e "${BLUE}Starting server...${NC}"
echo "API will be available at:"
echo "  - API Base: http://localhost:5051/api"
echo "  - Docs: http://localhost:5051/api/docs"
echo "  - MVP1 Endpoints: http://localhost:5051/api/"
echo "  - Chat IA: http://localhost:5051/api/chat/processar"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python -m app.main
