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
First Use Authenticator

Password-based authenticator with forced password change support.
"""

from __future__ import annotations

from firstuseauthenticator import FirstUseAuthenticator


class CustomFirstUseAuthenticator(FirstUseAuthenticator):
    """
    FirstUseAuthenticator with forced password change support.

    Users set their password on first login, and admins can force
    password changes.
    """

    prefix = ""
    service_name = "Native"
    login_service = "Native"
    create_users = False
    dbm_path = "/srv/jupyterhub/passwords.dbm"
    force_change_dbm_path = "/srv/jupyterhub/force_password_change.dbm"

    def normalize_username(self, username):
        """Normalize username to lowercase."""
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
