from types import ModuleType
from typing import Dict, Any


def execute_code(code: str, **kwargs) -> Dict[str, Any]:
    local_values = dict(kwargs)
    exec(code, globals(), local_values)
    return local_values


def import_module(module_name: str, from_module: str = None) -> ModuleType:
    if from_module is None:
        code = f"import {module_name}"
    else:
        code = f"from {from_module} import {module_name}"
    params = execute_code(code)
    return params[module_name]


def import_module_and_get_attribute(module_name: str, attribute_name: str, from_module: str = None) -> Any:
    mod = import_module(module_name, from_module)
    return mod.__dict__[attribute_name]
