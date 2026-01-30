# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
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
