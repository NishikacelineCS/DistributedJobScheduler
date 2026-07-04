from typing import Callable, Dict, Any

class TaskRegistry:
    def __init__(self):
        self._tasks: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        if name in self._tasks:
            raise ValueError(f"Task with name '{name}' is already registered.")
        self._tasks[name] = func

    def get(self, name: str) -> Callable:
        if name not in self._tasks:
            raise KeyError(f"Task '{name}' not found in registry.")
        return self._tasks[name]

    def task(self, name: str):
        """Decorator to register a task."""
        def decorator(func: Callable):
            self.register(name, func)
            return func
        return decorator

# Global task registry instance
registry = TaskRegistry()
