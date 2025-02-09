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

print_warning() {
    echo -e "${YELLOW}[!] $1${NC}"
}

print_error() {
    echo -e "${RED}[-] $1${NC}"
}

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root"
    exit 1
fi

# Create telugu-automation user and group
print_message "Creating telugu-automation user and group..."
if ! getent group telugu-automation > /dev/null; then
    groupadd telugu-automation
fi

if ! getent passwd telugu-automation > /dev/null; then
    useradd -r -g telugu-automation -d /opt/telugu-automation -s /bin/false telugu-automation
fi

# Update system and install dependencies
print_message "Updating system and installing dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv ffmpeg git chromium-browser

# Create required directories
print_message "Creating required directories..."
mkdir -p data/{audio,video,json,temp} logs config tn

# Set up virtual environment
print_message "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Copy configuration files
print_message "Setting up configuration..."
if [ ! -f "config/production.env" ]; then
    print_warning "Please create config/production.env with your settings"
    touch config/production.env
fi

if [ ! -f "config/serials_config.json" ]; then
    print_warning "Please create config/serials_config.json with your serial configurations"
    touch config/serials_config.json
fi

if [ ! -f "client_secrets.json" ]; then
    print_warning "Please place your client_secrets.json file in the project root"
    touch client_secrets.json
fi

# Set proper permissions
print_message "Setting permissions..."
chown -R telugu-automation:telugu-automation /opt/telugu-automation
chmod -R 750 /opt/telugu-automation
chmod -R 770 /opt/telugu-automation/{logs,data,tn}
chmod 640 /opt/telugu-automation/config/*.{env,json}
chmod 640 /opt/telugu-automation/client_secrets.json

# Install and enable systemd service
print_message "Installing systemd service..."
cp config/telugu-automation.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable telugu-automation.service

# Start the service
print_message "Starting telugu-automation service..."
systemctl start telugu-automation.service

# Check service status
if systemctl is-active --quiet telugu-automation.service; then
    print_message "Service is running successfully!"
else
    print_error "Service failed to start. Check logs with: journalctl -u telugu-automation.service"
fi

print_message "Setup complete! Please check the following:"
print_warning "1. Configure config/production.env with your settings"
print_warning "2. Place your client_secrets.json file in the project root"
print_warning "3. Configure config/serials_config.json with your serial details"
print_warning "4. Check logs at /opt/telugu-automation/logs/application.log"

print_message "You can manage the service with:"
echo "  systemctl start telugu-automation"
echo "  systemctl stop telugu-automation"
echo "  systemctl restart telugu-automation"
echo "  systemctl status telugu-automation"
echo "  journalctl -u telugu-automation -f" 