"""
配置管理器 - 统一管理所有配置文件
"""
import asyncio
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from ncatbot.utils.logger import get_log

_log = get_log()

@dataclass
class BotConfig:
    """机器人基础配置"""
    bot_uin: str = "1554688500"
    ws_uri: str = "ws://localhost:3001"
    token: Optional[str] = None
    root_user: str = "1075047189"
    bot_name: str = "小黑"
    
@dataclass
class ProxyConfig:
    """代理配置"""
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    enabled: bool = False

@dataclass
class APIConfig:
    """API配置"""
    gemini_apikey: str = ""
    saucenao_api_key: str = ""
    pixiv_refresh_token: str = ""
    vits_url: str = "https://siyangyuan-vitshonkai.hf.space"
    chaofen_url: str = "https://siyangyuan-animecf.hf.space"

@dataclass
class DatabaseConfig:
    """数据库配置"""
    db_path: str = "data.db"
    backup_enabled: bool = True
    backup_interval: int = 3600  # 秒

class ConfigManager:
    """统一配置管理器"""
    
    def __init__(self, config_path: Union[str, Path] = "config.yaml"):
        self.config_path = Path(config_path)
        self._config_data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._watchers = []
        
        # 配置对象
        self.bot_config = BotConfig()
        self.proxy_config = ProxyConfig()
        self.api_config = APIConfig()
        self.database_config = DatabaseConfig()
        
    async def load_config(self) -> None:
        """异步加载配置文件"""
        async with self._lock:
            try:
                if not self.config_path.exists():
                    await self._create_default_config()
                    _log.warning(f"配置文件不存在，已创建默认配置: {self.config_path}")
                
                with open(self.config_path, "r", encoding="utf-8") as file:
                    self._config_data = yaml.safe_load(file) or {}
                
                await self._parse_config()
                _log.info(f"成功加载配置文件: {self.config_path}")
                
            except yaml.YAMLError as e:
                _log.error(f"解析 YAML 文件出错: {e}")
                raise
            except Exception as e:
                _log.error(f"加载配置文件时发生错误: {e}")
                raise
    
    async def _parse_config(self) -> None:
        """解析配置到对应的配置对象"""
        # 解析机器人配置
        bot_data = self._config_data.get("bot", {})
        self.bot_config.bot_uin = str(bot_data.get("uin", self.bot_config.bot_uin))
        self.bot_config.ws_uri = bot_data.get("ws_uri", self.bot_config.ws_uri)
        self.bot_config.token = bot_data.get("token")
        self.bot_config.root_user = str(bot_data.get("root_user", self.bot_config.root_user))
        self.bot_config.bot_name = self._config_data.get("bot_name", self.bot_config.bot_name)
        
        # 解析代理配置
        proxy_data = self._config_data.get("proxy", {})
        if isinstance(proxy_data, str):
            # 兼容旧版本配置
            self.proxy_config.http_proxy = proxy_data
            self.proxy_config.https_proxy = proxy_data
            self.proxy_config.enabled = bool(proxy_data)
        elif isinstance(proxy_data, dict):
            self.proxy_config.http_proxy = proxy_data.get("http")
            self.proxy_config.https_proxy = proxy_data.get("https")
            self.proxy_config.enabled = proxy_data.get("enabled", False)
        
        # 解析API配置
        self.api_config.gemini_apikey = self._config_data.get("gemini_apikey", "")
        self.api_config.saucenao_api_key = self._config_data.get("saucenao_api_key", "")
        self.api_config.pixiv_refresh_token = self._config_data.get("pixiv_refresh_token", "")
        self.api_config.vits_url = self._config_data.get("VITS_url", self.api_config.vits_url)
        self.api_config.chaofen_url = self._config_data.get("chaofen_url", self.api_config.chaofen_url)
        
        # 解析数据库配置
        db_data = self._config_data.get("database", {})
        self.database_config.db_path = db_data.get("path", self.database_config.db_path)
        self.database_config.backup_enabled = db_data.get("backup_enabled", self.database_config.backup_enabled)
        self.database_config.backup_interval = db_data.get("backup_interval", self.database_config.backup_interval)
    
    async def _create_default_config(self) -> None:
        """创建默认配置文件"""
        default_config = {
            "bot": {
                "uin": "1554688500",
                "ws_uri": "ws://localhost:3001",
                "root_user": "1075047189"
            },
            "bot_name": "小黑",
            "proxy": {
                "http": "http://127.0.0.1:1100",
                "https": "http://127.0.0.1:1100", 
                "enabled": False
            },
            "master": [1075047189],
            "gemini_apikey": "",
            "saucenao_api_key": "",
            "pixiv_refresh_token": "",
            "VITS_url": "https://siyangyuan-vitshonkai.hf.space",
            "chaofen_url": "https://siyangyuan-animecf.hf.space",
            "database": {
                "path": "data.db",
                "backup_enabled": True,
                "backup_interval": 3600
            }
        }
        
        with open(self.config_path, "w", encoding="utf-8") as file:
            yaml.dump(default_config, file, default_flow_style=False, allow_unicode=True)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split(".")
        value = self._config_data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_bot_config(self) -> Dict[str, Any]:
        """获取机器人配置字典"""
        return {
            "bot_uin": self.bot_config.bot_uin,
            "ws_uri": self.bot_config.ws_uri,
            "token": self.bot_config.token,
            "root_user": self.bot_config.root_user,
            "bot_name": self.bot_config.bot_name
        }
    
    async def save_config(self) -> None:
        """保存配置到文件"""
        async with self._lock:
            try:
                with open(self.config_path, "w", encoding="utf-8") as file:
                    yaml.dump(self._config_data, file, default_flow_style=False, allow_unicode=True)
                _log.info("配置文件已保存")
            except Exception as e:
                _log.error(f"保存配置文件时发生错误: {e}")
                raise
    
    async def update_config(self, key: str, value: Any) -> None:
        """更新配置项"""
        async with self._lock:
            keys = key.split(".")
            config = self._config_data
            
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            config[keys[-1]] = value
            await self.save_config()
            await self._parse_config()
    
    @asynccontextmanager
    async def config_context(self):
        """配置上下文管理器"""
        async with self._lock:
            yield self._config_data
    
    async def close(self) -> None:
        """清理资源"""
        # 清理监听器等资源
        self._watchers.clear()
        _log.info("配置管理器已关闭")

# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None

async def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
        await _config_manager.load_config()
    return _config_manager

def get_config(key: str, default: Any = None) -> Any:
    """
    同步获取配置项（向后兼容）
    注意：这是同步函数，仅用于向后兼容
    """
    global _config_manager
    if _config_manager is None:
        # 如果还没有初始化，创建临时实例
        temp_manager = ConfigManager()
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，无法同步调用异步函数
                _log.warning("在运行的事件循环中同步调用get_config，返回默认值")
                return default
            else:
                loop.run_until_complete(temp_manager.load_config())
                _config_manager = temp_manager
        except RuntimeError:
            _log.warning("无法获取事件循环，返回默认值")
            return default
    
    return _config_manager.get_config(key, default)

# 向后兼容的加载函数
def load_config(config_path: str = "config.yaml") -> None:
    """
    向后兼容的配置加载函数
    """
    import asyncio
    
    async def _load():
        global _config_manager
        _config_manager = ConfigManager(config_path)
        await _config_manager.load_config()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果循环正在运行，创建任务
            asyncio.create_task(_load())
        else:
            loop.run_until_complete(_load())
    except RuntimeError:
        # 没有事件循环，创建新的
        asyncio.run(_load())
