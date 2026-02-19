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
HTTP Handlers for JupyterHub

Provides custom handlers for:
- Password management
- Admin UI
- Quota management API
- Accelerator configuration API
"""

from __future__ import annotations

import json
from typing import Any

from jupyterhub.apihandlers import APIHandler
from jupyterhub.handlers import BaseHandler
from multiauthenticator import MultiAuthenticator
from pydantic import ValidationError
from tornado import web

from core.authenticators import CustomFirstUseAuthenticator
from core.quota import (
    BatchQuotaRequest,
    QuotaAction,
    QuotaModifyRequest,
    QuotaRefreshRequest,
    get_quota_manager,
)

# =============================================================================
# Module-level configuration (set via configure_handlers)
# =============================================================================

_handler_config: dict[str, Any] = {
    "accelerator_options": {},
    "quota_rates": {},
    "quota_enabled": False,
    "minimum_quota_to_start": 10,
}


def configure_handlers(
    accelerator_options: dict[str, Any] | None = None,
    quota_rates: dict[str, int] | None = None,
    quota_enabled: bool = False,
    minimum_quota_to_start: int = 10,
) -> None:
    """Configure handler module with runtime settings."""
    if accelerator_options is not None:
        _handler_config["accelerator_options"] = accelerator_options
    if quota_rates is not None:
        _handler_config["quota_rates"] = quota_rates
    _handler_config["quota_enabled"] = quota_enabled
    _handler_config["minimum_quota_to_start"] = minimum_quota_to_start


# =============================================================================
# Password Management Handlers
# =============================================================================


class CheckForcePasswordChangeHandler(BaseHandler):
    """API endpoint to check if user needs to change password."""

    @web.authenticated
    async def get(self):
        """Check if user needs forced password change."""
        assert self.current_user is not None
        user = self.current_user
        username = user.name

        if ":" in username:
            username = username.split(":", 1)[1]

        needs_change = False
        if isinstance(self.authenticator, MultiAuthenticator):
            for authenticator in self.authenticator._authenticators:
                if isinstance(authenticator, CustomFirstUseAuthenticator):
                    needs_change = authenticator.needs_password_change(username)
                    break

        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps({"needs_password_change": needs_change}))


class ChangePasswordHandler(BaseHandler):
    """Allow users to change their password."""

    @web.authenticated
    async def get(self):
        """Show password change form."""
        assert self.current_user is not None
        password_changed = self.get_argument("password_changed", default="") != ""
        forced = self.get_argument("forced", default="") != ""

        user = self.current_user
        username = user.name
        if ":" in username:
            username = username.split(":", 1)[1]

        is_forced = False
        if isinstance(self.authenticator, MultiAuthenticator):
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
        """Process password change."""
        assert self.current_user is not None
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

        username = user.name
        if username.startswith("github:"):
            self.set_status(400)
            return self.finish("GitHub users cannot change password here")

        firstuse_auth = None
        if isinstance(self.authenticator, MultiAuthenticator):
            for authenticator in self.authenticator._authenticators:
                if isinstance(authenticator, CustomFirstUseAuthenticator):
                    firstuse_auth = authenticator
                    break

        if not firstuse_auth:
            self.set_status(500)
            return self.finish("Password change not available")

        auth_result = await firstuse_auth.authenticate(self, {"username": username, "password": current_password})

        if not auth_result:
            self.set_status(403)
            return self.finish("Current password is incorrect")

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
    """Allow admins to reset passwords for native/local users."""

    @web.authenticated
    async def get(self):
        """Show admin password reset form."""
        assert self.current_user is not None
        if not self.current_user.admin:
            self.set_status(403)
            return self.finish("Admin access required")

        target_user = self.get_argument("user", default="")
        success = self.get_argument("success", default="") != ""
        error = self.get_argument("error", default="")

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
        """Process admin password reset."""
        assert self.current_user is not None
        if not self.current_user.admin:
            self.set_status(403)
            return self.finish("Admin access required")

        target_user = self.get_body_argument("target_user", default=None)
        new_password = self.get_body_argument("new_password", default=None)
        confirm_password = self.get_body_argument("confirm_password", default=None)
        force_change = self.get_body_argument("force_change", default="on") == "on"

        if not target_user or not new_password or not confirm_password:
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
        if isinstance(self.authenticator, MultiAuthenticator):
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


# =============================================================================
# Admin UI Handlers
# =============================================================================


class AdminUIHandler(BaseHandler):
    """Serve the custom admin UI (React app)."""

    @web.authenticated
    async def get(self):
        """Serve admin UI page."""
        assert self.current_user is not None
        if not self.current_user.admin:
            self.set_status(403)
            return self.finish("Admin access required")

        html = await self.render_template("admin-ui.html")
        self.finish(html)


class AdminAPISetPasswordHandler(APIHandler):
    """API endpoint for setting user passwords."""

    @web.authenticated
    async def post(self):
        """Set password for a user."""
        assert self.current_user is not None
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
            if isinstance(self.authenticator, MultiAuthenticator):
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
            self.finish(json.dumps({"error": "Failed to set password"}))


class AdminAPIGeneratePasswordHandler(APIHandler):
    """API endpoint for generating random passwords."""

    @web.authenticated
    async def get(self):
        """Generate a random password."""
        assert self.current_user is not None
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


# =============================================================================
# Quota Management Handlers
# =============================================================================


class QuotaAPIHandler(APIHandler):
    """API endpoint for managing user quota."""

    @web.authenticated
    async def get(self, username=None):
        """Get quota balance."""
        assert self.current_user is not None

        if username:
            if not self.current_user.admin and self.current_user.name.lower() != username.lower():
                self.set_status(403)
                self.set_header("Content-Type", "application/json")
                return self.finish(json.dumps({"error": "Access denied"}))

            quota_manager = get_quota_manager()
            balance = quota_manager.get_balance(username)
            unlimited = quota_manager.is_unlimited_in_db(username)
            transactions = quota_manager.get_user_transactions(username, 20)

            self.set_header("Content-Type", "application/json")
            self.finish(
                json.dumps(
                    {
                        "username": username,
                        "balance": balance,
                        "unlimited": unlimited,
                        "recent_transactions": transactions,
                    }
                )
            )
        else:
            if not self.current_user.admin:
                self.set_status(403)
                self.set_header("Content-Type", "application/json")
                return self.finish(json.dumps({"error": "Admin access required"}))

            quota_manager = get_quota_manager()
            balances = quota_manager.get_all_balances()

            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"users": balances}))

    @web.authenticated
    async def post(self, username=None):
        """Set or add quota (admin only)."""
        assert self.current_user is not None
        if not self.current_user.admin:
            self.set_status(403)
            self.set_header("Content-Type", "application/json")
            return self.finish(json.dumps({"error": "Admin access required"}))

        try:
            data = json.loads(self.request.body.decode("utf-8"))

            try:
                req = QuotaModifyRequest(**data)
            except ValidationError as ve:
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                errors = [{"field": e["loc"][0] if e["loc"] else "request", "message": e["msg"]} for e in ve.errors()]
                return self.finish(json.dumps({"error": "Validation failed", "details": errors}))

            if not username:
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                return self.finish(json.dumps({"error": "Username required"}))

            quota_manager = get_quota_manager()
            admin_name = self.current_user.name

            if req.action == QuotaAction.SET:
                assert req.amount is not None
                new_balance = quota_manager.set_balance(username, req.amount, admin_name)
            elif req.action == QuotaAction.ADD:
                assert req.amount is not None
                new_balance = quota_manager.add_quota(username, req.amount, req.description or "", admin_name)
            elif req.action == QuotaAction.DEDUCT:
                assert req.amount is not None
                current_balance = quota_manager.get_balance(username)
                if current_balance < req.amount:
                    self.set_status(400)
                    self.set_header("Content-Type", "application/json")
                    return self.finish(json.dumps({"error": "Insufficient balance"}))
                new_balance = quota_manager.deduct_quota(username, req.amount, req.description or "")
            elif req.action == QuotaAction.SET_UNLIMITED:
                assert req.unlimited is not None
                quota_manager.set_unlimited(username, req.unlimited, admin_name)
                new_balance = quota_manager.get_balance(username)
                self.set_header("Content-Type", "application/json")
                return self.finish(
                    json.dumps(
                        {
                            "username": username,
                            "balance": new_balance,
                            "unlimited": req.unlimited,
                            "action": req.action.value,
                        }
                    )
                )

            self.set_header("Content-Type", "application/json")
            self.finish(
                json.dumps(
                    {
                        "username": username,
                        "balance": new_balance,
                        "action": req.action.value,
                        "amount": req.amount,
                    }
                )
            )

        except json.JSONDecodeError:
            self.set_status(400)
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"error": "Invalid JSON"}))
        except Exception as e:
            self.log.error(f"Quota API error: {e}")
            self.set_status(500)
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"error": "Internal server error"}))


class QuotaBatchAPIHandler(APIHandler):
    """API endpoint for batch quota operations."""

    @web.authenticated
    async def post(self):
        """Batch set quota for multiple users."""
        assert self.current_user is not None
        if not self.current_user.admin:
            self.set_status(403)
            self.set_header("Content-Type", "application/json")
            return self.finish(json.dumps({"error": "Admin access required"}))

        try:
            data = json.loads(self.request.body.decode("utf-8"))

            try:
                req = BatchQuotaRequest(**data)
            except ValidationError as ve:
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                errors = [{"field": str(e["loc"]), "message": e["msg"]} for e in ve.errors()]
                return self.finish(json.dumps({"error": "Validation failed", "details": errors}))

            quota_manager = get_quota_manager()
            admin_name = self.current_user.name

            results = {"success": 0, "failed": 0, "details": []}

            for user in req.users:
                try:
                    quota_manager.set_balance(user.username, user.amount, admin_name)
                    results["success"] += 1
                    results["details"].append({"username": user.username, "status": "success", "balance": user.amount})
                except Exception:
                    results["failed"] += 1
                    results["details"].append(
                        {"username": user.username, "status": "failed", "error": "Processing error"}
                    )

            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps(results))

        except json.JSONDecodeError:
            self.set_status(400)
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"error": "Invalid JSON"}))
        except Exception as e:
            self.log.error(f"Batch quota API error: {e}")
            self.set_status(500)
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"error": "Internal server error"}))


class QuotaRefreshHandler(APIHandler):
    """API endpoint for batch quota refresh."""

    @web.authenticated
    async def post(self):
        """Refresh quota for all eligible users based on targeting rules."""
        assert self.current_user is not None
        is_admin = getattr(self.current_user, "admin", False)
        if not is_admin:
            self.set_status(403)
            self.set_header("Content-Type", "application/json")
            user_info = f"name={getattr(self.current_user, 'name', 'unknown')}, admin={is_admin}"
            self.log.warning(f"[QUOTA] Refresh 403: {user_info}")
            return self.finish(json.dumps({"error": "Admin access required"}))

        try:
            data = json.loads(self.request.body.decode("utf-8"))

            try:
                req = QuotaRefreshRequest(**data)
            except ValidationError as ve:
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                errors = [{"field": str(e["loc"]), "message": e["msg"]} for e in ve.errors()]
                return self.finish(json.dumps({"error": "Validation failed", "details": errors}))

            self.log.info(
                f"[QUOTA] Refresh triggered: rule={req.rule_name}, action={req.action.value}, amount={req.amount}"
            )

            quota_manager = get_quota_manager()
            result = quota_manager.batch_refresh_quota(
                amount=req.amount,
                action=req.action.value,
                max_balance=req.max_balance,
                min_balance=req.min_balance,
                targets=req.targets.model_dump(exclude_none=True),
                rule_name=req.rule_name,
            )

            self.log.info(f"[QUOTA] Refresh complete: {result}")
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps(result))

        except json.JSONDecodeError:
            self.set_status(400)
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"error": "Invalid JSON"}))
        except Exception as e:
            self.log.error(f"[QUOTA] Refresh error: {e}")
            self.set_status(500)
            self.set_header("Content-Type", "application/json")
            self.finish(json.dumps({"error": "Internal server error"}))


# =============================================================================
# Configuration API Handlers
# =============================================================================


class AcceleratorsAPIHandler(APIHandler):
    """API endpoint for available accelerator options."""

    @web.authenticated
    async def get(self):
        """Get available accelerator options."""
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps({"accelerators": _handler_config["accelerator_options"]}))


class QuotaRatesAPIHandler(APIHandler):
    """API endpoint for quota rates configuration."""

    @web.authenticated
    async def get(self):
        """Get quota rates and configuration."""
        self.set_header("Content-Type", "application/json")
        self.finish(
            json.dumps(
                {
                    "enabled": _handler_config["quota_enabled"],
                    "rates": _handler_config["quota_rates"],
                    "minimum_to_start": _handler_config["minimum_quota_to_start"],
                }
            )
        )


class UserQuotaInfoHandler(APIHandler):
    """API endpoint for current user's quota info (non-admin)."""

    @web.authenticated
    async def get(self):
        """Get current user's quota balance and rates."""
        assert self.current_user is not None

        username = self.current_user.name
        quota_manager = get_quota_manager()
        balance = quota_manager.get_balance(username)
        has_unlimited = quota_manager.is_unlimited_in_db(username)

        self.set_header("Content-Type", "application/json")
        self.finish(
            json.dumps(
                {
                    "username": username,
                    "balance": balance,
                    "unlimited": has_unlimited,
                    "rates": _handler_config["quota_rates"],
                    "enabled": _handler_config["quota_enabled"],
                }
            )
        )


class ResourcesAPIHandler(APIHandler):
    """API endpoint for available resources with metadata."""

    @web.authenticated
    async def get(self):
        """Get all available resources with metadata.

        Note: Access control is handled by the spawner via window.AVAILABLE_RESOURCES
        injected into the template. This API returns all configured resources.
        """
        from core.config import HubConfig

        config = HubConfig.get()

        # Return all configured resources - access control is done client-side
        # based on spawner-injected window.AVAILABLE_RESOURCES
        available_resources = set(config.resources.images.keys())

        # Build response
        resources_list = []
        groups_dict: dict[str, list[dict]] = {}

        for key in sorted(available_resources):
            image = config.get_resource_image(key)
            requirements = config.get_resource_requirements(key)
            metadata = config.get_resource_metadata(key)

            if not image:
                continue

            resource_data: dict[str, Any] = {
                "key": key,
                "image": image,
                "requirements": requirements.model_dump(by_alias=True, exclude_none=True)
                if requirements
                else {"cpu": "2", "memory": "4Gi"},
            }

            if metadata:
                resource_data["metadata"] = metadata.model_dump(exclude_none=True)
                group_name = metadata.group or "OTHERS"
            else:
                group_name = "OTHERS"

            resources_list.append(resource_data)

            if group_name not in groups_dict:
                groups_dict[group_name] = []
            groups_dict[group_name].append(resource_data)

        # Build groups list - sort alphabetically, but put OTHERS last
        groups_list = []
        sorted_group_names = sorted(groups_dict.keys(), key=lambda x: (x == "OTHERS", x))
        for group_name in sorted_group_names:
            groups_list.append(
                {
                    "name": group_name,
                    "displayName": group_name.replace("_", " ").title(),
                    "resources": groups_dict[group_name],
                }
            )

        self.set_header("Content-Type", "application/json")
        self.finish(
            json.dumps(
                {
                    "resources": resources_list,
                    "groups": groups_list,
                    "acceleratorKeys": list(config.accelerators.keys()),
                }
            )
        )


# =============================================================================
# Handler Registration
# =============================================================================


def get_handlers() -> list[tuple[str, type]]:
    """
    Get all handlers to register with JupyterHub.

    Returns:
        List of (route, handler_class) tuples
    """
    return [
        # Password management
        (r"/auth/change-password", ChangePasswordHandler),
        (r"/auth/check-force-password-change", CheckForcePasswordChangeHandler),
        (r"/admin/reset-password", AdminResetPasswordHandler),
        # Admin UI
        (r"/admin/users", AdminUIHandler),
        (r"/admin/groups", AdminUIHandler),
        (r"/admin/api/set-password", AdminAPISetPasswordHandler),
        (r"/admin/api/generate-password", AdminAPIGeneratePasswordHandler),
        # Accelerator info API
        (r"/api/accelerators", AcceleratorsAPIHandler),
        # Resources API
        (r"/api/resources", ResourcesAPIHandler),
        # Quota management API
        (r"/admin/api/quota/?", QuotaAPIHandler),
        (r"/admin/api/quota/batch", QuotaBatchAPIHandler),
        (r"/admin/api/quota/refresh", QuotaRefreshHandler),
        (r"/admin/api/quota/([^/]+)", QuotaAPIHandler),
        (r"/api/quota/rates", QuotaRatesAPIHandler),
        (r"/api/quota/me", UserQuotaInfoHandler),
    ]


__all__ = [
    # Password handlers
    "CheckForcePasswordChangeHandler",
    "ChangePasswordHandler",
    "AdminResetPasswordHandler",
    # Admin UI handlers
    "AdminUIHandler",
    "AdminAPISetPasswordHandler",
    "AdminAPIGeneratePasswordHandler",
    # Quota handlers
    "QuotaAPIHandler",
    "QuotaBatchAPIHandler",
    "QuotaRefreshHandler",
    # Config API handlers
    "AcceleratorsAPIHandler",
    "QuotaRatesAPIHandler",
    "UserQuotaInfoHandler",
    "ResourcesAPIHandler",
    # Configuration
    "configure_handlers",
    # Registration
    "get_handlers",
]
