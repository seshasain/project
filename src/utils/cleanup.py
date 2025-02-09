"""
Cleanup utility for managing temporary files and disk space.
"""

import os
import time
import shutil
import logging
import glob
from datetime import datetime, timedelta
from typing import List, Tuple

logger = logging.getLogger(__name__)

class CleanupManager:
    """Manages cleanup of temporary files and old logs."""
    
    def __init__(self, 
                 temp_dir: str = 'data/temp',
                 video_dir: str = 'data/video',
                 audio_dir: str = 'data/audio',
                 logs_dir: str = 'logs',
                 max_age_days: int = 7,
                 min_free_space_gb: float = 10.0,
                 report_retention_days: int = 30):
        """Initialize the cleanup manager.
        
        Args:
            temp_dir: Directory containing temporary files
            video_dir: Directory containing generated videos
            audio_dir: Directory containing audio files
            logs_dir: Directory containing log files
            max_age_days: Maximum age of files to keep
            min_free_space_gb: Minimum free space to maintain in GB
            report_retention_days: Days to keep health reports
        """
        self.temp_dir = temp_dir
        self.video_dir = video_dir
        self.audio_dir = audio_dir
        self.logs_dir = logs_dir
        self.max_age_days = max_age_days
        self.min_free_space_gb = min_free_space_gb
        self.report_retention_days = report_retention_days
    
    def _get_old_files(self, directory: str, max_age_days: int) -> List[Tuple[str, float]]:
        """Get list of files older than max_age_days.
        
        Args:
            directory: Directory to check
            max_age_days: Maximum age of files to keep
            
        Returns:
            List of tuples containing file path and size in bytes
        """
        old_files = []
        cutoff = datetime.now() - timedelta(days=max_age_days)
        
        if not os.path.exists(directory):
            return old_files
            
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if mtime < cutoff:
                        size = os.path.getsize(file_path)
                        old_files.append((file_path, size))
                except OSError as e:
                    logger.warning(f"Error checking file {file_path}: {str(e)}")
                    
        return old_files
    
    def _get_free_space_gb(self) -> float:
        """Get free space in GB."""
        usage = shutil.disk_usage('/')
        return usage.free / (1024 * 1024 * 1024)
    
    def _delete_files(self, files: List[Tuple[str, float]]) -> float:
        """Delete files and return total space freed.
        
        Args:
            files: List of tuples containing file path and size
            
        Returns:
            Total space freed in bytes
        """
        total_freed = 0
        for file_path, size in files:
            try:
                os.remove(file_path)
                total_freed += size
                logger.info(f"Deleted {file_path} ({size / 1024 / 1024:.2f} MB)")
            except OSError as e:
                logger.warning(f"Error deleting {file_path}: {str(e)}")
                
        return total_freed
    
    def cleanup_old_files(self) -> None:
        """Clean up files older than max_age_days."""
        directories = [
            self.temp_dir,
            self.video_dir,
            self.audio_dir,
            self.logs_dir
        ]
        
        total_freed = 0
        for directory in directories:
            old_files = self._get_old_files(directory, self.max_age_days)
            if old_files:
                freed = self._delete_files(old_files)
                total_freed += freed
                
        if total_freed > 0:
            logger.info(
                f"Cleanup completed. Freed {total_freed / 1024 / 1024:.2f} MB "
                f"of space"
            )
    
    def cleanup_old_reports(self) -> None:
        """Clean up old health reports."""
        try:
            report_pattern = os.path.join(self.logs_dir, 'health_report_*.txt')
            cutoff = datetime.now() - timedelta(days=self.report_retention_days)
            
            total_freed = 0
            for report_file in glob.glob(report_pattern):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(report_file))
                    if mtime < cutoff:
                        size = os.path.getsize(report_file)
                        os.remove(report_file)
                        total_freed += size
                        logger.info(
                            f"Deleted old report {report_file} "
                            f"({size / 1024:.2f} KB)"
                        )
                except OSError as e:
                    logger.warning(
                        f"Error processing report {report_file}: {str(e)}"
                    )
            
            if total_freed > 0:
                logger.info(
                    f"Report cleanup completed. "
                    f"Freed {total_freed / 1024:.2f} KB"
                )
                
        except Exception as e:
            logger.error(f"Error cleaning up reports: {str(e)}")
    
    def ensure_free_space(self) -> None:
        """Ensure minimum free space is available."""
        free_space = self._get_free_space_gb()
        if free_space < self.min_free_space_gb:
            logger.warning(
                f"Low disk space: {free_space:.2f}GB free. "
                f"Need {self.min_free_space_gb}GB"
            )
            
            # Get all files sorted by age (oldest first)
            all_files = []
            for directory in [self.temp_dir, self.video_dir, self.audio_dir]:
                if os.path.exists(directory):
                    for root, _, files in os.walk(directory):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                mtime = os.path.getmtime(file_path)
                                size = os.path.getsize(file_path)
                                all_files.append((file_path, size, mtime))
                            except OSError:
                                continue
            
            # Sort by modification time (oldest first)
            all_files.sort(key=lambda x: x[2])
            
            # Delete files until we have enough space
            files_to_delete = []
            for file_path, size, _ in all_files:
                files_to_delete.append((file_path, size))
                free_space = self._get_free_space_gb()
                if free_space >= self.min_free_space_gb:
                    break
            
            if files_to_delete:
                freed = self._delete_files(files_to_delete)
                logger.info(
                    f"Emergency cleanup completed. "
                    f"Freed {freed / 1024 / 1024:.2f} MB of space"
                )
    
    def run(self) -> None:
        """Run all cleanup operations."""
        try:
            logger.info("Starting cleanup process...")
            self.cleanup_old_files()
            self.cleanup_old_reports()
            self.ensure_free_space()
            logger.info("Cleanup process completed successfully")
            
        except Exception as e:
            logger.error(f"Cleanup process failed: {str(e)}")

def cleanup() -> None:
    """Run cleanup operations."""
    report_retention_days = int(os.getenv('HEALTH_REPORT_RETENTION_DAYS', '30'))
    manager = CleanupManager(report_retention_days=report_retention_days)
    manager.run() 