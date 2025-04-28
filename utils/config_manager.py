import yaml
import os
from ncatbot.utils.logger import get_log

_log = get_log()

_config = {}

def load_config(config_path="config.yaml"):
    """
    加载 YAML 配置文件并存储到全局变量中。
    """
    global _config
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            _config = yaml.safe_load(file)
        _log.info(f"成功加载配置文件: {config_path}")
    except FileNotFoundError:
        _log.error(f"配置文件未找到: {config_path}")
    except yaml.YAMLError as e:
        _log.error(f"解析 YAML 文件出错: {e}")
    except Exception as e:
        _log.error(f"加载配置文件时发生错误: {e}")

def get_config(key, default=None):
    """
    从全局配置中获取指定配置项的值。
    """
    return _config.get(key, default)
