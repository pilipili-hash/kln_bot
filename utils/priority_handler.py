import functools
from typing import Callable, List, Tuple, Any, Dict

_handlers: List[Tuple[int, Callable, Any]] = []

def register_handler(priority: int):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.priority = priority
        _handlers.append((priority, func, None))
        _handlers.sort(key=lambda item: item[0])
        return wrapper
    return decorator

async def dispatch_event(event: Any, plugins_dict: Dict[str, Any]) -> bool:
    global _handlers
    updated_handlers = []
    for priority, handler, plugin_instance in _handlers:
        if plugin_instance is None:
            for plugin_instance in plugins_dict.values():
                if hasattr(plugin_instance, handler.__name__):
                    updated_handlers.append((priority, handler, plugin_instance))
                    break
        else:
            updated_handlers.append((priority, handler, plugin_instance))
    _handlers = updated_handlers
    for priority, handler, plugin_instance in _handlers:
        if plugin_instance:
            try:
                result = await handler(plugin_instance, event)
                if result is True:
                    # print(f"Event handled by {handler.__name__} from {plugin_instance.__class__.__name__} with priority {priority}")
                    return True
            except Exception as e:
                print(f"Error executing handler {handler.__name__} (priority {priority}): {e}")
    return False