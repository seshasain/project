"""
Main entry point for the Telugu Serial Automation application.
Performs system checks and starts the scheduler.
"""

import os
import sys
import schedule
import time
import time
import logging
import structlog
from dotenv import load_dotenv
from utils.system_check import verify_system
from scheduler.main_scheduler import SerialProcessor

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/application.log')
    ]
)

logger = structlog.get_logger()

def main():
    """Main entry point for the application."""
    try:
        # Load environment variables
        load_dotenv('config/production.env')
        
        # Verify system requirements
        logger.info("Performing system checks...")
        if not verify_system():
            logger.error("System checks failed. Please fix the issues and try again.")
            return 1
            
        # Initialize and start the scheduler
        logger.info("Starting Telugu Serial Automation...")
        processor = SerialProcessor()
        processor.check_serials()
        while True:
            time.sleep(60)  # Sleep for 1 minute
            processor.check_serials()
        
        return 0
        
    except Exception as e:
        logger.error(f"Application failed to start: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 