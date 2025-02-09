"""
Utility for analyzing health metrics and generating reports.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class HealthAnalyzer:
    """Analyzes health metrics and generates reports."""
    
    def __init__(self, metrics_file: str = 'logs/health_metrics.json'):
        """Initialize the health analyzer.
        
        Args:
            metrics_file: Path to the health metrics JSON file
        """
        self.metrics_file = metrics_file
        
    def _load_metrics(self) -> List[Dict]:
        """Load metrics from file."""
        try:
            if not os.path.exists(self.metrics_file):
                return []
                
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error loading metrics: {str(e)}")
            return []
    
    def _parse_timestamp(self, timestamp: str) -> datetime:
        """Parse ISO format timestamp."""
        return datetime.fromisoformat(timestamp)
    
    def get_recent_metrics(self, hours: int = 24) -> List[Dict]:
        """Get metrics from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of metric dictionaries
        """
        metrics = self._load_metrics()
        if not metrics:
            return []
            
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            m for m in metrics
            if self._parse_timestamp(m['timestamp']) > cutoff
        ]
    
    def calculate_statistics(self, metrics: List[Dict]) -> Dict:
        """Calculate statistics from metrics.
        
        Args:
            metrics: List of metric dictionaries
            
        Returns:
            Dictionary of calculated statistics
        """
        if not metrics:
            return {}
            
        # Initialize accumulators
        cpu_values = []
        memory_values = []
        disk_values = []
        failed_checks = []
        youtube_api_failures = 0
        upload_frequency_failures = 0
        
        # Process each metric
        for metric in metrics:
            # Process values
            if 'process' in metric:
                cpu_values.append(metric['process'].get('cpu_percent', 0))
                memory_values.append(metric['process'].get('memory_percent', 0))
                
            if 'disk' in metric:
                disk_values.append(metric['disk'].get('percent_used', 0))
            
            # Count failures
            if not metric.get('youtube_api_healthy', True):
                youtube_api_failures += 1
                
            if not metric.get('upload_frequency_healthy', True):
                upload_frequency_failures += 1
                
            failed_checks.extend(metric.get('failed_checks', []))
        
        # Calculate statistics
        stats = {
            'period_start': metrics[0]['timestamp'],
            'period_end': metrics[-1]['timestamp'],
            'total_checks': len(metrics),
            'cpu_usage': {
                'min': min(cpu_values) if cpu_values else 0,
                'max': max(cpu_values) if cpu_values else 0,
                'avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0
            },
            'memory_usage': {
                'min': min(memory_values) if memory_values else 0,
                'max': max(memory_values) if memory_values else 0,
                'avg': sum(memory_values) / len(memory_values) if memory_values else 0
            },
            'disk_usage': {
                'min': min(disk_values) if disk_values else 0,
                'max': max(disk_values) if disk_values else 0,
                'avg': sum(disk_values) / len(disk_values) if disk_values else 0
            },
            'failures': {
                'youtube_api': youtube_api_failures,
                'upload_frequency': upload_frequency_failures,
                'total_failed_checks': len(failed_checks)
            }
        }
        
        # Calculate failure rates
        total_checks = len(metrics)
        if total_checks > 0:
            stats['failure_rates'] = {
                'youtube_api': youtube_api_failures / total_checks * 100,
                'upload_frequency': upload_frequency_failures / total_checks * 100
            }
        
        return stats
    
    def generate_report(self, hours: int = 24) -> str:
        """Generate a health report for the specified period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Formatted report string
        """
        metrics = self.get_recent_metrics(hours)
        if not metrics:
            return "No health metrics available for the specified period."
            
        stats = self.calculate_statistics(metrics)
        
        # Format the report
        report = [
            f"Health Report for the Last {hours} Hours",
            f"Period: {stats['period_start']} to {stats['period_end']}",
            f"Total Health Checks: {stats['total_checks']}",
            "",
            "Resource Usage:",
            f"  CPU: {stats['cpu_usage']['min']:.1f}% to {stats['cpu_usage']['max']:.1f}% (avg: {stats['cpu_usage']['avg']:.1f}%)",
            f"  Memory: {stats['memory_usage']['min']:.1f}% to {stats['memory_usage']['max']:.1f}% (avg: {stats['memory_usage']['avg']:.1f}%)",
            f"  Disk: {stats['disk_usage']['min']:.1f}% to {stats['disk_usage']['max']:.1f}% (avg: {stats['disk_usage']['avg']:.1f}%)",
            "",
            "Failures:",
            f"  YouTube API: {stats['failures']['youtube_api']} ({stats['failure_rates']['youtube_api']:.1f}%)",
            f"  Upload Frequency: {stats['failures']['upload_frequency']} ({stats['failure_rates']['upload_frequency']:.1f}%)",
            f"  Total Failed Checks: {stats['failures']['total_failed_checks']}"
        ]
        
        return "\n".join(report)
    
    def save_report(self, report: str, output_file: str) -> None:
        """Save the report to a file.
        
        Args:
            report: Report string to save
            output_file: Path to save the report
        """
        try:
            # Add timestamp to filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base, ext = os.path.splitext(output_file)
            timestamped_file = f"{base}_{timestamp}{ext}"
            
            os.makedirs(os.path.dirname(timestamped_file), exist_ok=True)
            with open(timestamped_file, 'w') as f:
                f.write(report)
                
            logger.info(f"Health report saved to {timestamped_file}")
            
        except Exception as e:
            logger.error(f"Error saving report: {str(e)}")

def analyze_health(hours: int = 24, 
                  metrics_file: str = 'logs/health_metrics.json',
                  output_file: Optional[str] = None) -> str:
    """Analyze health metrics and generate a report.
    
    Args:
        hours: Number of hours to analyze
        metrics_file: Path to the metrics file
        output_file: Optional path to save the report
        
    Returns:
        Generated report string
    """
    analyzer = HealthAnalyzer(metrics_file)
    report = analyzer.generate_report(hours)
    
    if output_file:
        analyzer.save_report(report, output_file)
    
    return report

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Generate and save a report for the last 24 hours
    report = analyze_health(
        hours=24,
        output_file='logs/health_report.txt'
    )
    print(report) 