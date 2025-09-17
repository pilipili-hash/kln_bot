"""
性能监控模块 - 监控系统性能和资源使用情况
"""
import asyncio
import time
import psutil
import functools
from collections import defaultdict, deque
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ncatbot.utils.logger import get_log

_log = get_log()

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    function_name: str
    call_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    error_count: int = 0
    last_called: Optional[datetime] = None
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def update(self, execution_time: float, had_error: bool = False):
        """更新性能指标"""
        self.call_count += 1
        self.total_time += execution_time
        self.avg_time = self.total_time / self.call_count
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)
        self.last_called = datetime.now()
        self.recent_times.append(execution_time)
        
        if had_error:
            self.error_count += 1
    
    @property
    def recent_avg_time(self) -> float:
        """最近调用的平均时间"""
        if not self.recent_times:
            return 0.0
        return sum(self.recent_times) / len(self.recent_times)
    
    @property
    def error_rate(self) -> float:
        """错误率"""
        if self.call_count == 0:
            return 0.0
        return self.error_count / self.call_count

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self._metrics: Dict[str, PerformanceMetrics] = {}
        self._system_metrics = deque(maxlen=1000)
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitor_interval = 10.0  # 秒
        self._alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 80.0,
            'avg_response_time': 1.0,  # 秒
            'error_rate': 0.1  # 10%
        }
    
    def start_monitoring(self):
        """开始性能监控"""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitor_system())
            _log.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止性能监控"""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            _log.info("性能监控已停止")
    
    async def _monitor_system(self):
        """监控系统性能"""
        while True:
            try:
                # 收集系统指标
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                system_metric = {
                    'timestamp': datetime.now(),
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_mb': memory.used / 1024 / 1024,
                    'disk_percent': disk.percent,
                    'disk_used_gb': disk.used / 1024 / 1024 / 1024
                }
                
                self._system_metrics.append(system_metric)
                
                # 检查告警阈值
                await self._check_alerts(system_metric)
                
                await asyncio.sleep(self._monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                _log.error(f"系统监控出错: {e}")
                await asyncio.sleep(self._monitor_interval)
    
    async def _check_alerts(self, metric: Dict[str, Any]):
        """检查告警条件"""
        alerts = []
        
        if metric['cpu_percent'] > self._alert_thresholds['cpu_percent']:
            alerts.append(f"CPU使用率过高: {metric['cpu_percent']:.1f}%")
        
        if metric['memory_percent'] > self._alert_thresholds['memory_percent']:
            alerts.append(f"内存使用率过高: {metric['memory_percent']:.1f}%")
        
        # 检查函数性能告警
        for func_name, func_metrics in self._metrics.items():
            if func_metrics.recent_avg_time > self._alert_thresholds['avg_response_time']:
                alerts.append(f"函数 {func_name} 响应时间过长: {func_metrics.recent_avg_time:.2f}s")
            
            if func_metrics.error_rate > self._alert_thresholds['error_rate']:
                alerts.append(f"函数 {func_name} 错误率过高: {func_metrics.error_rate:.1%}")
        
        # 记录告警
        for alert in alerts:
            _log.warning(f"性能告警: {alert}")
    
    def get_function_metrics(self, function_name: str) -> Optional[PerformanceMetrics]:
        """获取函数性能指标"""
        return self._metrics.get(function_name)
    
    def get_all_metrics(self) -> Dict[str, PerformanceMetrics]:
        """获取所有性能指标"""
        return self._metrics.copy()
    
    def get_system_metrics(self, minutes: int = 10) -> List[Dict[str, Any]]:
        """获取系统性能指标"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            metric for metric in self._system_metrics
            if metric['timestamp'] >= cutoff_time
        ]
    
    def record_function_call(self, function_name: str, execution_time: float, had_error: bool = False):
        """记录函数调用性能"""
        if function_name not in self._metrics:
            self._metrics[function_name] = PerformanceMetrics(function_name)
        
        self._metrics[function_name].update(execution_time, had_error)
    
    def generate_report(self) -> str:
        """生成性能报告"""
        report_lines = ["=== 性能监控报告 ===\n"]
        
        # 系统性能
        if self._system_metrics:
            latest = self._system_metrics[-1]
            report_lines.extend([
                "## 系统性能",
                f"CPU使用率: {latest['cpu_percent']:.1f}%",
                f"内存使用率: {latest['memory_percent']:.1f}% ({latest['memory_used_mb']:.1f}MB)",
                f"磁盘使用率: {latest['disk_percent']:.1f}% ({latest['disk_used_gb']:.1f}GB)",
                ""
            ])
        
        # 函数性能Top 10
        if self._metrics:
            sorted_metrics = sorted(
                self._metrics.values(),
                key=lambda x: x.call_count,
                reverse=True
            )[:10]
            
            report_lines.append("## 函数调用统计 (Top 10)")
            report_lines.append("| 函数名 | 调用次数 | 平均时间 | 最大时间 | 错误率 |")
            report_lines.append("|--------|----------|----------|----------|--------|")
            
            for metric in sorted_metrics:
                report_lines.append(
                    f"| {metric.function_name} | {metric.call_count} | "
                    f"{metric.avg_time:.3f}s | {metric.max_time:.3f}s | "
                    f"{metric.error_rate:.1%} |"
                )
        
        return "\n".join(report_lines)

# 全局性能监控器实例
global_monitor = PerformanceMonitor()

def monitor_performance(function_name: Optional[str] = None):
    """性能监控装饰器"""
    def decorator(func: Callable) -> Callable:
        nonlocal function_name
        if function_name is None:
            function_name = f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            had_error = False
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                had_error = True
                raise
            finally:
                execution_time = time.time() - start_time
                global_monitor.record_function_call(function_name, execution_time, had_error)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            had_error = False
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                had_error = True
                raise
            finally:
                execution_time = time.time() - start_time
                global_monitor.record_function_call(function_name, execution_time, had_error)
        
        # 判断是否为异步函数
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class ResourcePool:
    """资源池管理"""
    
    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._pool = asyncio.Queue(maxsize=max_size)
        self._created_count = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> Any:
        """获取资源"""
        try:
            # 尝试从池中获取资源
            resource = self._pool.get_nowait()
            return resource
        except asyncio.QueueEmpty:
            # 池中没有资源，创建新的
            async with self._lock:
                if self._created_count < self.max_size:
                    resource = await self._create_resource()
                    self._created_count += 1
                    return resource
                else:
                    # 等待资源释放
                    return await self._pool.get()
    
    async def release(self, resource: Any):
        """释放资源"""
        try:
            self._pool.put_nowait(resource)
        except asyncio.QueueFull:
            # 池已满，直接销毁资源
            await self._destroy_resource(resource)
    
    async def _create_resource(self) -> Any:
        """创建新资源（子类实现）"""
        raise NotImplementedError
    
    async def _destroy_resource(self, resource: Any):
        """销毁资源（子类实现）"""
        pass

class HTTPConnectionPool(ResourcePool):
    """HTTP连接池"""
    
    def __init__(self, max_size: int = 10):
        super().__init__(max_size)
        self._session = None
    
    async def _create_resource(self):
        """创建HTTP会话"""
        import aiohttp
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _destroy_resource(self, resource):
        """销毁HTTP会话"""
        if resource and not resource.closed:
            await resource.close()

# 全局HTTP连接池
http_pool = HTTPConnectionPool()

def init_performance_monitoring():
    """初始化性能监控"""
    global_monitor.start_monitoring()
    _log.info("性能监控系统已初始化")

def cleanup_performance_monitoring():
    """清理性能监控"""
    global_monitor.stop_monitoring()
    _log.info("性能监控系统已清理")
