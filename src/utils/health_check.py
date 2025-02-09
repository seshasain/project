"""
Health check utility to monitor application status.
"""

import os
import json
import psutil
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class HealthChecker:
    """Monitors application health and performance."""
    
    def __init__(self):
        """Initialize the health checker."""
        self.process = psutil.Process()
        self.start_time = datetime.now()
        self.last_upload_time: Optional[datetime] = None
        self.failed_checks: List[str] = []
        
        # Load configuration
        self.max_cpu_percent = float(os.getenv('MAX_CPU_PERCENT', '80'))
        self.max_memory_percent = float(os.getenv('MAX_MEMORY_PERCENT', '80'))
        self.max_disk_percent = float(os.getenv('MAX_DISK_PERCENT', '90'))
        self.max_open_files = int(os.getenv('MAX_OPEN_FILES', '1000'))
    
    def check_process_health(self) -> Tuple[bool, Dict]:
        """Check process CPU, memory, and file descriptor usage."""
        try:
            cpu_percent = self.process.cpu_percent(interval=1)
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            open_files = len(self.process.open_files())
            
            metrics = {
                'cpu_percent': cpu_percent,
                'memory_rss_mb': memory_info.rss / 1024 / 1024,
                'memory_percent': memory_percent,
                'open_files': open_files,
                'uptime_hours': (datetime.now() - self.start_time).total_seconds() / 3600
            }
            
            # Check for concerning values
            is_healthy = True
            if cpu_percent > self.max_cpu_percent:
                self.failed_checks.append(
                    f"High CPU usage: {cpu_percent}% "
                    f"(max: {self.max_cpu_percent}%)"
                )
                is_healthy = False
                
            if memory_percent > self.max_memory_percent:
                self.failed_checks.append(
                    f"High memory usage: {memory_percent}% "
                    f"(max: {self.max_memory_percent}%)"
                )
                is_healthy = False
                
            if open_files > self.max_open_files:
                self.failed_checks.append(
                    f"High number of open files: {open_files} "
                    f"(max: {self.max_open_files})"
                )
                is_healthy = False
            
            return is_healthy, metrics
            
        except Exception as e:
            self.failed_checks.append(f"Process health check failed: {str(e)}")
            return False, {}
    
    def check_youtube_api(self) -> bool:
        """Check YouTube API connectivity."""
        try:
            # Simple test request to YouTube Data API
            response = requests.get(
                'https://www.googleapis.com/youtube/v3/channels',
                params={'part': 'id', 'mine': 'true'},
                headers={'Authorization': f'Bearer {self._get_access_token()}'}
            )
            
            if response.status_code == 200:
                return True
            else:
                self.failed_checks.append(
                    f"YouTube API check failed: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.failed_checks.append(f"YouTube API check failed: {str(e)}")
            return False
    
    def _get_access_token(self) -> str:
        """Get current access token from pickle file."""
        import pickle
        token_file = os.getenv('YOUTUBE_TOKEN_FILE', 'token.pickle')
        
        try:
            with open(token_file, 'rb') as f:
                credentials = pickle.load(f)
                if credentials and not credentials.expired:
                    return credentials.token
                    
        except Exception as e:
            logger.error(f"Error reading token file: {str(e)}")
            
        return ''
    
    def check_disk_usage(self) -> Tuple[bool, Dict]:
        """Check disk space usage."""
        try:
            usage = psutil.disk_usage('/')
            metrics = {
                'total_gb': usage.total / (1024**3),
                'used_gb': usage.used / (1024**3),
                'free_gb': usage.free / (1024**3),
                'percent_used': usage.percent
            }
            
            is_healthy = True
            if usage.percent > self.max_disk_percent:
                self.failed_checks.append(
                    f"Critical disk usage: {usage.percent}% used "
                    f"(max: {self.max_disk_percent}%)"
                )
                is_healthy = False
                
            return is_healthy, metrics
            
        except Exception as e:
            self.failed_checks.append(f"Disk usage check failed: {str(e)}")
            return False, {}
    
    def check_upload_frequency(self) -> bool:
        """Check if uploads are happening at expected frequency."""
        if not self.last_upload_time:
            return True
            
        hours_since_last_upload = (
            datetime.now() - self.last_upload_time
        ).total_seconds() / 3600
        
        expected_interval = float(os.getenv('CHECK_INTERVAL_MINUTES', '10')) / 60
        max_allowed_gap = expected_interval * 3  # Allow for some delays
        
        if hours_since_last_upload > max_allowed_gap:
            self.failed_checks.append(
                f"No uploads for {hours_since_last_upload:.1f} hours "
                f"(max: {max_allowed_gap:.1f} hours)"
            )
            return False
            
        return True
    
    def update_last_upload_time(self) -> None:
        """Update the timestamp of the last successful upload."""
        self.last_upload_time = datetime.now()
    
    def run_health_check(self) -> Tuple[bool, Dict]:
        """Run all health checks.
        
        Returns:
            Tuple of (is_healthy, metrics_dict)
        """
        self.failed_checks = []  # Reset failed checks
        
        # Run all checks
        process_healthy, process_metrics = self.check_process_health()
        disk_healthy, disk_metrics = self.check_disk_usage()
        youtube_healthy = self.check_youtube_api()
        upload_healthy = self.check_upload_frequency()
        
        # Combine all metrics
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'process': process_metrics,
            'disk': disk_metrics,
            'youtube_api_healthy': youtube_healthy,
            'upload_frequency_healthy': upload_healthy,
            'failed_checks': self.failed_checks
        }
        
        # Write metrics to file
        self._write_metrics(metrics)
        
        # Overall health status
        is_healthy = all([
            process_healthy,
            disk_healthy,
            youtube_healthy,
            upload_healthy
        ])
        
        return is_healthy, metrics
    
    def _write_metrics(self, metrics: Dict) -> None:
        """Write metrics to a JSON file."""
        try:
            metrics_file = 'logs/health_metrics.json'
            os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
            
            # Keep last 100 metrics
            existing_metrics = []
            if os.path.exists(metrics_file):
                with open(metrics_file, 'r') as f:
                    existing_metrics = json.load(f)
                    
            existing_metrics.append(metrics)
            if len(existing_metrics) > 100:
                existing_metrics = existing_metrics[-100:]
                
            with open(metrics_file, 'w') as f:
                json.dump(existing_metrics, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error writing metrics: {str(e)}")

def check_health() -> Tuple[bool, Dict]:
    """Run health check and return results."""
    checker = HealthChecker()
    return checker.run_health_check() 