"""
Main scheduler for the Telugu Serial Automation service.
"""

import os
import time
import schedule
import logging
from datetime import datetime
from utils.cleanup import cleanup
from utils.system_check import verify_system
from utils.health_check import HealthChecker
from utils.analyze_health import analyze_health

logger = logging.getLogger(__name__)

class SerialScheduler:
    """Manages scheduling of serial episode processing and uploads."""
    
    def __init__(self):
        """Initialize the scheduler."""
        self.check_interval = int(os.getenv('CHECK_INTERVAL_MINUTES', '10'))
        self.cleanup_interval = int(os.getenv('CLEANUP_INTERVAL_HOURS', '6'))
        self.health_check_interval = int(os.getenv('HEALTH_CHECK_MINUTES', '5'))
        self.report_interval = int(os.getenv('HEALTH_REPORT_HOURS', '24'))
        
        # Initialize health checker
        self.health_checker = HealthChecker()
        
        # Schedule regular tasks
        schedule.every(self.check_interval).minutes.do(self.process_episodes)
        schedule.every(self.cleanup_interval).hours.do(cleanup)
        schedule.every(self.health_check_interval).minutes.do(self.check_health)
        schedule.every(self.report_interval).hours.do(self.generate_health_report)
        
        # Schedule system checks daily
        schedule.every().day.at("00:00").do(verify_system)
    
    def process_episodes(self):
        """Process and upload new episodes."""
        try:
            logger.info("Checking for new episodes...")
            # Your existing episode processing logic here
            
            # Update last upload time if successful
            self.health_checker.update_last_upload_time()
            
        except Exception as e:
            logger.error(f"Error processing episodes: {str(e)}")
    
    def check_health(self):
        """Run health checks."""
        try:
            is_healthy, metrics = self.health_checker.run_health_check()
            
            if not is_healthy:
                logger.warning(
                    "Health check failed. Issues: " + 
                    ", ".join(metrics.get('failed_checks', []))
                )
            
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
    
    def generate_health_report(self):
        """Generate and save health report."""
        try:
            logger.info("Generating health report...")
            report = analyze_health(
                hours=self.report_interval,
                output_file='logs/health_report.txt'
            )
            logger.info("Health report generated successfully")
            
        except Exception as e:
            logger.error(f"Error generating health report: {str(e)}")
    
    def start(self):
        """Start the scheduler."""
        logger.info(
            f"Starting scheduler (check interval: {self.check_interval} minutes, "
            f"cleanup interval: {self.cleanup_interval} hours, "
            f"health check interval: {self.health_check_interval} minutes, "
            f"report interval: {self.report_interval} hours)"
        )
        
        # Generate initial health report
        self.generate_health_report()
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Scheduler error: {str(e)}")
                time.sleep(300)  # Wait 5 minutes on error
                
if __name__ == "__main__":
    scheduler = SerialScheduler()
    scheduler.start() 