# Type stubs for z2jh (Zero to JupyterHub) Helm chart utilities
# These functions are provided by the z2jh Helm chart at runtime
from typing import Any, TypeVar, overload

T = TypeVar("T")

@overload
def get_config(key: str) -> Any: ...
@overload
def get_config(key: str, default: T) -> T | Any: ...
def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value from Helm chart values.yaml"""
    ...

def get_name(name: str) -> str:
    """Get namespaced resource name"""
    ...

def get_name_env(name: str, suffix: str = "") -> str:
    """Get environment variable style name"""
    ...

def get_secret_value(key: str, default: str | None = None) -> str | None:
    """Get value from Kubernetes secret"""
    ...

def set_config_if_not_none(cparent: Any, name: str, key: str) -> None:
    """Set config value if the key exists in Helm values"""
    ...
