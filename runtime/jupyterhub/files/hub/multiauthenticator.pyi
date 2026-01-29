# Type stubs for jupyterhub-multiauthenticator
from typing import Any

from jupyterhub.auth import Authenticator

class MultiAuthenticator(Authenticator):
    """Authenticator that supports multiple authentication methods."""

    _authenticators: list[Authenticator]

    def __init__(self, **kwargs: Any) -> None: ...
