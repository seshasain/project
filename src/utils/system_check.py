"""
System Check Utility

Verifies system requirements and configuration for production deployment.
"""

import os
import sys
import shutil
import psutil
import logging
import subprocess
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class SystemChecker:
    """Checks system requirements and configuration."""
    
    REQUIRED_DIRS = [
        'data/audio',
        'data/video',
        'data/json',
        'data/temp',
        'logs',
        'config',
        'tn'
    ]
    
    REQUIRED_FILES = [
        'client_secrets.json',
        'config/production.env',
        'config/serials_config.json'
    ]
    
    REQUIRED_COMMANDS = [
        'ffmpeg',
        'python3',
        'chromium-browser'
    ]
    
    MIN_REQUIREMENTS = {
        'disk_space_gb': 10,
        'memory_gb': 4,
        'cpu_cores': 2
    }
    
    def __init__(self):
        self.issues: List[str] = []
        
    def check_directories(self) -> bool:
        """Check if required directories exist and are writable."""
        for directory in self.REQUIRED_DIRS:
            if not os.path.exists(directory):
                self.issues.append(f"Missing directory: {directory}")
                continue
            
            if not os.access(directory, os.W_OK):
                self.issues.append(f"Directory not writable: {directory}")
        
        return len(self.issues) == 0
    
    def check_files(self) -> bool:
        """Check if required files exist and are readable."""
        for file_path in self.REQUIRED_FILES:
            if not os.path.exists(file_path):
                self.issues.append(f"Missing file: {file_path}")
                continue
            
            if not os.access(file_path, os.R_OK):
                self.issues.append(f"File not readable: {file_path}")
        
        return len(self.issues) == 0
    
    def check_commands(self) -> bool:
        """Check if required commands are available."""
        for command in self.REQUIRED_COMMANDS:
            if not shutil.which(command):
                self.issues.append(f"Missing command: {command}")
        
        return len(self.issues) == 0
    
    def check_ffmpeg(self) -> bool:
        """Check FFmpeg version and capabilities."""
        try:
            result = subprocess.run(["ffmpeg", "-codecs"], 
                                 capture_output=True, 
                                 text=True)
            
            if result.returncode != 0:
                self.issues.append("FFmpeg test failed")
                return False
            
            # Check for required codecs
            if 'libx264' not in result.stdout:
                self.issues.append("FFmpeg missing libx264 support")
            
            if not any(x in result.stdout.lower() for x in ["aac", "libfdk_aac"]):
                self.issues.append("FFmpeg missing AAC support")
                
        except Exception as e:
            self.issues.append(f"FFmpeg check error: {str(e)}")
            return False
            
        return len(self.issues) == 0
    
    def check_system_resources(self) -> bool:
        """Check if system meets minimum requirements."""
        # Check disk space
        disk = psutil.disk_usage('/')
        free_gb = disk.free / (1024 * 1024 * 1024)
        if free_gb < self.MIN_REQUIREMENTS['disk_space_gb']:
            self.issues.append(
                f"Insufficient disk space. Need {self.MIN_REQUIREMENTS['disk_space_gb']}GB, "
                f"have {free_gb:.1f}GB"
            )
        
        # Check memory
        memory = psutil.virtual_memory()
        total_gb = memory.total / (1024 * 1024 * 1024)
        if total_gb < self.MIN_REQUIREMENTS['memory_gb']:
            self.issues.append(
                f"Insufficient memory. Need {self.MIN_REQUIREMENTS['memory_gb']}GB, "
                f"have {total_gb:.1f}GB"
            )
        
        # Check CPU cores
        cpu_count = psutil.cpu_count()
        if cpu_count < self.MIN_REQUIREMENTS['cpu_cores']:
            self.issues.append(
                f"Insufficient CPU cores. Need {self.MIN_REQUIREMENTS['cpu_cores']}, "
                f"have {cpu_count}"
            )
        
        return len(self.issues) == 0
    
    def check_python_packages(self) -> bool:
        """Check if all required Python packages are installed."""
        try:
            import google.oauth2.credentials
            import google_auth_oauthlib.flow
            import googleapiclient.discovery
            import googleapiclient.http
            import playwright
            import requests
            import schedule
            import tqdm
            import dotenv
            
        except ImportError as e:
            self.issues.append(f"Missing Python package: {str(e)}")
            return False
            
        return True
    
    def check_permissions(self) -> bool:
        """Check if the process has necessary permissions."""
        try:
            # Check log file creation
            test_log = 'logs/test.log'
            with open(test_log, 'w') as f:
                f.write('test')
            os.remove(test_log)
            
            # Check video file creation
            test_video = 'data/video/test.txt'
            with open(test_video, 'w') as f:
                f.write('test')
            os.remove(test_video)
            
        except Exception as e:
            self.issues.append(f"Permission check failed: {str(e)}")
            return False
            
        return True
    
    def run_all_checks(self) -> Tuple[bool, List[str]]:
        """Run all system checks."""
        checks = [
            self.check_directories,
            self.check_files,
            self.check_commands,
            self.check_ffmpeg,
            self.check_system_resources,
            self.check_python_packages,
            self.check_permissions
        ]
        
        all_passed = True
        for check in checks:
            if not check():
                all_passed = False
        
        return all_passed, self.issues

def verify_system():
    """Verify system is ready for production."""
    checker = SystemChecker()
    passed, issues = checker.run_all_checks()
    
    if passed:
        logger.info("✅ All system checks passed!")
        return True
    else:
        logger.error("❌ System check failed!")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(0 if verify_system() else 1) 