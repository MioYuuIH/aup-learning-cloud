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

"""
JupyterHub Setup Module

This module is called from jupyterhub_config.py to set up business logic.
It reads configuration from the HubConfig singleton and configures:
- Authenticator
- Spawner
- HTTP Handlers

Usage in jupyterhub_config.py:
    from core.config import HubConfig
    HubConfig.init(...)  # Initialize config singleton

    from core.setup import setup_hub
    setup_hub(c)  # Pass JupyterHub config object
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def setup_hub(c: Any) -> None:
    """
    Set up JupyterHub with business logic from core.

    This function:
    1. Gets configuration from HubConfig singleton
    2. Configures the spawner class
    3. Configures the authenticator class
    4. Registers HTTP handlers
    5. Sets up quota session cleanup

    Args:
        c: JupyterHub configuration object (from get_config())
    """
    from core.authenticators import (
        CustomFirstUseAuthenticator,
        CustomGitHubOAuthenticator,
        create_authenticator,
    )
    from core.config import HubConfig
    from core.handlers import configure_handlers, get_handlers
    from core.spawner import RemoteLabKubeSpawner

    # Get the initialized config singleton
    config = HubConfig.get()

    # =========================================================================
    # Configure Spawner
    # =========================================================================

    # Configure spawner class with settings from config
    RemoteLabKubeSpawner.auth_mode = config.auth_mode
    RemoteLabKubeSpawner.single_node_mode = config.single_node_mode
    RemoteLabKubeSpawner.github_org_name = config.github_org_name
    RemoteLabKubeSpawner.quota_enabled = config.quota_enabled

    # Set resource configuration
    RemoteLabKubeSpawner.resource_images = config.build_resource_images()
    RemoteLabKubeSpawner.resource_requirements = config.build_resource_requirements()
    RemoteLabKubeSpawner.node_selector_mapping = config.build_node_selector_mapping()
    RemoteLabKubeSpawner.environment_mapping = config.build_environment_mapping()
    RemoteLabKubeSpawner.team_resource_mapping = config.build_team_resource_mapping()

    # Set quota configuration
    RemoteLabKubeSpawner.quota_rates = config.build_quota_rates()
    RemoteLabKubeSpawner.default_quota = config.quota.defaultQuota
    RemoteLabKubeSpawner.minimum_quota_to_start = config.quota.minimumToStart

    c.JupyterHub.spawner_class = RemoteLabKubeSpawner

    # =========================================================================
    # Configure Authenticator
    # =========================================================================

    c.Authenticator.enable_auth_state = True

    async def auth_state_hook(spawner, auth_state):
        if auth_state is None:
            spawner.github_access_token = None
            return
        spawner.github_access_token = auth_state.get("access_token")

    c.Spawner.auth_state_hook = auth_state_hook

    # Set authenticator based on mode
    c.JupyterHub.authenticator_class = create_authenticator(config.auth_mode)

    if config.auth_mode == "auto-login":
        c.Authenticator.allow_all = True
        c.JupyterHub.template_vars = {"hide_logout": True}
    elif config.auth_mode == "multi":
        c.MultiAuthenticator.authenticators = [
            {
                "authenticator_class": CustomGitHubOAuthenticator,
                "url_prefix": "/github",
            },
            {
                "authenticator_class": CustomFirstUseAuthenticator,
                "url_prefix": "/native",
                "config": {"prefix": ""},
            },
        ]

    # =========================================================================
    # Configure Handlers
    # =========================================================================

    configure_handlers(
        accelerator_options={k: v.model_dump() for k, v in config.accelerators.items()},
        quota_rates=config.build_quota_rates(),
        quota_enabled=config.quota_enabled,
        minimum_quota_to_start=config.quota.minimumToStart,
    )

    if not hasattr(c.JupyterHub, "extra_handlers") or c.JupyterHub.extra_handlers is None:
        c.JupyterHub.extra_handlers = []

    for route, handler in get_handlers():
        c.JupyterHub.extra_handlers.append((route, handler))

    # =========================================================================
    # Quota Session Cleanup
    # =========================================================================

    if config.quota_enabled:
        try:
            from core.quota import get_quota_manager

            quota_manager = get_quota_manager()
            stale_sessions = quota_manager.cleanup_stale_sessions()
            if stale_sessions:
                print(f"[QUOTA] Cleaned up {len(stale_sessions)} stale sessions on startup")
            active_count = quota_manager.get_active_sessions_count()
            print(f"[QUOTA] {active_count} active sessions found")
        except Exception as e:
            print(f"[QUOTA] Warning: Failed to cleanup stale sessions: {e}")

    # =========================================================================
    # Template Vars
    # =========================================================================

    if not isinstance(c.JupyterHub.template_vars, dict):
        c.JupyterHub.template_vars = {}
    c.JupyterHub.template_vars["authenticator_mode"] = config.auth_mode  # type: ignore[assignment]

    print(f"[SETUP] Hub setup complete: auth_mode={config.auth_mode}")
