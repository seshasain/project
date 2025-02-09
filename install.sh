#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print colored messages
print_message() {
    echo -e "${GREEN}[+] $1${NC}"
}

print_error() {
    echo -e "${RED}[-] $1${NC}"
}

# Check if running on Ubuntu
if ! grep -q 'Ubuntu' /etc/os-release; then
    print_error "This script is designed to run on Ubuntu only"
    exit 1
fi

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use: sudo ./install.sh)"
    exit 1
fi

# Install git if not present
if ! command -v git &> /dev/null; then
    print_message "Installing git..."
    apt-get update
    apt-get install -y git
fi

# Clone the repository
REPO_URL="https://github.com/seshasain/project.git"
TARGET_DIR="/opt/telugu-automation"

if [ -d "$TARGET_DIR" ]; then
    print_message "Directory already exists. Updating..."
    cd "$TARGET_DIR"
    git pull
else
    print_message "Cloning repository..."
    git clone "$REPO_URL" "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

# Run the setup script
print_message "Running setup script..."
bash setup_server.sh

print_message "Installation complete! Check the messages above for any additional steps needed." 