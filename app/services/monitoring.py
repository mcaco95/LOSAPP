import psutil
import time
from datetime import datetime
from flask import current_app

class MonitoringService:
    @staticmethod
    def get_system_metrics():
        """Get current system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_total = memory.total / (1024 * 1024 * 1024)  # Convert to GB
            memory_used = memory.used / (1024 * 1024 * 1024)    # Convert to GB
            memory_percent = memory.percent
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_total = disk.total / (1024 * 1024 * 1024)      # Convert to GB
            disk_used = disk.used / (1024 * 1024 * 1024)        # Convert to GB
            disk_percent = disk.percent
            
            # Process metrics for the current Python process
            process = psutil.Process()
            process_memory = process.memory_info().rss / (1024 * 1024)  # Convert to MB
            process_cpu = process.cpu_percent()
            process_threads = process.num_threads()
            
            return {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'cpu': {
                    'percent': round(cpu_percent, 2),
                    'cores': cpu_count
                },
                'memory': {
                    'total_gb': round(memory_total, 2),
                    'used_gb': round(memory_used, 2),
                    'percent': round(memory_percent, 2)
                },
                'disk': {
                    'total_gb': round(disk_total, 2),
                    'used_gb': round(disk_used, 2),
                    'percent': round(disk_percent, 2)
                },
                'process': {
                    'memory_mb': round(process_memory, 2),
                    'cpu_percent': round(process_cpu, 2),
                    'threads': process_threads
                }
            }
        except Exception as e:
            current_app.logger.error(f"Error getting system metrics: {str(e)}")
            return None 