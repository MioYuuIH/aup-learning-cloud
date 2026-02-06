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
Base Spawner Mixin

Provides common functionality for RemoteLab spawners across different platforms.
This mixin can be combined with KubeSpawner, LocalProcessSpawner, etc.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    import logging

    from jupyterhub.user import User

    from core.config import HubConfig


class RemoteLabSpawnerMixin:
    """
    Mixin class providing common RemoteLab spawner functionality.

    This mixin provides:
    - Team-based resource access control
    - Resource selection form generation
    - Quota integration hooks
    - Memory parsing utilities

    Subclasses should implement platform-specific methods.
    """

    # Type hints for attributes from Spawner base class (available at runtime via MRO)
    if TYPE_CHECKING:
        user: User
        log: logging.Logger

    # Configuration injection (set by factory)
    _hub_config: HubConfig | None = None

    # Runtime settings (set by jupyterhub_config.py)
    github_org_name: str = ""
    auth_mode: str = "auto-login"
    single_node_mode: bool = False
    quota_enabled: bool = False

    # Resource configuration (set from config)
    resource_images: dict[str, str] = {}
    resource_requirements: dict[str, dict] = {}
    accelerator_options: dict[str, dict] = {}
    team_resource_mapping: dict[str, list[str]] = {}
    node_selector_mapping: dict[str, dict[str, str]] = {}
    environment_mapping: dict[str, dict[str, str]] = {}

    # Quota settings
    quota_rates: dict[str, int] = {}
    default_quota: int = 0
    minimum_quota_to_start: int = 10

    @classmethod
    def configure_from_config(cls, config: HubConfig) -> None:
        """
        Configure the spawner class from a HubCoreConfig instance.

        This should be called during initialization to inject configuration.
        """
        cls._hub_config = config

        # Extract resource images and requirements
        cls.resource_images = dict(config.resources.images)
        cls.resource_requirements = {
            k: v.model_dump(by_alias=True, exclude_none=True) for k, v in config.resources.requirements.items()
        }

        # Extract accelerator configuration
        cls.accelerator_options = {k: v.model_dump() for k, v in config.accelerators.items()}
        cls.node_selector_mapping = {k: v.nodeSelector for k, v in config.accelerators.items()}
        cls.environment_mapping = {k: v.env for k, v in config.accelerators.items()}

        # Extract team mapping
        cls.team_resource_mapping = dict(config.teams.mapping)

        # Extract quota settings
        cls.quota_rates = config.build_quota_rates()
        cls.default_quota = config.quota.defaultQuota
        cls.minimum_quota_to_start = config.quota.minimumToStart
        cls.quota_enabled = config.quota.enabled

    async def get_user_teams(self) -> list[str]:
        """
        Get available resources for the user based on their GitHub team membership.

        Returns:
            List of resource names the user can access
        """
        username = self.user.name.strip()
        username_upper = username.upper()
        self.log.debug(f"Checking resource group for user: {username}")

        # Auto-login or dummy mode: grant all resources
        if self.auth_mode in ["auto-login", "dummy"]:
            self.log.debug(f"Auth mode '{self.auth_mode}': granting all resources")
            return self.team_resource_mapping.get("official", [])

        # Native users (no prefix) - check by absence of "github:" prefix
        if not username.startswith("github:"):
            self.log.debug(f"Native user detected: {username}")
            if "AUP" in username_upper:
                self.log.debug("Matched AUP user group")
                return self.team_resource_mapping.get("AUP", [])
            elif "TEST" in username_upper:
                self.log.debug("Matched TEST user group")
                return self.team_resource_mapping.get("official", [])
            # Default for native users
            self.log.debug("Native user with default resources")
            return self.team_resource_mapping.get("native-users", self.team_resource_mapping.get("official", []))

        # GitHub users - fetch team membership
        auth_state = await self.user.get_auth_state()
        if not auth_state or "access_token" not in auth_state:
            self.log.debug(
                "No auth state or access token found, setting to NONE, check if there is a local account config error."
            )
            return ["none"]

        access_token = auth_state["access_token"]
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        teams = []
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get("https://api.github.com/user/teams", headers=headers) as resp,
            ):
                if resp.status == 200:
                    data = await resp.json()
                    for team in data:
                        if team["organization"]["login"] == self.github_org_name:
                            teams.append(team["slug"])
                else:
                    self.log.debug(f"GitHub API request failed with status {resp.status}")
        except Exception as e:
            self.log.debug(f"Error fetching teams: {e}")

        # Map teams to available resources
        available_resources = []
        for team, resources in self.team_resource_mapping.items():
            if team in teams:
                if team == "official":
                    available_resources = self.team_resource_mapping[team]
                    break
                else:
                    available_resources.extend(resources)

        # Remove duplicates while preserving order
        available_resources = list(dict.fromkeys(available_resources))

        # If no teams found, provide basic access
        if not available_resources:
            available_resources = ["none"]
            self.log.debug("No team info for this user, set to none")

        self.log.debug(f"User teams: {teams} Available resources: {available_resources}")

        return available_resources

    async def options_form(self, _) -> str:
        """Generate the HTML form for resource selection."""
        try:
            available_resource_names = await self.get_user_teams()
            self.log.debug(f"Providing users with following resources: {available_resource_names}")

            # Use template path
            template_path = os.environ.get("JUPYTERHUB_TEMPLATE_PATH", "/srv/jupyterhub/templates")
            template_file = os.path.join(template_path, "resource_options_form.html")

            if os.path.exists(template_file):
                with open(template_file, encoding="utf-8") as f:
                    html_content = f.read()

                # Inject available resources and config from backend
                available_resources_js = json.dumps(available_resource_names)
                single_node_mode_js = "true" if self.single_node_mode else "false"
                injection_script = f"""
<script>
    window.AVAILABLE_RESOURCES = {available_resources_js};
    window.SINGLE_NODE_MODE = {single_node_mode_js};
</script>
</head>"""

                html_content = html_content.replace("</head>", injection_script)

                self.log.debug(f"Successfully loaded template from {template_file}")
                return html_content
            else:
                self.log.debug(f"Failed to load template from {template_file}, Fall back to basic form.")
                return self._generate_fallback_form(available_resource_names)

        except Exception as e:
            self.log.error(f"Failed to load options form: {e}", exc_info=True)
            return """
            <div style="padding: 20px; background: #ffebee; border: 1px solid #f44336; border-radius: 8px; color: #c62828;">
                <strong>Error:</strong> Failed to load resource selection form.
                <br>Please contact an administrator or check the server logs.
            </div>
            """

    def _generate_fallback_form(self, available_resource_names: list[str]) -> str:
        """Generate a simple fallback form if template is not available."""
        options_html = ""

        for i, resource_name in enumerate(available_resource_names):
            if resource_name in self.resource_images:
                requirements = self.resource_requirements.get(resource_name, {})
                cpu = requirements.get("cpu", "2")
                memory = requirements.get("memory", "4Gi").replace("Gi", "GB")

                checked = "checked" if i == 0 else ""

                options_html += f"""
                <div style="margin-bottom: 12px; padding: 12px; border: 1px solid #e0e0e0; border-radius: 8px; background: white;">
                    <label style="display: flex; align-items: center; cursor: pointer;">
                        <input type="radio" name="resource_type" value="{resource_name}" {checked}
                               style="margin-right: 12px;">
                        <div>
                            <strong>{resource_name.upper()}</strong>
                            <div style="font-size: 0.9em; color: #666;">
                                {cpu} CPU, {memory} Memory
                            </div>
                        </div>
                    </label>
                </div>
                """

        if not options_html:
            options_html = """
            <div style="padding: 20px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; color: #856404;">
                <strong>No resources available</strong><br>
                Please contact administrator for access.
            </div>
            """

        return f"""
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h3>Choose a Resource</h3>
            {options_html}
            <div style="margin-top: 20px;">
                <label for="runtime">Run my server for (minutes):</label>
                <input name="runtime" type="number" min="10" value="20" max="120" step="5"
                       style="margin-left: 10px; padding: 8px; width: 80px;">
            </div>
            <div style="margin-top: 20px;">
                <input type="submit" value="Start" class="btn btn-jupyter form-control">
            </div>
        </div>
        """

    def options_from_form(self, formdata) -> dict[str, Any]:
        """Parse form data and configure the spawner based on selected resource and GPU."""
        options = {}

        # Parse runtime
        runtime_minutes = formdata.get("runtime", ["20"])[0]
        options["runtime_minutes"] = int(runtime_minutes)

        # Parse resource type
        resource_type_list = formdata.get("resource_type", [])
        if len(resource_type_list) != 1:
            raise RuntimeError(f"Selected 0 or more than 1 resources! {resource_type_list}")

        resource_type = resource_type_list[0]
        options["resource_type"] = resource_type

        # Parse GPU selection if available
        gpu_selection = formdata.get(f"gpu_selection_{resource_type}", [None])[0]
        options["gpu_selection"] = gpu_selection

        # Validate resource type
        if resource_type not in self.resource_images:
            raise RuntimeError(f"Unknown Resource: {resource_type}")

        # Configure spawner based on selections (platform-specific)
        self._configure_spawner(resource_type, gpu_selection)

        self.log.debug(
            f"User selected resource: {resource_type} with GPU: {gpu_selection} for {runtime_minutes} minutes"
        )

        return options

    def _configure_spawner(self, _resource_type: str, _gpu_selection: str | None = None) -> None:
        """
        Configure the spawner based on the resource type and GPU selection.

        This method should be overridden by platform-specific subclasses.
        """
        raise NotImplementedError("Subclasses must implement _configure_spawner")

    def _parse_memory_string(self, memory_str) -> float:
        """Parse memory string with units like '16Gi' or '512Mi' to float in GB."""
        if isinstance(memory_str, (int, float)):
            return float(memory_str)

        memory_str = str(memory_str).strip()

        if memory_str.isdigit():
            return float(memory_str)

        units = {
            "Ki": 1 / 1024 / 1024,
            "Mi": 1 / 1024,
            "Gi": 1,
            "Ti": 1024,
            "K": 1 / 1000 / 1000,
            "M": 1 / 1000,
            "G": 1,
            "T": 1000,
        }

        for unit, multiplier in units.items():
            if memory_str.endswith(unit):
                try:
                    value = float(memory_str[: -len(unit)])
                    return value * multiplier
                except ValueError:
                    pass

        try:
            return float(memory_str)
        except ValueError:
            print(f"Warning: Could not parse memory value '{memory_str}', defaulting to 1GB")
            return 1.0

    def get_quota_rate(self, accelerator_type: str | None) -> int:
        """Get quota rate based on accelerator type."""
        if not accelerator_type:
            return self.quota_rates.get("cpu", 1)
        return self.quota_rates.get(accelerator_type, self.quota_rates.get("cpu", 1))
