#!/bin/bash

# Define colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}Starting ORA Universal Bot...${NC}"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Running Setup Wizard..."
    python3 setup_wizard.py
    exit 0
fi

# Activate venv
source venv/bin/activate

# Check for .env
if [ ! -f ".env" ]; then
    echo "Configuration file .env not found!"
    echo "Please run 'python3 setup_wizard.py' to generate it."
    exit 1
fi

echo -e "${GREEN}ORA is Online. Press Ctrl+C to stop.${NC}"

# Run Bot
python -m src.bot
