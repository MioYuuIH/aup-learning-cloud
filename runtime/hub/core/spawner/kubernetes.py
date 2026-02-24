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
Kubernetes Spawner Implementation

Provides RemoteLabKubeSpawner for Kubernetes-based deployments.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import re
import time
from urllib.parse import urlparse
from typing import TYPE_CHECKING, Any

import aiohttp
from jupyterhub.user import User as JupyterHubUser
from kubespawner import KubeSpawner
from tornado import web

if TYPE_CHECKING:
    from core.config import HubConfig


# NPU Security Config
# Special security config to enable `sudo` when using NPU inside docker.
NPU_SECURITY_CONFIG = {
    "extra_container_config": {
        "securityContext": {
            "allowPrivilegeEscalation": True,
            "privileged": True,
            "capabilities": {"add": ["IPC_LOCK", "SYS_ADMIN"]},
        }
    }
}


class RemoteLabKubeSpawner(KubeSpawner):
    """
    KubeSpawner implementation for RemoteLab.

    Provides:
    - Team-based resource access control
    - GPU/NPU selection and node affinity
    - Quota integration for usage tracking
    - Automatic container shutdown
    """

    # Type annotation to override KubeSpawner's MockObject type
    user: JupyterHubUser  # type: ignore[assignment]

    # Configuration injection (set by factory)
    _hub_config: HubConfig | None = None

    # Runtime settings (set by jupyterhub_config.py)
    github_org_name: str = ""
    auth_mode: str = "auto-login"
    single_node_mode: bool = False
    quota_enabled: bool | None = False

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

    # Repository cloning configuration
    ALLOWED_GIT_PROVIDERS: set[str] = {"github.com", "gitlab.com", "bitbucket.org"}
    MAX_CLONE_TIMEOUT: int = 300  # seconds
    GIT_INIT_CONTAINER_IMAGE: str = "alpine/git:2.47.2"

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

        # Extract git clone settings
        git_config = config.git_clone
        if git_config.initContainerImage:
            cls.GIT_INIT_CONTAINER_IMAGE = git_config.initContainerImage
        if git_config.allowedProviders:
            cls.ALLOWED_GIT_PROVIDERS = set(git_config.allowedProviders)
        if git_config.maxCloneTimeout is not None:
            cls.MAX_CLONE_TIMEOUT = git_config.maxCloneTimeout

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

        # Configure spawner based on selections
        self._configure_spawner(resource_type, gpu_selection)

        self.log.debug(
            f"User selected resource: {resource_type} with GPU: {gpu_selection} for {runtime_minutes} minutes"
        )

        # Optional repository cloning fields (do not break existing forms)
        try:
            repo_url = formdata.get("repo_url", [""])[0].strip()
        except Exception:
            repo_url = ""

        try:
            access_token = formdata.get("access_token", [""])[0].strip()
        except Exception:
            access_token = ""

        if repo_url:
            options["repo_url"] = repo_url
        if access_token:
            options["access_token"] = access_token

        return options

    def _validate_and_sanitize_repo_url(self, url: str) -> tuple[bool, str, str]:
        """
        Validate repository URL and return (is_valid, error_message, sanitized_url).
        Empty/blank URLs return (True, "", "").
        """
        if not url or not str(url).strip():
            return True, "", ""

        url = str(url).strip()

        try:
            parsed = urlparse(url)
            if parsed.scheme and parsed.scheme not in ["http", "https"]:
                return False, "Only HTTP/HTTPS URLs supported", ""
            if not parsed.netloc:
                return False, "Invalid URL format", ""
        except Exception as e:
            return False, f"URL parsing error: {e}", ""

        hostname = parsed.netloc.lower()
        is_whitelisted = any(
            hostname == provider or hostname.endswith('.' + provider) for provider in self.ALLOWED_GIT_PROVIDERS
        )

        if not is_whitelisted:
            return False, f"Repository host '{hostname}' not authorized", ""

        dangerous_patterns = [';', '||', '&&', '$(', '`', '\n', '\r']
        if any(pat in url for pat in dangerous_patterns):
            return False, "URL contains suspicious characters", ""

        return True, "", url

    def _extract_repo_name(self, url: str) -> str:
        """Extract and sanitize a directory name from a git repo URL."""
        path = urlparse(url).path.rstrip('/')
        name = path.split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]
        name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
        return name or "repo"

    def _build_git_init_container(self, repo_url: str, repo_name: str, home_volume_name: str) -> dict:
        """
        Build an init container spec that clones or updates the given repository
        into /home/jovyan/<repo_name> on the user's home PVC.

        - First spawn: git clone --depth 1
        - Subsequent spawns: git fetch + reset --hard (always gets latest, no conflict)
        - On any failure: logs the error and exits 0 so the spawn is not blocked

        The script is base64-encoded and decoded at runtime to prevent KubeSpawner's
        _expand_all from treating shell braces as Python format string placeholders.
        """
        clone_script = (
            "#!/bin/sh\n"
            "export HOME=/tmp\n"
            f'REPO_URL="{repo_url}"\n'
            f'CLONE_DIR="/home/jovyan/{repo_name}"\n'
            "git config --global http.sslVerify true\n"
            "git config --global user.email jupyterhub@local\n"
            "git config --global user.name JupyterHub\n"
            "if [ ! -d \"$CLONE_DIR/.git\" ]; then\n"
            "  echo \"Cloning $REPO_URL into $CLONE_DIR\"\n"
            f"  timeout {self.MAX_CLONE_TIMEOUT} git clone --depth 1 \"$REPO_URL\" \"$CLONE_DIR\"\n"
            "  if [ $? -ne 0 ]; then echo 'Clone failed - check URL and network access'; fi\n"
            "else\n"
            "  echo \"Repository exists, fetching latest...\"\n"
            f"  timeout {self.MAX_CLONE_TIMEOUT} git -C \"$CLONE_DIR\" fetch origin\n"
            "  if [ $? -eq 0 ]; then\n"
            "    git -C \"$CLONE_DIR\" reset --hard origin/HEAD\n"
            "  else\n"
            "    echo 'Fetch failed, keeping existing version'\n"
            "  fi\n"
            "fi\n"
            "echo 'Done'\n"
            "exit 0\n"
        )
        encoded = base64.b64encode(clone_script.encode()).decode()

        return {
            "name": "init-clone-repo",
            "image": self.GIT_INIT_CONTAINER_IMAGE,
            "imagePullPolicy": "IfNotPresent",
            "command": ["sh", "-c", f"echo {encoded} | base64 -d | sh"],
            "volumeMounts": [{"name": home_volume_name, "mountPath": "/home/jovyan"}],
            "securityContext": {
                "runAsUser": 1000,
                "runAsNonRoot": True,
                "allowPrivilegeEscalation": False,
            },
            "resources": {
                "requests": {"memory": "128Mi", "cpu": "100m"},
                "limits": {"memory": "256Mi", "cpu": "300m"},
            },
        }

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

    def _configure_spawner(self, resource_type: str, gpu_selection: str | None = None) -> None:
        """Configure the spawner based on the resource type and GPU selection."""

        # Set basic configuration
        self.image = self.resource_images[resource_type]

        # Set resource requirements
        requirements = self.resource_requirements[resource_type]

        # Set CPU guarantee and limit
        self.cpu_guarantee = float(requirements["cpu"])
        self.cpu_limit = float(requirements["cpu"]) * 1.25  # Add 25% buffer

        # Handle memory values
        memory_str = requirements["memory"]

        if memory_str.endswith("Gi"):
            numeric_part = float(memory_str[:-2])
            self.mem_guarantee = f"{numeric_part}G"
        else:
            self.mem_guarantee = memory_str

        # Handle memory limit
        if "memory_limit" in requirements:
            limit_str = requirements["memory_limit"]
            if limit_str.endswith("Gi"):
                limit_numeric = float(limit_str[:-2])
                self.mem_limit = f"{limit_numeric}G"
            else:
                self.mem_limit = limit_str
        else:
            if memory_str.endswith("Gi"):
                numeric_part = float(memory_str[:-2])
                limit_value = numeric_part * 1.5
                self.mem_limit = f"{limit_value}G"
            else:
                try:
                    match = re.match(r"^([\d.]+)", memory_str)
                    if match:
                        numeric_part = float(match.group(1))
                        limit_value = numeric_part * 1.5
                        self.mem_limit = f"{limit_value}G"
                    else:
                        self.mem_limit = memory_str
                except Exception:
                    self.mem_limit = memory_str

        # GPU/NPU resources
        if "amd.com/gpu" in requirements:
            self.extra_resource_guarantees = {"amd.com/gpu": str(requirements["amd.com/gpu"])}
            self.extra_resource_limits = {"amd.com/gpu": str(requirements["amd.com/gpu"])}
        elif "amd.com/npu" in requirements:
            self.log.debug("NPU DEVICE PLUGIN are removed, amd.com/npu is no more needed")

        # Configure node affinity based on GPU selection
        if gpu_selection and gpu_selection in self.node_selector_mapping:
            node_selector = self.node_selector_mapping[gpu_selection]

            node_affinity = {
                "matchExpressions": [
                    {"key": key, "operator": "In", "values": [value]} for key, value in node_selector.items()
                ]
            }

            self.node_affinity_required = [node_affinity]
            self.log.debug(f"Set node affinity for GPU {gpu_selection}: {node_affinity}")

            # Set environment variables
            if gpu_selection in self.environment_mapping:
                env_vars = self.environment_mapping[gpu_selection]
                if env_vars:
                    self.environment.update(env_vars)
                    self.log.debug(f"Set environment variables: {env_vars}")

        # Special configuration for NPU resources
        if resource_type in ["Tutorial-NPU-Resnet", "ROSCON2025-GPU", "ROSCON2025-NPU"]:
            self.log.debug(f"Set node affinity for NPU {resource_type}")
            for key, value in NPU_SECURITY_CONFIG.items():
                if hasattr(self, key):
                    setattr(self, key, value)

            self.cmd = ["/bin/bash", "-l", "-c", "jupyterhub-singleuser", "--allow-root"]

    async def start(self):
        """Start the spawner and schedule automatic shutdown."""
        runtime_minutes = self.user_options.get("runtime_minutes", 20)
        resource_type = self.user_options.get("resource_type", "cpu")
        gpu_selection = self.user_options.get("gpu_selection", None)
        username = self.user.name.lower()

        # Determine accelerator type for quota calculation
        accelerator_type = gpu_selection if gpu_selection else "cpu"

        # Quota check (if enabled)
        if self.quota_enabled:
            from core.quota import get_quota_manager

            quota_manager = get_quota_manager()

            # Check if user has unlimited quota
            has_unlimited = quota_manager.is_unlimited_in_db(username)

            if has_unlimited:
                print(f"[QUOTA] User {username} has unlimited quota, skipping quota check")
                self.usage_session_id = None
                self._has_unlimited_quota = True
            else:
                can_start, message, estimated_cost = quota_manager.can_start_container(
                    username,
                    accelerator_type,
                    runtime_minutes,
                    self.quota_rates,
                    self.default_quota,
                )

                if not can_start:
                    print(f"[QUOTA] Blocked container start for {username}: {message}")
                    raise web.HTTPError(
                        403,
                        f"Cannot start container: {message}. Please contact administrator to add quota.",
                    )

                # Start usage session for tracking
                self.usage_session_id = quota_manager.start_usage_session(username, accelerator_type)
                self._has_unlimited_quota = False
                print(
                    f"[QUOTA] Session {self.usage_session_id} started for {username} ({accelerator_type}), estimated cost: {estimated_cost}"
                )
        else:
            self.usage_session_id = None
            self._has_unlimited_quota = True

        start_time = int(time.time())

        # Calculate quota rate for this accelerator type
        quota_rate = self.get_quota_rate(accelerator_type) if self.quota_enabled else 0

        # Set environment variables for jupyterlab-server-timer extension
        timer_runtime = runtime_minutes if not self.single_node_mode else 4320  # 3 days
        self.environment.update(
            {
                "JOB_START_TIME": str(start_time),
                "JOB_RUN_TIME": str(timer_runtime),
                "QUOTA_RATE": str(quota_rate),
            }
        )

        # Prefer a repo URL provided by the frontend only; do not fallback to config
        try:
            repo_url = str(self.user_options.get("repo_url", "") or "").strip()
            access_token = str(self.user_options.get("access_token", "") or "").strip()
        except Exception:
            repo_url = ""
            access_token = ""

        if repo_url:
            is_valid, err_msg, sanitized_url = self._validate_and_sanitize_repo_url(repo_url)
            if not is_valid:
                self.log.warning(f"Repository URL rejected for user {self.user.name}: {err_msg}")
            else:
                try:
                    repo_name = self._extract_repo_name(sanitized_url)

                    # Reference the volume KubeSpawner will create for the user's home
                    # directory. The name follows the chart's volumeNameTemplate:
                    # volume-{user_server}, which for the default server is volume-{username}.
                    # We must NOT add a duplicate volume entry for the same PVC — on RWO
                    # storage that causes the pod to hang waiting for volume attachment.
                    safe_username = self._expand_user_properties("{username}")
                    home_volume_name = f"volume-{safe_username}"

                    init_container = self._build_git_init_container(sanitized_url, repo_name, home_volume_name)
                    self.init_containers = [init_container] + list(self.init_containers or [])
                    self.log.info(f"Configured git init container for {self.user.name}: {sanitized_url} -> ~/{ repo_name}")
                except Exception as e:
                    self.log.warning(f"Failed to configure git init container: {e}")

        start_result = await super().start()

        # Store for internal use
        self.start_time = start_time
        self._resource_type = resource_type

        # In single-node mode, skip auto-shutdown timer
        if self.single_node_mode:
            self.shutdown_time = None
            self.check_timer = None
            self.log.debug(f"Container for {self.user.name} started (single-node mode, no time limit)")
        else:
            self.shutdown_time = start_time + (runtime_minutes * 60)
            loop = asyncio.get_event_loop()
            self.check_timer = loop.call_later(60, self.check_timeout)
            self.log.debug(f"Container for {self.user.name} started at {time.ctime(self.start_time)}")
            self.log.debug(f"Scheduled shutdown after {runtime_minutes} minutes at {time.ctime(self.shutdown_time)}")

        return start_result

    async def stop(self, now=False):
        """Stop the container and record quota usage."""
        if self.quota_enabled and hasattr(self, "usage_session_id") and self.usage_session_id:
            session_id = self.usage_session_id
            username = self.user.name
            self.usage_session_id = None

            try:
                from core.quota import get_quota_manager

                quota_manager = get_quota_manager()
                duration, quota_used = quota_manager.end_usage_session(session_id, self.quota_rates)
                print(f"[QUOTA] Session ended for {username}. Duration: {duration} min, Quota used: {quota_used}")
            except Exception as e:
                print(f"[QUOTA] Error ending session for {username}: {e}")

        if hasattr(self, "check_timer") and self.check_timer:
            with contextlib.suppress(Exception):
                self.check_timer.cancel()

        return await super().stop(now=now)

    def check_timeout(self) -> None:
        """Periodic check for container timeout."""
        if self.shutdown_time is None:
            return

        current_time = time.time()

        if current_time >= self.shutdown_time:
            self.log.debug(
                f"Stopping container for user {self.user.name} as requested time has elapsed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}"
            )
            asyncio.ensure_future(self.stop())
        else:
            loop = asyncio.get_event_loop()
            self.check_timer = loop.call_later(60, self.check_timeout)

            remaining_minutes = int((self.shutdown_time - current_time) / 60)
            if remaining_minutes % 5 == 0:
                self.log.debug(
                    f"Container for {self.user.name} has {remaining_minutes} minutes remaining at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}"
                )
