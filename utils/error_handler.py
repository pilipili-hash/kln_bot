"""
错误处理和重试机制模块
"""
import asyncio
import functools
import traceback
from typing import Any, Callable, Optional, Type, Union, List
from ncatbot.utils.logger import get_log

_log = get_log()

class RetryError(Exception):
    """重试失败异常"""
    def __init__(self, message: str, last_exception: Exception):
        super().__init__(message)
        self.last_exception = last_exception

def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    异步重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避系数
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # 最后一次尝试失败
                        _log.error(f"函数 {func.__name__} 重试 {max_attempts} 次后失败: {e}")
                        raise RetryError(
                            f"重试 {max_attempts} 次后失败",
                            last_exception
                        )
                    
                    # 执行重试回调
                    if on_retry:
                        try:
                            on_retry(attempt + 1, e)
                        except Exception as callback_error:
                            _log.warning(f"重试回调执行失败: {callback_error}")
                    
                    _log.warning(
                        f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，"
                        f"{current_delay:.1f}秒后重试"
                    )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            # 理论上不会到达这里
            raise last_exception
        
        return wrapper
    return decorator

def safe_async(
    default_return: Any = None,
    log_errors: bool = True,
    raise_on_error: bool = False
):
    """
    安全执行装饰器，捕获所有异常
    
    Args:
        default_return: 出错时的默认返回值
        log_errors: 是否记录错误日志
        raise_on_error: 是否重新抛出异常
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    _log.error(f"函数 {func.__name__} 执行失败: {e}")
                    _log.debug(f"详细错误信息:\n{traceback.format_exc()}")
                
                if raise_on_error:
                    raise
                
                return default_return
        
        return wrapper
    return decorator

class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        self._error_handlers = {}
    
    def register_handler(self, exception_type: Type[Exception], handler: Callable):
        """注册异常处理器"""
        self._error_handlers[exception_type] = handler
    
    async def handle_error(self, exception: Exception, context: str = "") -> bool:
        """
        处理异常
        
        Args:
            exception: 异常实例
            context: 错误上下文信息
            
        Returns:
            bool: 是否已处理
        """
        exception_type = type(exception)
        
        # 查找对应的处理器
        handler = self._error_handlers.get(exception_type)
        if not handler:
            # 查找父类处理器
            for exc_type, exc_handler in self._error_handlers.items():
                if isinstance(exception, exc_type):
                    handler = exc_handler
                    break
        
        if handler:
            try:
                await handler(exception, context)
                return True
            except Exception as handler_error:
                _log.error(f"错误处理器执行失败: {handler_error}")
        
        # 默认处理
        _log.error(f"未处理的异常 [{context}]: {exception}")
        _log.debug(f"异常详情:\n{traceback.format_exc()}")
        return False

# 全局错误处理器实例
global_error_handler = ErrorHandler()

async def handle_api_error(exception: Exception, context: str = ""):
    """API错误处理器"""
    _log.warning(f"API调用失败 [{context}]: {exception}")
    # 这里可以添加具体的API错误处理逻辑

async def handle_database_error(exception: Exception, context: str = ""):
    """数据库错误处理器"""
    _log.error(f"数据库操作失败 [{context}]: {exception}")
    # 这里可以添加数据库错误恢复逻辑

async def handle_network_error(exception: Exception, context: str = ""):
    """网络错误处理器"""
    _log.warning(f"网络请求失败 [{context}]: {exception}")
    # 这里可以添加网络错误重试逻辑

# 注册默认错误处理器
import aiohttp
import aiosqlite

global_error_handler.register_handler(aiohttp.ClientError, handle_api_error)
global_error_handler.register_handler(aiosqlite.Error, handle_database_error)
global_error_handler.register_handler(ConnectionError, handle_network_error)

class CircuitBreaker:
    """熔断器模式实现"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._failure_count = 0
        self._last_failure_time = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def _can_attempt(self) -> bool:
        """检查是否可以尝试调用"""
        if self._state == "CLOSED":
            return True
        elif self._state == "OPEN":
            if (asyncio.get_event_loop().time() - self._last_failure_time) >= self.recovery_timeout:
                self._state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def _on_success(self):
        """成功时的处理"""
        self._failure_count = 0
        self._state = "CLOSED"
    
    def _on_failure(self):
        """失败时的处理"""
        self._failure_count += 1
        self._last_failure_time = asyncio.get_event_loop().time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not self._can_attempt():
                raise Exception(f"熔断器开启，拒绝调用 {func.__name__}")
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper

def timeout(seconds: float):
    """超时装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                _log.warning(f"函数 {func.__name__} 执行超时 ({seconds}秒)")
                raise
        
        return wrapper
    return decorator
