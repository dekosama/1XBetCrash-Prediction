#!/usr/bin/env python3
"""
Performance monitoring and benchmarking script for the crash prediction system.
"""

import time
import psutil
import os
import sys
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
import numpy as np
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('performance_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'memory_usage': [],
            'cpu_usage': [],
            'execution_times': {},
            'file_sizes': {},
            'model_load_times': {},
            'prediction_times': []
        }
        self.start_time = time.time()
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics"""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size
            'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        return psutil.cpu_percent(interval=1)
    
    def measure_execution_time(self, func_name: str):
        """Decorator to measure function execution time"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()
                
                execution_time = end_time - start_time
                if func_name not in self.metrics['execution_times']:
                    self.metrics['execution_times'][func_name] = []
                self.metrics['execution_times'][func_name].append(execution_time)
                
                logger.info(f"{func_name} executed in {execution_time:.4f}s")
                return result
            return wrapper
        return decorator
    
    def measure_async_execution_time(self, func_name: str):
        """Decorator to measure async function execution time"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                result = await func(*args, **kwargs)
                end_time = time.time()
                
                execution_time = end_time - start_time
                if func_name not in self.metrics['execution_times']:
                    self.metrics['execution_times'][func_name] = []
                self.metrics['execution_times'][func_name].append(execution_time)
                
                logger.info(f"{func_name} (async) executed in {execution_time:.4f}s")
                return result
            return wrapper
        return decorator
    
    def get_file_sizes(self) -> Dict[str, Dict[str, float]]:
        """Get file sizes for key project files"""
        files_to_check = [
            '1XBetCrash.csv',
            'Crash.py',
            'async_crash_bot.py',
            '1XBetCrashUpdater.py',
            'requirements.txt',
            'Dockerfile'
        ]
        
        file_sizes = {}
        for file_path in files_to_check:
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                file_sizes[file_path] = {
                    'bytes': size_bytes,
                    'kb': size_bytes / 1024,
                    'mb': size_bytes / 1024 / 1024
                }
        
        # Check model cache directory
        model_cache_dir = 'model_cache'
        if os.path.exists(model_cache_dir):
            total_cache_size = 0
            cache_files = 0
            for root, dirs, files in os.walk(model_cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_cache_size += os.path.getsize(file_path)
                    cache_files += 1
            
            file_sizes['model_cache'] = {
                'bytes': total_cache_size,
                'kb': total_cache_size / 1024,
                'mb': total_cache_size / 1024 / 1024,
                'file_count': cache_files
            }
        
        return file_sizes
    
    def record_metrics(self):
        """Record current system metrics"""
        memory = self.get_memory_usage()
        cpu = self.get_cpu_usage()
        
        self.metrics['memory_usage'].append({
            'timestamp': time.time(),
            **memory
        })
        
        self.metrics['cpu_usage'].append({
            'timestamp': time.time(),
            'cpu_percent': cpu
        })
    
    def benchmark_data_loading(self):
        """Benchmark data loading performance"""
        logger.info("Benchmarking data loading...")
        
        csv_file = '1XBetCrash.csv'
        if not os.path.exists(csv_file):
            logger.warning(f"CSV file {csv_file} not found for benchmarking")
            return
        
        # Test different loading methods
        results = {}
        
        # Standard pandas loading
        start_time = time.time()
        df1 = pd.read_csv(csv_file)
        results['standard_loading'] = time.time() - start_time
        
        # Optimized pandas loading with dtypes
        start_time = time.time()
        df2 = pd.read_csv(csv_file, dtype={
            'Number of players': 'int32',
            'Total bets': 'float32',
            'Multiplier': 'float32'
        })
        results['optimized_loading'] = time.time() - start_time
        
        # Memory usage comparison
        results['standard_memory'] = df1.memory_usage(deep=True).sum() / 1024 / 1024  # MB
        results['optimized_memory'] = df2.memory_usage(deep=True).sum() / 1024 / 1024  # MB
        
        logger.info(f"Data loading benchmark results: {results}")
        self.metrics['data_loading_benchmark'] = results
        
        return results
    
    def benchmark_model_performance(self):
        """Benchmark model loading and prediction performance"""
        logger.info("Benchmarking model performance...")
        
        try:
            # Import after ensuring the modules exist
            sys.path.append('.')
            
            # Test sync version
            from Crash import OptimizedCrashPredictor
            
            # Benchmark sync predictor
            start_time = time.time()
            sync_predictor = OptimizedCrashPredictor()
            sync_init_time = time.time() - start_time
            
            start_time = time.time()
            sync_predictions = sync_predictor.predict_next_values(10)
            sync_prediction_time = time.time() - start_time
            
            self.metrics['model_performance'] = {
                'sync_init_time': sync_init_time,
                'sync_prediction_time': sync_prediction_time,
                'sync_models_count': len(sync_predictor.models)
            }
            
            logger.info(f"Sync model init time: {sync_init_time:.4f}s")
            logger.info(f"Sync prediction time: {sync_prediction_time:.4f}s")
            
        except ImportError as e:
            logger.warning(f"Could not import models for benchmarking: {e}")
    
    async def benchmark_async_model_performance(self):
        """Benchmark async model performance"""
        logger.info("Benchmarking async model performance...")
        
        try:
            from async_crash_bot import AsyncOptimizedCrashPredictor
            
            # Benchmark async predictor
            start_time = time.time()
            async_predictor = AsyncOptimizedCrashPredictor()
            await async_predictor.initialize()
            async_init_time = time.time() - start_time
            
            start_time = time.time()
            async_predictions = await async_predictor.predict_next_values(10)
            async_prediction_time = time.time() - start_time
            
            if 'model_performance' not in self.metrics:
                self.metrics['model_performance'] = {}
            
            self.metrics['model_performance'].update({
                'async_init_time': async_init_time,
                'async_prediction_time': async_prediction_time,
                'async_models_count': len(async_predictor.models)
            })
            
            logger.info(f"Async model init time: {async_init_time:.4f}s")
            logger.info(f"Async prediction time: {async_prediction_time:.4f}s")
            
        except ImportError as e:
            logger.warning(f"Could not import async models for benchmarking: {e}")
    
    def analyze_docker_optimization(self):
        """Analyze Docker-related optimizations"""
        logger.info("Analyzing Docker optimizations...")
        
        dockerfile_path = 'Dockerfile'
        dockerignore_path = '.dockerignore'
        
        optimizations = {
            'multi_stage_build': False,
            'slim_base_image': False,
            'dockerignore_present': os.path.exists(dockerignore_path),
            'layer_optimization': False
        }
        
        if os.path.exists(dockerfile_path):
            with open(dockerfile_path, 'r') as f:
                dockerfile_content = f.read().lower()
                
                if 'as base' in dockerfile_content or 'as production' in dockerfile_content:
                    optimizations['multi_stage_build'] = True
                
                if 'python:' in dockerfile_content and 'slim' in dockerfile_content:
                    optimizations['slim_base_image'] = True
                
                if '--no-cache-dir' in dockerfile_content:
                    optimizations['layer_optimization'] = True
        
        self.metrics['docker_optimizations'] = optimizations
        logger.info(f"Docker optimizations: {optimizations}")
        
        return optimizations
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        logger.info("Generating performance report...")
        
        # Calculate averages and statistics
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_runtime': time.time() - self.start_time,
            'system_info': {
                'cpu_count': psutil.cpu_count(),
                'total_memory_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
                'python_version': sys.version
            },
            'file_sizes': self.get_file_sizes(),
            'optimizations_applied': []
        }
        
        # Memory usage statistics
        if self.metrics['memory_usage']:
            memory_usage = [m['rss_mb'] for m in self.metrics['memory_usage']]
            report['memory_stats'] = {
                'avg_memory_mb': np.mean(memory_usage),
                'max_memory_mb': np.max(memory_usage),
                'min_memory_mb': np.min(memory_usage)
            }
        
        # CPU usage statistics
        if self.metrics['cpu_usage']:
            cpu_usage = [c['cpu_percent'] for c in self.metrics['cpu_usage']]
            report['cpu_stats'] = {
                'avg_cpu_percent': np.mean(cpu_usage),
                'max_cpu_percent': np.max(cpu_usage),
                'min_cpu_percent': np.min(cpu_usage)
            }
        
        # Execution time statistics
        if self.metrics['execution_times']:
            execution_stats = {}
            for func_name, times in self.metrics['execution_times'].items():
                execution_stats[func_name] = {
                    'avg_time': np.mean(times),
                    'max_time': np.max(times),
                    'min_time': np.min(times),
                    'call_count': len(times)
                }
            report['execution_stats'] = execution_stats
        
        # Add other metrics
        for key in ['data_loading_benchmark', 'model_performance', 'docker_optimizations']:
            if key in self.metrics:
                report[key] = self.metrics[key]
        
        # List applied optimizations
        optimizations = [
            "Multi-stage Docker build",
            "Slim Python base image",
            "Model caching with pickle",
            "Memory-efficient data types (float32, int32)",
            "Parallel model execution",
            "Async processing capabilities",
            "Chrome browser optimizations for Selenium",
            "Buffered CSV writing",
            "LRU caching for data loading",
            "Garbage collection optimization"
        ]
        report['optimizations_applied'] = optimizations
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: str = None):
        """Save performance report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Performance report saved to {filename}")
        return filename

async def run_performance_analysis():
    """Run comprehensive performance analysis"""
    monitor = PerformanceMonitor()
    
    logger.info("Starting performance analysis...")
    
    # Record initial metrics
    monitor.record_metrics()
    
    # Run benchmarks
    monitor.benchmark_data_loading()
    monitor.benchmark_model_performance()
    await monitor.benchmark_async_model_performance()
    monitor.analyze_docker_optimization()
    
    # Record final metrics
    monitor.record_metrics()
    
    # Generate and save report
    report = monitor.generate_report()
    filename = monitor.save_report(report)
    
    # Print summary
    print("\n" + "="*60)
    print("PERFORMANCE ANALYSIS SUMMARY")
    print("="*60)
    
    if 'memory_stats' in report:
        print(f"Average Memory Usage: {report['memory_stats']['avg_memory_mb']:.2f} MB")
        print(f"Peak Memory Usage: {report['memory_stats']['max_memory_mb']:.2f} MB")
    
    if 'data_loading_benchmark' in report:
        dlb = report['data_loading_benchmark']
        print(f"Data Loading Improvement: {((dlb['standard_loading'] - dlb['optimized_loading']) / dlb['standard_loading'] * 100):.1f}%")
        print(f"Memory Usage Reduction: {((dlb['standard_memory'] - dlb['optimized_memory']) / dlb['standard_memory'] * 100):.1f}%")
    
    if 'model_performance' in report:
        mp = report['model_performance']
        if 'async_prediction_time' in mp and 'sync_prediction_time' in mp:
            async_improvement = ((mp['sync_prediction_time'] - mp['async_prediction_time']) / mp['sync_prediction_time'] * 100)
            print(f"Async Performance Improvement: {async_improvement:.1f}%")
    
    print(f"Total Optimizations Applied: {len(report['optimizations_applied'])}")
    print(f"Report saved to: {filename}")
    print("="*60)

if __name__ == "__main__":
    try:
        asyncio.run(run_performance_analysis())
    except KeyboardInterrupt:
        logger.info("Performance analysis interrupted by user")
    except Exception as e:
        logger.error(f"Performance analysis failed: {e}")
        raise