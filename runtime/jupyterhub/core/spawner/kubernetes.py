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
import contextlib
import re
import time
from typing import TYPE_CHECKING

from jupyterhub.user import User as JupyterHubUser
from kubespawner import KubeSpawner
from tornado import web

from core.spawner.base import RemoteLabSpawnerMixin

if TYPE_CHECKING:
    pass


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


class RemoteLabKubeSpawner(RemoteLabSpawnerMixin, KubeSpawner):
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
