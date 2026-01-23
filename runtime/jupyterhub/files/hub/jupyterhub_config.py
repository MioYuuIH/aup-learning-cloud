# Modifications Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Portions of this file consist of AI-generated content.
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
# ruff: noqa: E402, I001
# E402: Module level import not at top (required: sys.path must be modified before z2jh import)
# I001: Import sorting disabled (import order is intentional)

# Setup path for local modules first
import os
import sys

configuration_directory = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, configuration_directory)

import asyncio
import datetime
import glob
import json
import re
import time
from typing import Any

import aiohttp
import jwt
from firstuseauthenticator import FirstUseAuthenticator
from jupyterhub.auth import Authenticator
from jupyterhub.handlers import BaseHandler
from jupyterhub.utils import url_path_join
from kubernetes_asyncio import client
from kubespawner import KubeSpawner
from multiauthenticator import MultiAuthenticator
from oauthenticator.github import GitHubOAuthenticator
from tornado import web
from tornado.httpclient import AsyncHTTPClient

# z2jh utilities for reading Helm chart values
# Note: z2jh's get_config(key) is renamed to z2jh_get_config to avoid conflict with
# JupyterHub's magic get_config() function (see below)
from z2jh import (
    get_config as z2jh_get_config,
    get_name,
    get_name_env,
    get_secret_value,
    set_config_if_not_none,
)

# JupyterHub magic function: get_config()
# This is injected by traitlets at runtime, NOT imported from any module.
# It returns a configuration object for setting JupyterHub options like c.JupyterHub.port
# See: https://jupyterhub.readthedocs.io/en/stable/getting-started/config-basics.html
c = get_config()  # noqa: F821

c.Authenticator.enable_auth_state = True


async def auth_state_hook(spawner, auth_state):
    if auth_state is None:
        spawner.github_access_token = None
        return
    spawner.github_access_token = auth_state.get("access_token")


c.Spawner.auth_state_hook = auth_state_hook

# GitHub organization name for team-based access control
# Configure in values.yaml: custom.githubOrgName
GITHUB_ORG_NAME = z2jh_get_config("custom.githubOrgName", "")

# ----- RESOURCE IMAGES -----
# format: {resource_name: image_name}
RESOURCE_IMAGES = {
    "cpu": "ghcr.io/amdresearch/auplc-default:latest",
    "Course-CV": "ghcr.io/amdresearch/auplc-cv:latest",
    "Course-DL": "ghcr.io/amdresearch/auplc-dl:latest",
    "Course-LLM": "ghcr.io/amdresearch/auplc-llm:latest",
}

# RESOURCE_REQUIREMENTS
# You should use the exact same `resource_name` key as above.
RESOURCE_REQUIREMENTS = {
    "cpu": {"cpu": "2", "memory": "4Gi", "memory_limit": "6Gi"},
    "Course-CV": {"cpu": "4", "memory": "16Gi", "memory_limit": "24Gi", "amd.com/gpu": "1"},
    "Course-DL": {"cpu": "4", "memory": "16Gi", "memory_limit": "24Gi", "amd.com/gpu": "1"},
    "Course-LLM": {"cpu": "4", "memory": "16Gi", "memory_limit": "24Gi", "amd.com/gpu": "1"},
    "none": {"cpu": "2", "memory": "4Gi", "memory_limit": "6Gi"},
}

# NODE_SELECTOR_MAPPING
# recall https://github.com/AMDResearch/ryzen-aipc-cluster/tree/main/k8s, you should tag the nodes to
# do resource allocation.
NODE_SELECTOR_MAPPING = {
    # GPU nodes
    "strix": {"node-type": "strix"},
    "strix-halo": {"node-type": "strix-halo"},
    "dgpu": {"node-type": "dgpu"},
    # NPU nodes (Note: NPU's strix uses different labels)
    "strix-npu": {"type": "strix"},
}

# ENVIRONMENT_MAPPING
# Here set up the basic environment value of singleuser image when it boot up.
ENVIRONMENT_MAPPING = {"phx": {}, "strix": {}, "dgpu": {}, "strix-npu": {}}

# NPU Security Config
# This is the special NPU security config to enable `sudo` when using NPU inside docker.
# Further information: https://github.com/AMDResearch/Riallto/blob/main/scripts/linux/launch_jupyter.sh
NPU_SECURITY_CONFIG = {
    "extra_container_config": {
        "securityContext": {
            "allowPrivilegeEscalation": True,
            "privileged": True,
            "capabilities": {"add": ["IPC_LOCK", "SYS_ADMIN"]},
        }
    }
}

# TEAM_RESOURCE_MAPPING
# left side is team_name, right side is resource_name
# the resource_name should be the same as the key in RESOURCE_IMAGES
TEAM_RESOURCE_MAPPING = {
    "cpu": ["cpu"],
    "gpu": ["Course-CV", "Course-DL", "Course-LLM"],
    "official": ["cpu", "Course-CV", "Course-DL", "Course-LLM"],
    "AUP": ["Course-CV", "Course-DL", "Course-LLM"],
    "native-users": ["Course-CV", "Course-DL", "Course-LLM"],
}

# Here are some example user and password configs for LocalAccount.

AUP_USERS = [f"AUP{i:02d}" for i in range(1, 51)]
TEST_USERS = [f"TEST{i:02d}" for i in range(1, 51)]
AUP_PASSWORD = "AUP"  # AUP userpassword
TEST_PASSWORD = "TEST"  # TEST userpassword
ADMIN_PASSWORD = "AUP"
LOCAL_ACCOUNT_PREFIX = "LocalAccount"
LOCAL_ACCOUNT_PREFIX_UPPER = LOCAL_ACCOUNT_PREFIX.upper()


# Legacy Authenticator
# Use token to authenticate user. The token was generated by FPGARemoteLab.
class RemoteLabAuthenticator(Authenticator):
    @staticmethod
    def _camelCaseify(s):
        """convert snake_case to camelCase

        For the common case where some_value is set from someValue
        so we don't have to specify the name twice.
        """
        return re.sub(r"_([a-z])", lambda m: m.group(1).upper(), s)

    @staticmethod
    def _get_current_utc_timestamp():
        dt = datetime.datetime.now(datetime.timezone.utc)
        utc_time = dt.replace(tzinfo=datetime.timezone.utc)
        utc_timestamp = utc_time.timestamp()
        return int(utc_timestamp)

    @staticmethod
    def _decode_jwt(token, handler=None):
        # Read the public key from the file
        with open(os.getenv("JWT_PUBLIC_KEY_FILE", "/usr/local/etc/jupyterhub/jwt_public_key.pem")) as f:
            JWT_PUBLIC_KEY = f.read()
        try:
            payload = jwt.decode(token, JWT_PUBLIC_KEY, algorithms="EdDSA")
        except jwt.ExpiredSignatureError:
            print("JWT Info: JWT Expired!")
            return None
        except jwt.InvalidSignatureError:
            print("JWT Info: Not signed by trusted server!")
            return None
        except jwt.DecodeError as e:
            print(f"JWT Info: {e}")
            return None
        except Exception as e:
            if handler:
                handler.log.warning(f"JWT Info: JWT Invalid! {e}")
            return None
        return payload["data"]

    custom_html = """
    <form action="/hub/login"
                method="post"
                role="form">
            <div class="auth-form-header">
              <h1>Sign in</h1>
            </div>
            <div class='auth-form-body m-auto'>
              <input type="hidden" name="_xsrf" value="{{ xsrf }}" />
              <input type="hidden" id="username_input" name="username" value="Invalid" />
              <div id="auth-result" class="alert" style="display:none;margin-bottom:12px;"></div>
              <label for='password_input'>Password:</label>
              <input type="password"
                     class="form-control"
                     autocomplete="current-password"
                     name="password"
                     id="password_input" />
              <div class="feedback-container">
                <input id="login_submit"
                       type="submit"
                       class='btn btn-jupyter form-control'
                       value='Sign in'
                       tabindex="3" />
                <div class="feedback-widget hidden">
                  <i class="fa fa-spinner"></i>
                </div>
              </div>
              <script>
                document.querySelector('form').addEventListener('submit', function(e) {
                  const resultDiv = document.getElementById('auth-result');
                  resultDiv.style.display = 'none';
                });
              </script>
    """

    async def authenticate(self, handler, data=None):
        token = data["password"]
        jwt_data = self._decode_jwt(token, handler)

        # Create error message for display
        error_msg = None
        if jwt_data is None:
            error_msg = "JWT token is invalid or expired"
            handler.log.warning(error_msg)
            raise web.HTTPError(401, error_msg)
        elif jwt_data["type"] != "jupyterhub-token":
            error_msg = f"Unknown token type: {jwt_data['type']}"
            handler.log.warning(error_msg)
            raise web.HTTPError(401, error_msg)

        handler.log.info("Authentication successful")
        return jwt_data["username"]


# MultiAuthenticator
# Change login.html to serve several methods.
class CustomMultiAuthenticator(MultiAuthenticator):
    def get_custom_html(self, base_url):
        html = []

        for authenticator in self._authenticators:
            name = getattr(authenticator, "service_name", "authenticator")
            login_service = getattr(authenticator, "login_service", name)
            url = authenticator.login_url(base_url)

            if name == LOCAL_ACCOUNT_PREFIX:
                # LOCALACCOUNT
                html.append(f"""
                <div class="login-option mb-6 bg-white rounded-xl shadow-lg p-6">
                <form action="{url}" method="post">
                    <input type="hidden" name="_xsrf" value="{{{{ xsrf }}}}" />
                    <div class="mb-4">
                    <input type="text" name="username" placeholder="Username"
                            class="block w-full px-4 py-2 border rounded-md shadow-sm focus:ring-2 focus:ring-blue-500"
                            required />
                    </div>
                    <div class="mb-4">
                    <input type="password" name="password" placeholder="Password"
                            class="block w-full px-4 py-2 border rounded-md shadow-sm focus:ring-2 focus:ring-blue-500"
                            required />
                    </div>
                    <button type="submit"
                            class="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md">
                    Use LocalAccount Login
                    </button>
                </form>
                </div>
                """)
            else:
                # OAuth Button
                html.append(f"""
                <div class="login-option mb-4">
                <a role="button" class="w-full inline-block text-center py-3 px-4 bg-gray-800 text-white
                                    rounded-md hover:bg-gray-900 font-medium"
                    href="{url}{{% if next is defined and next|length %}}?next={{{{next}}}}{{% endif %}}">
                    Use {login_service} Login
                </a>
                </div>
                """)

        return "\n".join(html)


# LocalAccountAuthenticator
# Match the username to the group, all users in the same group can access the same resources.
# all users in the same group share same password.
class SimpleGroupAuthenticator(Authenticator):
    service_name = LOCAL_ACCOUNT_PREFIX

    async def authenticate(self, handler, data):
        username = data["username"].strip()
        password = data["password"].strip()

        if username in AUP_USERS and password == AUP_PASSWORD:
            return {"name": f"{username}", "group": "AUP"}
        elif username in TEST_USERS and password == TEST_PASSWORD:
            return {"name": f"{username}", "group": "TEST"}
        else:
            return None


# AutoLoginAuthenticator
# For single-node deployments - automatically logs in users without credentials
class AutoLoginAuthenticator(Authenticator):
    """
    Authenticator for single-node deployments that automatically logs in users
    without requiring any credentials.

    WARNING: Only use in single-node, personal learning environments!
    This bypasses all authentication and should NEVER be used in production
    or multi-user environments.
    """

    auto_login = True
    login_service = "Auto Login"

    def get_handlers(self, app):
        """Override to bypass login page and auto-authenticate"""
        from jupyterhub.handlers import BaseHandler

        class AutoLoginHandler(BaseHandler):
            """Handler that automatically authenticates and redirects to spawn"""

            async def get(self):
                """Auto-authenticate user on GET request"""
                # Use a fixed username for single-node mode
                username = "student"

                # Get or create user
                user = self.find_user(username)
                if user is None:
                    user = self.user_from_username(username)

                # Set login cookie
                self.set_login_cookie(user)

                # Redirect to user's server (spawn page)
                next_url = self.get_argument("next", "")
                if not next_url:
                    next_url = self.hub.server_url(user, "")

                self.log.info(f"Auto-login: user '{username}' authenticated, redirecting to {next_url}")
                self.redirect(next_url)

            async def post(self):
                """Handle POST requests (shouldn't happen in auto-login)"""
                await self.get()

        # Return custom handler for /login route
        return [
            (r"/login", AutoLoginHandler),
        ]


# GitHubOAth
# Call the GitHub API by access_token
class CustomGitHubOAuthenticator(GitHubOAuthenticator):
    name = "github"

    async def authenticate(self, handler, data=None):
        result = await super().authenticate(handler, data)
        if not result:
            return None

        access_token = result["auth_state"]["access_token"]
        result["auth_state"]["access_token"] = access_token

        return result


# Password change handler for FirstUseAuthenticator


class CheckForcePasswordChangeHandler(BaseHandler):
    """API endpoint to check if user needs to change password"""

    @web.authenticated
    async def get(self):
        """Check if user needs forced password change"""
        user = self.current_user
        username = user.name

        # Remove prefix if present
        if ":" in username:
            username = username.split(":", 1)[1]

        # Check if user needs forced password change
        needs_change = False
        if hasattr(self.authenticator, "_authenticators"):
            for authenticator in self.authenticator._authenticators:
                if isinstance(authenticator, CustomFirstUseAuthenticator):
                    needs_change = authenticator.needs_password_change(username)
                    break

        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps({"needs_password_change": needs_change}))


class ChangePasswordHandler(BaseHandler):
    """Allow users to change their password"""

    @web.authenticated
    async def get(self):
        """Show password change form"""
        password_changed = self.get_argument("password_changed", default=False)
        forced = self.get_argument("forced", default=False)

        # Check if this is a forced password change
        user = self.current_user
        username = user.name
        if ":" in username:
            username = username.split(":", 1)[1]

        is_forced = False
        if hasattr(self.authenticator, "_authenticators"):
            for authenticator in self.authenticator._authenticators:
                if isinstance(authenticator, CustomFirstUseAuthenticator):
                    is_forced = authenticator.needs_password_change(username)
                    break

        html = await self.render_template(
            "change-password.html", password_changed=password_changed, forced_change=is_forced or forced
        )
        self.finish(html)

    @web.authenticated
    async def post(self):
        """Process password change"""
        user = self.current_user
        current_password = self.get_body_argument("current_password", default=None)
        new_password = self.get_body_argument("new_password", default=None)
        confirm_password = self.get_body_argument("confirm_password", default=None)

        if not all([current_password, new_password, confirm_password]):
            self.set_status(400)
            return self.finish("All fields are required")

        if new_password != confirm_password:
            self.set_status(400)
            return self.finish("New passwords do not match")

        # Native users have no prefix, GitHub users have "github:" prefix
        username = user.name
        if username.startswith("github:"):
            self.set_status(400)
            return self.finish("GitHub users cannot change password here")

        # Get FirstUseAuthenticator instance from MultiAuthenticator
        firstuse_auth = None
        if hasattr(self.authenticator, "_authenticators"):
            for authenticator in self.authenticator._authenticators:
                if isinstance(authenticator, CustomFirstUseAuthenticator):
                    firstuse_auth = authenticator
                    break

        if not firstuse_auth:
            self.set_status(500)
            return self.finish("Password change not available")

        # Verify current password using FirstUseAuthenticator
        auth_result = await firstuse_auth.authenticate(self, {"username": username, "password": current_password})

        if not auth_result:
            self.set_status(403)
            return self.finish("Current password is incorrect")

        # Change password using reset_password method
        try:
            firstuse_auth.reset_password(username, new_password)
            if hasattr(firstuse_auth, "clear_force_password_change"):
                firstuse_auth.clear_force_password_change(username)
            self.redirect(self.hub.base_url + "auth/change-password?password_changed=1")
        except Exception as e:
            self.log.error(f"Failed to change password for {username}: {e}")
            self.set_status(500)
            self.finish("Failed to change password")


class AdminResetPasswordHandler(BaseHandler):
    """Allow admins to reset passwords for native/local users"""

    @web.authenticated
    async def get(self):
        """Show admin password reset form"""
        if not self.current_user.admin:
            self.set_status(403)
            return self.finish("Admin access required")

        target_user = self.get_argument("user", default="")
        success = self.get_argument("success", default=False)
        error = self.get_argument("error", default="")

        # Get list of native users
        native_users = []
        from jupyterhub.orm import User

        for user in self.db.query(User).all():
            if not user.name.startswith("github:") and user.name != "admin":
                native_users.append(user.name)

        html = await self.render_template(
            "admin-reset-password.html",
            native_users=sorted(native_users),
            target_user=target_user,
            success=success,
            error=error,
        )
        self.finish(html)

    @web.authenticated
    async def post(self):
        """Process admin password reset"""
        if not self.current_user.admin:
            self.set_status(403)
            return self.finish("Admin access required")

        target_user = self.get_body_argument("target_user", default=None)
        new_password = self.get_body_argument("new_password", default=None)
        confirm_password = self.get_body_argument("confirm_password", default=None)
        force_change = self.get_body_argument("force_change", default="on") == "on"

        if not all([target_user, new_password, confirm_password]):
            return self.redirect(self.hub.base_url + "admin/reset-password?error=All+fields+are+required")

        if new_password != confirm_password:
            return self.redirect(
                self.hub.base_url + f"admin/reset-password?user={target_user}&error=Passwords+do+not+match"
            )

        username = target_user
        if username.startswith("github:"):
            return self.redirect(
                self.hub.base_url
                + f"admin/reset-password?user={target_user}&error=Cannot+reset+password+for+GitHub+users"
            )

        firstuse_auth = None
        if hasattr(self.authenticator, "_authenticators"):
            for authenticator in self.authenticator._authenticators:
                if isinstance(authenticator, CustomFirstUseAuthenticator):
                    firstuse_auth = authenticator
                    break

        if not firstuse_auth:
            return self.redirect(self.hub.base_url + "admin/reset-password?error=Password+reset+not+available")

        try:
            result = firstuse_auth.reset_password(username, new_password)
            if "too short" in result.lower():
                return self.redirect(
                    self.hub.base_url + f"admin/reset-password?user={target_user}&error=Password+too+short"
                )

            if force_change:
                firstuse_auth.mark_force_password_change(username, True)
            else:
                firstuse_auth.clear_force_password_change(username)

            return self.redirect(self.hub.base_url + f"admin/reset-password?success=1&user={target_user}")

        except Exception as e:
            self.log.error(f"Failed to reset password for {target_user}: {e}")
            return self.redirect(
                self.hub.base_url + f"admin/reset-password?user={target_user}&error=Failed+to+reset+password"
            )


class AdminUIHandler(BaseHandler):
    """Serve the custom admin UI (React app)"""

    @web.authenticated
    async def get(self):
        """Serve admin UI page"""
        if not self.current_user.admin:
            self.set_status(403)
            return self.finish("Admin access required")

        html = await self.render_template("admin-ui.html")
        self.finish(html)


class AdminAPISetPasswordHandler(BaseHandler):
    """API endpoint for setting user passwords"""

    def check_xsrf_cookie(self):
        """Allow API calls with proper authentication"""
        pass

    @web.authenticated
    async def post(self):
        """Set password for a user"""
        if not self.current_user.admin:
            self.set_status(403)
            self.set_header("Content-Type", "application/json")
            return self.finish(json.dumps({"error": "Admin access required"}))

        try:
            data = json.loads(self.request.body.decode("utf-8"))
            username = data.get("username")
            password = data.get("password")
            force_change = data.get("force_change", True)

            if not username or not password:
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                return self.finish(json.dumps({"error": "Username and password are required"}))

            if username.startswith("github:"):
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                return self.finish(json.dumps({"error": "Cannot set password for GitHub users"}))

            firstuse_auth = None
            if hasattr(self.authenticator, "_authenticators"):
                for authenticator in self.authenticator._authenticators:
                    if isinstance(authenticator, CustomFirstUseAuthenticator):
                        firstuse_auth = authenticator
                        break

            if not firstuse_auth:
                self.set_status(500)
                self.set_header("Content-Type", "application/json")
                return self.finish(json.dumps({"error": "Password management not available"}))

            result = firstuse_auth.set_password(username, password, force_change=force_change)

            if "too short" in result.lower():
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                return self.finish(json.dumps({"error": result}))

            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"message": result}))

        except json.JSONDecodeError:
            self.set_status(400)
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"error": "Invalid JSON"}))
        except Exception as e:
            self.log.error(f"Failed to set password: {e}")
            self.set_status(500)
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"error": str(e)}))


class AdminAPIGeneratePasswordHandler(BaseHandler):
    """API endpoint for generating random passwords"""

    @web.authenticated
    async def get(self):
        """Generate a random password"""
        if not self.current_user.admin:
            self.set_status(403)
            self.set_header("Content-Type", "application/json")
            return self.finish(json.dumps({"error": "Admin access required"}))

        import secrets
        import string

        chars = string.ascii_letters + string.digits
        chars = chars.replace("l", "").replace("I", "").replace("O", "").replace("0", "")
        password = "".join(secrets.choice(chars) for _ in range(16))

        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps({"password": password}))


# FirstUseAuthenticator - Users set their password on first login
class CustomFirstUseAuthenticator(FirstUseAuthenticator):
    prefix = ""
    service_name = "Native"
    login_service = "Native"
    create_users = False
    dbm_path = "/srv/jupyterhub/passwords.dbm"
    force_change_dbm_path = "/srv/jupyterhub/force_password_change.dbm"

    def normalize_username(self, username):
        """
        Normalize username to lowercase to match JupyterHub's default behavior.

        JupyterHub normalizes usernames to lowercase by default. This method
        ensures consistency between user creation, password setting, and login.

        This prevents authentication issues when users have uppercase letters
        in their usernames (e.g., "UserABC") but JupyterHub normalizes them to
        lowercase during login (e.g., "userabc"), causing a mismatch.

        References:
            - https://jupyterhub.readthedocs.io/en/4.0.2/reference/authenticators.html
            - https://github.com/jupyterhub/jupyterhub/issues/2059
            - https://github.com/jupyterhub/jupyterhub/issues/369

        Args:
            username: The username to normalize

        Returns:
            Lowercase version of the username
        """
        if not username:
            return username
        return username.lower()

    def _user_exists(self, username):
        """Check if user exists in JupyterHub database."""
        if self.db is None:
            if hasattr(self, "parent") and self.parent:
                db = self.parent.db
                if db is None:
                    return True
            else:
                return True
        else:
            db = self.db

        from jupyterhub.orm import User

        return db.query(User).filter_by(name=username).first() is not None

    def set_password(self, username, password, force_change=True):
        """Set password for a user."""
        import dbm

        import bcrypt

        if not self._validate_password(password):
            return f"Password too short! Minimum {self.min_password_length} characters required."

        with dbm.open(self.dbm_path, "c", 0o600) as db:
            db[username] = bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt())

        if force_change:
            self.mark_force_password_change(username)

        return f"Password set for {username}" + (" (force change on next login)" if force_change else "")

    def mark_force_password_change(self, username, force=True):
        """Mark or unmark a user for forced password change."""
        import dbm

        with dbm.open(self.force_change_dbm_path, "c", 0o600) as db:
            if force:
                db[username] = b"1"
            elif username.encode("utf8") in db:
                del db[username]

    def needs_password_change(self, username):
        """Check if user needs to change their password."""
        import dbm

        try:
            with dbm.open(self.force_change_dbm_path, "r") as db:
                return username.encode("utf8") in db or username in db
        except dbm.error:
            return False

    def clear_force_password_change(self, username):
        """Clear the forced password change flag for a user."""
        self.mark_force_password_change(username, force=False)

    async def authenticate(self, handler, data):
        result = await super().authenticate(handler, data)
        return result


# Config for MultiAuthenticator as callback link `url_prefix`
c.MultiAuthenticator.authenticators = [
    {
        "authenticator_class": CustomGitHubOAuthenticator,
        "url_prefix": "/github",
    },
    {
        "authenticator_class": CustomFirstUseAuthenticator,
        "url_prefix": "/native",
        "config": {
            "prefix": "",  # No prefix for native users
        },
    },
]


# Custom Edit for Kubespawner
class RemoteLabKubeSpawner(KubeSpawner):
    """
    Simplified KubeSpawner, relying on frontend to provide detailed resource configuration
    """

    async def get_user_teams(self) -> list[str]:
        """Get available resources for the user based on their GitHub team membership."""

        username = self.user.name.strip()
        username_upper = username.upper()
        print(f"[DEBUG] Checking resource group for user: {username}")

        # Auto-login or dummy mode: grant all resources
        if AUTH_MODE in ["auto-login", "dummy"]:
            print(f"[DEBUG] Auth mode '{AUTH_MODE}': granting all resources")
            return TEAM_RESOURCE_MAPPING["official"]

        # Native users (no prefix) - check by absence of "github:" prefix
        if not username.startswith("github:"):
            print(f"[DEBUG] Native user detected: {username}")
            if "AUP" in username_upper:
                print("[DEBUG] Matched AUP user group")
                return TEAM_RESOURCE_MAPPING["AUP"]
            elif "TEST" in username_upper:
                print("[DEBUG] Matched TEST user group")
                return TEAM_RESOURCE_MAPPING["official"]
            # Default for native users
            print("[DEBUG] Native user with default resources")
            return TEAM_RESOURCE_MAPPING.get("native-users", TEAM_RESOURCE_MAPPING["official"])

        auth_state = await self.user.get_auth_state()
        if not auth_state or "access_token" not in auth_state:
            print(
                "[DEBUG] No auth state or access token found, setting to NONE, check if there is a local account config error."
            )
            return ["none"]
        # Get access token from auth state
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
                        if team["organization"]["login"] == GITHUB_ORG_NAME:
                            teams.append(team["slug"])
                else:
                    print(f"[DEBUG] GitHub API request failed with status {resp.status}")
        except Exception as e:
            print(f"[DEBUG] Error fetching teams: {e}")

        # Map teams to available resources
        available_resources = []
        for team, resources in TEAM_RESOURCE_MAPPING.items():
            if team in teams:
                if team == "official":
                    available_resources = TEAM_RESOURCE_MAPPING[team]
                    break
                else:
                    available_resources.extend(resources)

        # Remove duplicates while preserving order
        available_resources = list(dict.fromkeys(available_resources))

        # If no teams found, provide basic access
        if not available_resources:
            available_resources = ["none"]
            #     available_resources = TEAM_RESOURCE_MAPPING[team]
            print("[DEBUG] No team info for this user, set to none")

        print(f"[DEBUG] User teams: {teams} Available resources: {available_resources}")

        return available_resources

    async def options_form(self, _) -> str:
        """Generate the HTML form for resource selection."""
        try:
            available_resource_names = await self.get_user_teams()
            print(f"[DEBUG] Providing users with following resources: {available_resource_names}")

            # Use template path
            template_path = os.environ.get("JUPYTERHUB_TEMPLATE_PATH", "/srv/jupyterhub/templates")
            template_file = os.path.join(template_path, "resource_options_form.html")

            if os.path.exists(template_file):
                # Read frontend template file
                with open(template_file, encoding="utf-8") as f:
                    html_content = f.read()

                # Inject available resources from backend
                available_resources_js = json.dumps(available_resource_names)
                injection_script = f"""
<script>
    window.AVAILABLE_RESOURCES = {available_resources_js};
</script>
</head>"""

                html_content = html_content.replace("</head>", injection_script)

                print(f"[DEBUG] Successfully loaded template from {template_file}")
                return html_content
            else:
                # If there is no template or load fail, fall back to basic forms
                print(f"[DEBUG] Failed to load template from {template_file}, Fall back to basic form.")
                return self._generate_fallback_form(available_resource_names)

        except Exception as e:
            print(f"[ERROR] Failed to load options form: {e}")
            import traceback

            traceback.print_exc()
            return f"""
            <div style="padding: 20px; background: #ffebee; border: 1px solid #f44336; border-radius: 8px; color: #c62828;">
                <strong>Error:</strong> Failed to load resource selection form.
                <br>Error: {str(e)}
                <br>Please check the logs for more details.
            </div>
            """

    def _generate_fallback_form(self, available_resource_names: list[str]) -> str:
        """Generate a simple fallback form if template is not available."""
        options_html = ""

        for i, resource_name in enumerate(available_resource_names):
            if resource_name in RESOURCE_IMAGES:
                requirements = RESOURCE_REQUIREMENTS.get(resource_name, {})
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
        if resource_type not in RESOURCE_IMAGES:
            raise RuntimeError(f"Unknown Resource: {resource_type}")

        # Configure spawner based on selections
        self._configure_spawner(resource_type, gpu_selection)

        print(
            f"[DEBUG] User selected resource: {resource_type} with GPU: {gpu_selection} for {runtime_minutes} minutes"
        )

        return options

    def _parse_memory_string(self, memory_str):
        """Parse memory string with units like '16Gi' or '512Mi' to float in GB."""
        if isinstance(memory_str, (int, float)):
            return float(memory_str)

        # Remove any whitespace
        memory_str = str(memory_str).strip()

        # If it's just a number, return it as float
        if memory_str.isdigit():
            return float(memory_str)

        # Handle units
        units = {
            "Ki": 1 / 1024 / 1024,  # KiB to GB
            "Mi": 1 / 1024,  # MiB to GB
            "Gi": 1,  # GiB to GB
            "Ti": 1024,  # TiB to GB
            "K": 1 / 1000 / 1000,  # KB to GB
            "M": 1 / 1000,  # MB to GB
            "G": 1,  # GB to GB
            "T": 1000,  # TB to GB
        }

        # Extract number and unit
        for unit, multiplier in units.items():
            if memory_str.endswith(unit):
                try:
                    value = float(memory_str[: -len(unit)])
                    return value * multiplier
                except ValueError:
                    pass

        # If no unit matched or couldn't parse, try direct conversion
        try:
            return float(memory_str)
        except ValueError:
            print(f"Warning: Could not parse memory value '{memory_str}', defaulting to 1GB")
            return 1.0  # Default to 1GB if parsing fails

    def _format_memory_for_k8s(self, memory_value):
        """Format memory value for Kubernetes (convert GB to appropriate unit).

        Args:
            memory_value: Memory value in GB

        Returns:
            String formatted for Kubernetes (e.g., '4G')
        """
        # Convert to string with G suffix for Kubernetes
        return f"{memory_value}G"

    def _format_memory_for_jupyterhub(self, memory_value):
        """Format memory value for JupyterHub's traitlets system.

        Args:
            memory_value: Memory value in GB

        Returns:
            Integer or float value (JupyterHub will add units as needed)
        """
        # JupyterHub expects numeric values for memory traits
        return memory_value

    def _configure_spawner(self, resource_type: str, gpu_selection: str | None = None) -> None:
        """Configure the spawner based on the resource type and GPU selection."""

        # Set basic configuration
        self.image = RESOURCE_IMAGES[resource_type]

        # Set resource requirements
        requirements = RESOURCE_REQUIREMENTS[resource_type]

        # Set CPU guarantee and limit
        self.cpu_guarantee = float(requirements["cpu"])
        self.cpu_limit = float(requirements["cpu"]) * 1.25  # Add 25% buffer for CPU

        # Handle memory values - convert Kubernetes format (Gi) to JupyterHub format (G)
        memory_str = requirements["memory"]

        # Simple conversion from Kubernetes to JupyterHub memory format
        if memory_str.endswith("Gi"):
            # Convert from Gi to G format
            numeric_part = float(memory_str[:-2])
            self.mem_guarantee = f"{numeric_part}G"
        else:
            # If no unit or different unit, use as is
            self.mem_guarantee = memory_str

        # Handle memory limit
        if "memory_limit" in requirements:
            limit_str = requirements["memory_limit"]
            if limit_str.endswith("Gi"):
                # Convert from Gi to G format
                limit_numeric = float(limit_str[:-2])
                self.mem_limit = f"{limit_numeric}G"
            else:
                self.mem_limit = limit_str
        else:
            # If no explicit limit is specified, calculate it as 1.5x the guarantee
            if memory_str.endswith("Gi"):
                numeric_part = float(memory_str[:-2])
                limit_value = numeric_part * 1.5
                self.mem_limit = f"{limit_value}G"
            else:
                # Try to extract numeric part if possible
                try:
                    # Try to extract numeric value from the beginning of the string
                    import re

                    match = re.match(r"^([\d.]+)", memory_str)
                    if match:
                        numeric_part = float(match.group(1))
                        limit_value = numeric_part * 1.5
                        self.mem_limit = f"{limit_value}G"
                    else:
                        # If we can't parse it, just use the original value
                        self.mem_limit = memory_str
                except Exception:
                    # Fallback to original value if parsing fails
                    self.mem_limit = memory_str

        # GPU/NPU resources: trnasfer label to k8s resource requirements.
        if "amd.com/gpu" in requirements:
            self.extra_resource_guarantees = {"amd.com/gpu": str(requirements["amd.com/gpu"])}
            self.extra_resource_limits = {"amd.com/gpu": str(requirements["amd.com/gpu"])}
        elif "amd.com/npu" in requirements:
            pass
            print("[DEBUG] NPU DEVICE PLUGIN are removed, amd.com/npu is no more needed")
            # self.extra_resource_guarantees = {"amd.com/npu": str(requirements["amd.com/npu"])}
            # self.extra_resource_limits = {"amd.com/npu": str(requirements["amd.com/npu"])}

        # Configure node affinity based on GPU selection
        if gpu_selection and gpu_selection in NODE_SELECTOR_MAPPING:
            node_selector = NODE_SELECTOR_MAPPING[gpu_selection]

            # Create node affinity requirement
            node_affinity = {
                "matchExpressions": [
                    {"key": key, "operator": "In", "values": [value]} for key, value in node_selector.items()
                ]
            }

            self.node_affinity_required = [node_affinity]
            print(f"[DEBUG] Set node affinity for GPU {gpu_selection}: {node_affinity}")

            # Set environment variables
            if gpu_selection in ENVIRONMENT_MAPPING:
                env_vars = ENVIRONMENT_MAPPING[gpu_selection]
                if env_vars:
                    self.environment.update(env_vars)
                    print(f"[DEBUG] Set environment variables: {env_vars}")

        # Special configuration for NPU resources
        if resource_type in ["Tutorial-NPU-Resnet", "ROSCON2025-GPU", "ROSCON2025-NPU"]:
            print(f"[DEBUG] Set node affinity for NPU {resource_type}")
            # Apply NPU security configuration
            for key, value in NPU_SECURITY_CONFIG.items():
                if hasattr(self, key):
                    setattr(self, key, value)

            # Set command for NPU containers
            self.cmd = ["/bin/bash", "-l", "-c", "jupyterhub-singleuser", "--allow-root"]

    async def start(self):
        """Start the spawner and schedule automatic shutdown."""
        # Get runtime setting before starting the container
        runtime_minutes = self.user_options.get("runtime_minutes", 20)
        start_time = int(time.time())

        # Set environment variables for jupyterlab-server-timer extension
        self.environment.update(
            {
                "JOB_START_TIME": str(start_time),
                "JOB_RUN_TIME": str(runtime_minutes),
            }
        )

        start_result = await super().start()

        # Store for internal use (auto-shutdown logic)
        self.start_time = start_time
        self.shutdown_time = start_time + (runtime_minutes * 60)

        # Schedule periodic checks and the final shutdown
        loop = asyncio.get_event_loop()
        self.check_timer = loop.call_later(60, self.check_timeout)  # Check every minute

        print(f"[DEBUG] Container for {self.user.name} started at {time.ctime(self.start_time)}")
        print(f"[DEBUG] Scheduled shutdown after {runtime_minutes} minutes at {time.ctime(self.shutdown_time)}")
        return start_result

    def check_timeout(self) -> None:
        """Periodic check for container timeout."""
        current_time = time.time()

        if current_time >= self.shutdown_time:
            print(
                f"[DEBUG] Stopping container for user {self.user.name} as requested time has elapsed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}"
            )
            asyncio.ensure_future(self.stop())
        else:
            # Reschedule next check
            loop = asyncio.get_event_loop()
            self.check_timer = loop.call_later(60, self.check_timeout)

            # Log remaining time every 5 minutes
            remaining_minutes = int((self.shutdown_time - current_time) / 60)
            if remaining_minutes % 5 == 0:
                print(
                    f"[DEBUG] Container for {self.user.name} has {remaining_minutes} minutes remaining at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}"
                )


# If you need to enable DEBUG output for jupyterhub
# c.JupyterHub.log_level = "DEBUG"


# Custom Spawner (KubeSpawner)
c.JupyterHub.spawner_class = RemoteLabKubeSpawner


# ======== Authenticator Configuration ========
# Auth mode: "auto-login" | "dummy" | "github" | "multi"
AUTH_MODE = z2jh_get_config("custom.authMode", "auto-login")
print(f"[INFO] Auth mode: {AUTH_MODE}")

if AUTH_MODE == "auto-login":
    # Auto-login mode: No credentials required (for single-node/personal use)
    c.JupyterHub.authenticator_class = AutoLoginAuthenticator
    c.Authenticator.allow_all = True
    # Hide logout button in single-node mode
    c.JupyterHub.template_vars = {"hide_logout": True}
elif AUTH_MODE == "dummy":
    # Dummy mode: Accept any username/password (for testing)
    c.JupyterHub.authenticator_class = "dummy"
elif AUTH_MODE == "github":
    # GitHub OAuth mode
    c.JupyterHub.authenticator_class = CustomGitHubOAuthenticator
elif AUTH_MODE == "multi":
    # Multi-auth mode: GitHub OAuth + Local accounts
    c.JupyterHub.authenticator_class = CustomMultiAuthenticator
else:
    print(f"[WARN] Unknown auth mode: {AUTH_MODE}, falling back to dummy")
    c.JupyterHub.authenticator_class = "dummy"


# Register password change and admin handlers
if not hasattr(c.JupyterHub, "extra_handlers") or c.JupyterHub.extra_handlers is None:
    c.JupyterHub.extra_handlers = []

c.JupyterHub.extra_handlers.append((r"/auth/change-password", ChangePasswordHandler))
c.JupyterHub.extra_handlers.append((r"/auth/check-force-password-change", CheckForcePasswordChangeHandler))
c.JupyterHub.extra_handlers.append((r"/admin/reset-password", AdminResetPasswordHandler))
c.JupyterHub.extra_handlers.append((r"/admin/users", AdminUIHandler))
c.JupyterHub.extra_handlers.append((r"/admin/groups", AdminUIHandler))
c.JupyterHub.extra_handlers.append((r"/admin/api/set-password", AdminAPISetPasswordHandler))
c.JupyterHub.extra_handlers.append((r"/admin/api/generate-password", AdminAPIGeneratePasswordHandler))

# Set custom template path
c.JupyterHub.template_paths = ["/tmp/custom_templates"]

# ======== Configs below are not modified from Z2JH project ========

# Configure JupyterHub to use the curl backend for making HTTP requests,
# rather than the pure-python implementations. The default one starts
# being too slow to make a large number of requests to the proxy API
# at the rate required.
AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

# Connect to a proxy running in a different pod. Note that *_SERVICE_*
# environment variables are set by Kubernetes for Services
c.ConfigurableHTTPProxy.api_url = f"http://{get_name('proxy-api')}:{get_name_env('proxy-api', '_SERVICE_PORT')}"
c.ConfigurableHTTPProxy.should_start = False

# Do not shut down user pods when hub is restarted
c.JupyterHub.cleanup_servers = False

# Check that the proxy has routes appropriately setup
c.JupyterHub.last_activity_interval = 60

# Don't wait at all before redirecting a spawning user to the progress page
c.JupyterHub.tornado_settings = {
    "slow_spawn_timeout": 0,
}


# configure the hub db connection
db_type = z2jh_get_config("hub.db.type")
if db_type == "sqlite-pvc":
    c.JupyterHub.db_url = "sqlite:///jupyterhub.sqlite"
elif db_type == "sqlite-memory":
    c.JupyterHub.db_url = "sqlite://"
else:
    set_config_if_not_none(c.JupyterHub, "db_url", "hub.db.url")
db_password = get_secret_value("hub.db.password", None)
if db_password is not None:
    if db_type == "mysql":
        os.environ["MYSQL_PWD"] = db_password
    elif db_type == "postgres":
        os.environ["PGPASSWORD"] = db_password
    else:
        print(f"Warning: hub.db.password is ignored for hub.db.type={db_type}")


# c.JupyterHub configuration from Helm chart's configmap
for trait, cfg_key in (
    ("concurrent_spawn_limit", None),
    ("active_server_limit", None),
    ("base_url", None),
    ("allow_named_servers", None),
    ("named_server_limit_per_user", None),
    ("authenticate_prometheus", None),
    ("redirect_to_server", None),
    ("shutdown_on_logout", None),
    ("template_vars", None),
):
    if cfg_key is None:
        cfg_key = RemoteLabAuthenticator._camelCaseify(trait)
    set_config_if_not_none(c.JupyterHub, trait, "hub." + cfg_key)
    print("set config @445", trait, "hub." + cfg_key)
print("HUB SETTING finished", c.JupyterHub)

# hub_bind_url configures what the JupyterHub process within the hub pod's
# container should listen to.
hub_container_port = 8081
c.JupyterHub.hub_bind_url = f"http://:{hub_container_port}"

# hub_connect_url is the URL for connecting to the hub for use by external
# JupyterHub services such as the proxy. Note that *_SERVICE_* environment
# variables are set by Kubernetes for Services.
c.JupyterHub.hub_connect_url = f"http://{get_name('hub')}:{get_name_env('hub', '_SERVICE_PORT')}"

# implement common labels
# This mimics the jupyterhub.commonLabels helper, but declares managed-by to
# kubespawner instead of helm.
#
# The labels app and release are old labels enabled to be deleted in z2jh 5, but
# for now retained to avoid a breaking change in z2jh 4 that would force user
# server restarts. Restarts would be required because NetworkPolicy resources
# must select old/new pods with labels that then needs to be seen on both
# old/new pods, and we want these resources to keep functioning for old/new user
# server pods during an upgrade.
#
common_labels = c.KubeSpawner.common_labels = {}
common_labels["app.kubernetes.io/name"] = common_labels["app"] = z2jh_get_config(
    "nameOverride",
    default=z2jh_get_config("Chart.Name", "jupyterhub"),
)
release = z2jh_get_config("Release.Name")
if release:
    common_labels["app.kubernetes.io/instance"] = common_labels["release"] = release
chart_name = z2jh_get_config("Chart.Name")
chart_version = z2jh_get_config("Chart.Version")
if chart_name and chart_version:
    common_labels["helm.sh/chart"] = common_labels["chart"] = f"{chart_name}-{chart_version.replace('+', '_')}"
common_labels["app.kubernetes.io/managed-by"] = "kubespawner"

c.KubeSpawner.namespace = os.environ.get("POD_NAMESPACE", "default")

# Max number of consecutive failures before the Hub restarts itself
set_config_if_not_none(
    c.Spawner,
    "consecutive_failure_limit",
    "hub.consecutiveFailureLimit",
)

for trait, cfg_key in (
    ("pod_name_template", None),
    ("start_timeout", None),
    ("image_pull_policy", "image.pullPolicy"),
    # ('image_pull_secrets', 'image.pullSecrets'), # Managed manually below
    ("events_enabled", "events"),
    ("extra_labels", None),
    ("extra_annotations", None),
    # ("allow_privilege_escalation", None), # Managed manually below
    ("uid", None),
    ("fs_gid", None),
    ("service_account", "serviceAccountName"),
    ("storage_extra_labels", "storage.extraLabels"),
    # ("tolerations", "extraTolerations"), # Managed manually below
    ("node_selector", None),
    ("node_affinity_required", "extraNodeAffinity.required"),
    ("node_affinity_preferred", "extraNodeAffinity.preferred"),
    ("pod_affinity_required", "extraPodAffinity.required"),
    ("pod_affinity_preferred", "extraPodAffinity.preferred"),
    ("pod_anti_affinity_required", "extraPodAntiAffinity.required"),
    ("pod_anti_affinity_preferred", "extraPodAntiAffinity.preferred"),
    ("lifecycle_hooks", None),
    ("init_containers", None),
    ("extra_containers", None),
    ("mem_limit", "memory.limit"),
    ("mem_guarantee", "memory.guarantee"),
    ("cpu_limit", "cpu.limit"),
    ("cpu_guarantee", "cpu.guarantee"),
    ("environment", "extraEnv"),
    ("profile_list", None),
    ("extra_pod_config", None),
):
    if cfg_key is None:
        cfg_key = RemoteLabAuthenticator._camelCaseify(trait)
    set_config_if_not_none(c.KubeSpawner, trait, "singleuser." + cfg_key)

# allow_privilege_escalation defaults to False in KubeSpawner 2+. Since its a
# property where None, False, and True all are valid values that users of the
# Helm chart may want to set, we can't use the set_config_if_not_none helper
# function as someone may want to override the default False value to None.
#
c.KubeSpawner.allow_privilege_escalation = z2jh_get_config("singleuser.allowPrivilegeEscalation")

# Combine imagePullSecret.create (single), imagePullSecrets (list), and
# singleuser.image.pullSecrets (list).
image_pull_secrets = []
if z2jh_get_config("imagePullSecret.automaticReferenceInjection") and z2jh_get_config("imagePullSecret.create"):
    image_pull_secrets.append(get_name("image-pull-secret"))
if z2jh_get_config("imagePullSecrets"):
    image_pull_secrets.extend(z2jh_get_config("imagePullSecrets"))
if z2jh_get_config("singleuser.image.pullSecrets"):
    image_pull_secrets.extend(z2jh_get_config("singleuser.image.pullSecrets"))
if image_pull_secrets:
    c.KubeSpawner.image_pull_secrets = image_pull_secrets

# scheduling:
if z2jh_get_config("scheduling.userScheduler.enabled"):
    c.KubeSpawner.scheduler_name = get_name("user-scheduler")
if z2jh_get_config("scheduling.podPriority.enabled"):
    c.KubeSpawner.priority_class_name = get_name("priority")

# add node-purpose affinity
match_node_purpose = z2jh_get_config("scheduling.userPods.nodeAffinity.matchNodePurpose")
if match_node_purpose:
    node_selector = {
        "matchExpressions": [
            {
                "key": "hub.jupyter.org/node-purpose",
                "operator": "In",
                "values": ["user"],
            }
        ],
    }
    if match_node_purpose == "prefer":
        c.KubeSpawner.node_affinity_preferred.append(
            {
                "weight": 100,
                "preference": node_selector,
            },
        )
    elif match_node_purpose == "require":
        c.KubeSpawner.node_affinity_required.append(node_selector)
    elif match_node_purpose == "ignore":
        pass
    else:
        raise ValueError(f"Unrecognized value for matchNodePurpose: {match_node_purpose}")

# Combine the common tolerations for user pods with singleuser tolerations
scheduling_user_pods_tolerations = z2jh_get_config("scheduling.userPods.tolerations", [])
singleuser_extra_tolerations = z2jh_get_config("singleuser.extraTolerations", [])
tolerations = scheduling_user_pods_tolerations + singleuser_extra_tolerations
if tolerations:
    c.KubeSpawner.tolerations = tolerations

# Configure dynamically provisioning pvc
storage_type = z2jh_get_config("singleuser.storage.type")
if storage_type == "dynamic":
    pvc_name_template = z2jh_get_config("singleuser.storage.dynamic.pvcNameTemplate")
    if pvc_name_template:
        c.KubeSpawner.pvc_name_template = pvc_name_template
    volume_name_template = z2jh_get_config("singleuser.storage.dynamic.volumeNameTemplate")
    c.KubeSpawner.storage_pvc_ensure = True
    set_config_if_not_none(c.KubeSpawner, "storage_class", "singleuser.storage.dynamic.storageClass")
    set_config_if_not_none(
        c.KubeSpawner,
        "storage_access_modes",
        "singleuser.storage.dynamic.storageAccessModes",
    )
    set_config_if_not_none(c.KubeSpawner, "storage_capacity", "singleuser.storage.capacity")

    # Add volumes to singleuser pods
    c.KubeSpawner.volumes = [
        {
            "name": volume_name_template,
            "persistentVolumeClaim": {"claimName": "{pvc_name}"},
        }
    ]
    c.KubeSpawner.volume_mounts = [
        {
            "mountPath": z2jh_get_config("singleuser.storage.homeMountPath"),
            "name": volume_name_template,
            "subPath": z2jh_get_config("singleuser.storage.dynamic.subPath"),
        }
    ]
elif storage_type == "static":
    pvc_claim_name = z2jh_get_config("singleuser.storage.static.pvcName")
    c.KubeSpawner.volumes = [{"name": "home", "persistentVolumeClaim": {"claimName": pvc_claim_name}}]

    c.KubeSpawner.volume_mounts = [
        {
            "mountPath": z2jh_get_config("singleuser.storage.homeMountPath"),
            "name": "home",
            "subPath": z2jh_get_config("singleuser.storage.static.subPath"),
        }
    ]

# Inject singleuser.extraFiles as volumes and volumeMounts with data loaded from
# the dedicated k8s Secret prepared to hold the extraFiles actual content.
extra_files = z2jh_get_config("singleuser.extraFiles", {})
if extra_files:
    volume = {
        "name": "files",
    }
    items = []
    for file_key, file_details in extra_files.items():
        # Each item is a mapping of a key in the k8s Secret to a path in this
        # abstract volume, the goal is to enable us to set the mode /
        # permissions only though so we don't change the mapping.
        item = {
            "key": file_key,
            "path": file_key,
        }
        if "mode" in file_details:
            item["mode"] = file_details["mode"]
        items.append(item)
    volume["secret"] = {
        "secretName": get_name("singleuser"),
        "items": items,
    }
    c.KubeSpawner.volumes.append(volume)

    volume_mounts = []
    for file_key, file_details in extra_files.items():
        volume_mounts.append(
            {
                "mountPath": file_details["mountPath"],
                "subPath": file_key,
                "name": "files",
            }
        )
    c.KubeSpawner.volume_mounts.extend(volume_mounts)

# Inject extraVolumes / extraVolumeMounts
c.KubeSpawner.volumes.extend(z2jh_get_config("singleuser.storage.extraVolumes", []))
c.KubeSpawner.volume_mounts.extend(z2jh_get_config("singleuser.storage.extraVolumeMounts", []))

c.JupyterHub.services = []
c.JupyterHub.load_roles = []

# jupyterhub-idle-culler's permissions are scoped to what it needs only, see
# https://github.com/jupyterhub/jupyterhub-idle-culler#permissions.
#
if z2jh_get_config("cull.enabled", False):
    jupyterhub_idle_culler_role = {
        "name": "jupyterhub-idle-culler",
        "scopes": [
            "list:users",
            "read:users:activity",
            "read:servers",
            "delete:servers",
            # "admin:users", # dynamically added if --cull-users is passed
        ],
        # assign the role to a jupyterhub service, so it gains these permissions
        "services": ["jupyterhub-idle-culler"],
    }

    cull_cmd = ["python3", "-m", "jupyterhub_idle_culler"]
    base_url = c.JupyterHub.get("base_url", "/")
    cull_cmd.append("--url=http://localhost:8081" + url_path_join(base_url, "hub/api"))

    cull_timeout = z2jh_get_config("cull.timeout")
    if cull_timeout:
        cull_cmd.append(f"--timeout={cull_timeout}")

    cull_every = z2jh_get_config("cull.every")
    if cull_every:
        cull_cmd.append(f"--cull-every={cull_every}")

    cull_concurrency = z2jh_get_config("cull.concurrency")
    if cull_concurrency:
        cull_cmd.append(f"--concurrency={cull_concurrency}")

    if z2jh_get_config("cull.users"):
        cull_cmd.append("--cull-users")
        jupyterhub_idle_culler_role["scopes"].append("admin:users")

    if not z2jh_get_config("cull.adminUsers"):
        cull_cmd.append("--cull-admin-users=false")

    if z2jh_get_config("cull.removeNamedServers"):
        cull_cmd.append("--remove-named-servers")

    cull_max_age = z2jh_get_config("cull.maxAge")
    if cull_max_age:
        cull_cmd.append(f"--max-age={cull_max_age}")

    c.JupyterHub.services.append(
        {
            "name": "jupyterhub-idle-culler",
            "command": cull_cmd,
        }
    )
    c.JupyterHub.load_roles.append(jupyterhub_idle_culler_role)

for key, service in z2jh_get_config("hub.services", {}).items():
    # c.JupyterHub.services is a list of dicts, but
    # hub.services is a dict of dicts to make the config mergable
    service.setdefault("name", key)

    # As the api_token could be exposed in hub.existingSecret, we need to read
    # it it from there or fall back to the chart managed k8s Secret's value.
    service.pop("apiToken", None)
    service["api_token"] = get_secret_value(f"hub.services.{key}.apiToken")

    c.JupyterHub.services.append(service)

for key, role in z2jh_get_config("hub.loadRoles", {}).items():
    # c.JupyterHub.load_roles is a list of dicts, but
    # hub.loadRoles is a dict of dicts to make the config mergable
    role.setdefault("name", key)

    c.JupyterHub.load_roles.append(role)

# respect explicit null command (distinct from unspecified)
# this avoids relying on KubeSpawner.cmd's default being None
# _unspecified = object()
# specified_cmd = z2jh_get_config("singleuser.cmd", _unspecified)
# if specified_cmd is not _unspecified:
#     c.Spawner.cmd = specified_cmd

set_config_if_not_none(c.Spawner, "default_url", "singleuser.defaultUrl")

cloud_metadata = z2jh_get_config("singleuser.cloudMetadata")

if cloud_metadata.get("blockWithIptables"):
    # Use iptables to block access to cloud metadata by default
    network_tools_image_name = z2jh_get_config("singleuser.networkTools.image.name")
    network_tools_image_tag = z2jh_get_config("singleuser.networkTools.image.tag")
    network_tools_resources = z2jh_get_config("singleuser.networkTools.resources")
    ip = cloud_metadata["ip"]
    ip_block_container = client.V1Container(
        name="block-cloud-metadata",
        image=f"{network_tools_image_name}:{network_tools_image_tag}",
        command=[
            "iptables",
            "--append",
            "OUTPUT",
            "--protocol",
            "tcp",
            "--destination",
            ip,
            "--destination-port",
            "80",
            "--jump",
            "DROP",
        ],
        security_context=client.V1SecurityContext(
            privileged=True,
            run_as_user=0,
            capabilities=client.V1Capabilities(add=["NET_ADMIN"]),
        ),
        resources=network_tools_resources,
    )

    c.KubeSpawner.init_containers.append(ip_block_container)

#### HERE BEGINS EXTRA LOG

# c.JupyterHub.extra_log_file='~/jupyterhub.log'

#### HERE ENDS EXTRA LOG


if z2jh_get_config("debug.enabled", False):
    c.JupyterHub.log_level = "DEBUG"
    c.Spawner.debug = True

# load potentially seeded secrets
#
# NOTE: ConfigurableHTTPProxy.auth_token is set through an environment variable
#       that is set using the chart managed secret.
c.JupyterHub.cookie_secret = get_secret_value("hub.config.JupyterHub.cookie_secret")
# NOTE: CryptKeeper.keys should be a list of strings, but we have encoded as a
#       single string joined with ; in the k8s Secret.
#
c.CryptKeeper.keys = get_secret_value("hub.config.CryptKeeper.keys").split(";")

# load hub.config values, except potentially seeded secrets already loaded
for app, cfg in z2jh_get_config("hub.config", {}).items():
    if app == "JupyterHub":
        cfg.pop("proxy_auth_token", None)
        cfg.pop("cookie_secret", None)
        cfg.pop("services", None)
        cfg.pop("authenticator_class", None)
    elif app == "ConfigurableHTTPProxy":
        cfg.pop("auth_token", None)
    elif app == "CryptKeeper":
        cfg.pop("keys", None)
    c[app].update(cfg)

# load /usr/local/etc/jupyterhub/jupyterhub_config.d config files
config_dir = "/usr/local/etc/jupyterhub/jupyterhub_config.d"
if os.path.isdir(config_dir):
    for file_path in sorted(glob.glob(f"{config_dir}/*.py")):
        file_name = os.path.basename(file_path)
        print(f"Loading {config_dir} config: {file_name}")
        with open(file_path) as f:
            file_content = f.read()
        # compiling makes debugging easier: https://stackoverflow.com/a/437857
        exec(compile(source=file_content, filename=file_name, mode="exec"))

# execute hub.extraConfig entries
for key, config_py in sorted(z2jh_get_config("hub.extraConfig", {}).items()):
    print(f"Loading extra config: {key}--{config_py}")
    exec(config_py)

# Pass authenticator_mode to templates
if not isinstance(c.JupyterHub.template_vars, dict):
    c.JupyterHub.template_vars = {}
c.JupyterHub.template_vars["authenticator_mode"] = AUTH_MODE
print(f"✅ Template vars set: authenticator_mode={AUTH_MODE}")
