#!/usr/bin/env python3
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
JupyterHub User Management Script

This script provides batch operations for managing JupyterHub Native Authenticator users
via the JupyterHub REST API.

Features:
- Create users in batch from CSV/Excel files
- Set default passwords for users (with optional force change on first login)
- Delete users in batch
- List all users
- Export user list to CSV/Excel

Requirements:
- pandas
- openpyxl
- requests

Environment Variables:
- JUPYTERHUB_URL: JupyterHub base URL (e.g., https://your-hub.example.com)
- JUPYTERHUB_TOKEN: Admin API token

Usage:
    # Create users from file (with optional password column)
    python manage_users.py create users.csv

    # Set passwords for users (requires kubectl access)
    python manage_users.py set-passwords users.csv

    # Delete users from file
    python manage_users.py delete remove_list.csv

    # List all users
    python manage_users.py list

    # Export users to file
    python manage_users.py export backup.xlsx

CSV File Format:
    username,password,admin
    student01,defaultpass123,false
    student02,defaultpass123,false
    admin01,adminpass456,true

If password column is missing, passwords will be auto-generated.
"""

import argparse
import os
import secrets
import string
import subprocess
import sys

import pandas as pd
import requests


class JupyterHubUserManager:
    """JupyterHub user management via REST API"""

    def __init__(self, hub_url: str, api_token: str):
        """
        Initialize the user manager.

        Args:
            hub_url: JupyterHub base URL (e.g., http://localhost:30890)
            api_token: Admin API token
        """
        self.hub_url = hub_url.rstrip("/")
        self.api_url = f"{self.hub_url}/hub/api"
        self.headers = {"Authorization": f"token {api_token}", "Content-Type": "application/json"}

    @staticmethod
    def normalize_username(username: str) -> str:
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
        return username.strip().lower()

    def _check_connection(self) -> bool:
        """Check if connection to JupyterHub is working"""
        try:
            response = requests.get(f"{self.api_url}/", headers=self.headers)
            if response.status_code == 200:
                print(f"✅ Connected to JupyterHub at {self.hub_url}")
                return True
            else:
                print(f"❌ Connection failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def list_users(self) -> list[dict]:
        """
        Get list of all users.

        Returns:
            List of user dictionaries
        """
        try:
            response = requests.get(f"{self.api_url}/users", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching users: {e}")
            return []

    def create_user(self, username: str, admin: bool = False) -> bool:
        """
        Create a single user.

        Args:
            username: Username to create
            admin: Whether user should be admin

        Returns:
            True if successful, False otherwise
        """
        username = self.normalize_username(username)
        try:
            data = {"admin": admin}
            response = requests.post(f"{self.api_url}/users/{username}", headers=self.headers, json=data)

            if response.status_code in [201, 200]:
                print(f"  ✅ Created user: {username} (admin={admin})")
                return True
            elif response.status_code == 409:
                print(f"  ⚠️  User already exists: {username}")
                return False
            else:
                print(f"  ❌ Failed to create {username}: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error creating user {username}: {e}")
            return False

    def delete_user(self, username: str) -> bool:
        """
        Delete a single user.

        Args:
            username: Username to delete

        Returns:
            True if successful, False otherwise
        """
        username = self.normalize_username(username)
        try:
            response = requests.delete(f"{self.api_url}/users/{username}", headers=self.headers)

            if response.status_code in [204, 200]:
                print(f"  ✅ Deleted user: {username}")
                return True
            elif response.status_code == 404:
                print(f"  ⚠️  User not found: {username}")
                return False
            else:
                print(f"  ❌ Failed to delete {username}: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error deleting user {username}: {e}")
            return False

    def create_users_batch(self, users: list[dict]) -> dict[str, int]:
        """
        Create multiple users in batch.

        Args:
            users: List of user dicts with 'username' and optional 'admin' fields

        Returns:
            Dictionary with success/fail counts
        """
        results = {"success": 0, "failed": 0, "existing": 0}

        print(f"\n🔄 Creating {len(users)} users...")

        for user in users:
            username = user.get("username", "").strip()
            if not username:
                continue

            admin = str(user.get("admin", "false")).lower() in ["true", "1", "yes"]

            result = self.create_user(username, admin)
            if result:
                results["success"] += 1
            else:
                # Check if user already exists
                user_info = self.get_user(username)
                if user_info:
                    results["existing"] += 1
                else:
                    results["failed"] += 1

        return results

    def delete_users_batch(self, usernames: list[str]) -> dict[str, int]:
        """
        Delete multiple users in batch.

        Args:
            usernames: List of usernames to delete

        Returns:
            Dictionary with success/fail counts
        """
        results = {"success": 0, "failed": 0, "not_found": 0}

        print(f"\n🔄 Deleting {len(usernames)} users...")

        for username in usernames:
            username = username.strip()
            if not username:
                continue

            # Check if user exists first
            user_info = self.get_user(username)
            if not user_info:
                print(f"  ⚠️  User not found: {username}")
                results["not_found"] += 1
                continue

            result = self.delete_user(username)
            if result:
                results["success"] += 1
            else:
                results["failed"] += 1

        return results

    def get_user(self, username: str) -> dict | None:
        """
        Get information about a specific user.

        Args:
            username: Username to query

        Returns:
            User info dict or None if not found
        """
        username = self.normalize_username(username)
        try:
            response = requests.get(f"{self.api_url}/users/{username}", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def set_admin(self, username: str, admin: bool = True) -> bool:
        """
        Set or remove admin privileges for a user.

        Args:
            username: Username to modify
            admin: True to grant admin, False to revoke

        Returns:
            True if successful, False otherwise
        """
        username = self.normalize_username(username)
        try:
            response = requests.patch(f"{self.api_url}/users/{username}", headers=self.headers, json={"admin": admin})

            if response.status_code == 200:
                action = "granted" if admin else "revoked"
                print(f"  ✅ Admin {action} for: {username}")
                return True
            elif response.status_code == 404:
                print(f"  ❌ User not found: {username}")
                return False
            else:
                print(f"  ❌ Failed to modify {username}: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error modifying user {username}: {e}")
            return False


def load_users_from_file(filepath: str) -> list[dict]:
    """
    Load users from CSV or Excel file.

    File must have 'username' column, and optionally 'admin' column.

    Args:
        filepath: Path to CSV or Excel file

    Returns:
        List of user dictionaries
    """
    try:
        if filepath.endswith(".xlsx") or filepath.endswith(".xls"):
            df = pd.read_excel(filepath)
        else:
            df = pd.read_csv(filepath)

        if "username" not in df.columns:
            print("❌ Error: File must contain 'username' column")
            sys.exit(1)

        # Convert to list of dicts
        users = df.to_dict("records")

        # Clean up NaN values
        for user in users:
            if pd.isna(user.get("admin")):
                user["admin"] = False

        return users

    except Exception as e:
        print(f"❌ Error loading file: {e}")
        sys.exit(1)


def save_users_to_file(users: list[dict], filepath: str):
    """
    Save users to CSV or Excel file.

    Args:
        users: List of user dictionaries
        filepath: Output file path
    """
    try:
        # Extract relevant fields
        user_data = []
        for user in users:
            user_data.append(
                {
                    "username": user.get("name", ""),
                    "admin": user.get("admin", False),
                    "created": user.get("created", ""),
                    "last_activity": user.get("last_activity", ""),
                }
            )

        df = pd.DataFrame(user_data)

        if filepath.endswith(".xlsx") or filepath.endswith(".xls"):
            df.to_excel(filepath, index=False)
        else:
            df.to_csv(filepath, index=False)

        print(f"✅ Saved {len(users)} users to {filepath}")

    except Exception as e:
        print(f"❌ Error saving file: {e}")
        sys.exit(1)


def cmd_create(args, manager: JupyterHubUserManager):
    """Create users from file"""
    users = load_users_from_file(args.file)
    print(f"📄 Loaded {len(users)} users from {args.file}")

    results = manager.create_users_batch(users)

    print("\n" + "=" * 50)
    print("📊 Results:")
    print(f"  ✅ Created: {results['success']}")
    print(f"  ⚠️  Already exist: {results['existing']}")
    print(f"  ❌ Failed: {results['failed']}")
    print("=" * 50)


def cmd_delete(args, manager: JupyterHubUserManager):
    """Delete users from file"""
    users = load_users_from_file(args.file)
    usernames = [u["username"] for u in users if u.get("username")]

    print(f"📄 Loaded {len(usernames)} users from {args.file}")

    # Confirmation prompt
    if not args.yes:
        response = input(f"⚠️  Are you sure you want to delete {len(usernames)} users? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Operation cancelled")
            return

    results = manager.delete_users_batch(usernames)

    print("\n" + "=" * 50)
    print("📊 Results:")
    print(f"  ✅ Deleted: {results['success']}")
    print(f"  ⚠️  Not found: {results['not_found']}")
    print(f"  ❌ Failed: {results['failed']}")
    print("=" * 50)


def cmd_list(args, manager: JupyterHubUserManager):
    """List all users"""
    users = manager.list_users()

    if not users:
        print("No users found")
        return

    print(f"\n📋 Total users: {len(users)}\n")
    print(f"{'Username':<20} {'Admin':<10} {'Last Activity':<25}")
    print("-" * 60)

    for user in users:
        username = user.get("name", "")
        admin = "✓" if user.get("admin", False) else ""
        last_activity = user.get("last_activity", None)

        if last_activity is None or last_activity == "":
            last_activity = "Never"
        elif last_activity != "Never":
            # Truncate timestamp for display
            last_activity = last_activity[:19].replace("T", " ")

        print(f"{username:<20} {admin:<10} {last_activity:<25}")


def cmd_export(args, manager: JupyterHubUserManager):
    """Export users to file"""
    users = manager.list_users()

    if not users:
        print("No users to export")
        return

    save_users_to_file(users, args.file)


def cmd_set_admin(args, manager: JupyterHubUserManager):
    """Set or revoke admin privileges"""
    admin = not args.revoke

    if args.file:
        # Batch mode from file
        users = load_users_from_file(args.file)
        usernames = [u["username"] for u in users if u.get("username")]
        print(f"📄 Loaded {len(usernames)} users from {args.file}")
    else:
        # Single user mode
        usernames = args.users

    if not usernames:
        print("❌ No users specified")
        return

    action = "Revoking" if args.revoke else "Granting"
    print(f"\n🔄 {action} admin privileges for {len(usernames)} users...")

    results = {"success": 0, "failed": 0}
    for username in usernames:
        username = username.strip()
        if not username:
            continue

        if manager.set_admin(username, admin):
            results["success"] += 1
        else:
            results["failed"] += 1

    print("\n" + "=" * 50)
    print("📊 Results:")
    print(f"  ✅ Success: {results['success']}")
    print(f"  ❌ Failed: {results['failed']}")
    print("=" * 50)


def generate_password(length: int = 12) -> str:
    """Generate a random password"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def set_password_in_pod(username: str, password: str, force_change: bool = True, namespace: str = "jupyterhub") -> bool:
    """
    Set password for a user by executing Python code in the hub pod.

    Args:
        username: Username (without prefix)
        password: Password to set
        force_change: If True, mark user for forced password change
        namespace: Kubernetes namespace

    Returns:
        True if successful
    """
    # Normalize username to lowercase
    username = username.strip().lower()

    # Python code to execute in the pod
    python_code = f'''
import dbm
import bcrypt

# Password database paths
passwords_dbm = "/srv/jupyterhub/passwords.dbm"
force_change_dbm = "/srv/jupyterhub/force_password_change.dbm"

username = "{username}"
password = "{password}"
force_change = {force_change}

# Set password
with dbm.open(passwords_dbm, "c", 0o600) as db:
    db[username] = bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt())

# Mark for forced password change
if force_change:
    with dbm.open(force_change_dbm, "c", 0o600) as db:
        db[username] = b"1"

print(f"OK: Password set for {{username}}")
'''

    try:
        result = subprocess.run(
            ["kubectl", "--namespace", namespace, "exec", "deployment/hub", "--", "python3", "-c", python_code],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and "OK:" in result.stdout:
            return True
        else:
            print(f"  Error: {result.stderr or result.stdout}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  Timeout setting password for {username}")
        return False
    except FileNotFoundError:
        print("  Error: kubectl not found. Please install kubectl.")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def cmd_set_passwords(args, manager: JupyterHubUserManager):
    """Set passwords for users from file"""
    users = load_users_from_file(args.file)
    print(f"📄 Loaded {len(users)} users from {args.file}")

    # Check if password column exists
    has_passwords = any(u.get("password") for u in users)
    if not has_passwords and not args.generate:
        print("⚠️  No password column found. Use --generate to auto-generate passwords.")
        print("   Or add a 'password' column to your file.")
        return

    results = {"success": 0, "failed": 0}
    output_data = []

    print(f"\n🔄 Setting passwords for {len(users)} users...")

    for user in users:
        username = user.get("username", "").strip()
        if not username:
            continue

        # Get or generate password
        password = user.get("password", "")
        if pd.isna(password) or not password:
            if args.generate:
                password = args.default_password if args.default_password else generate_password()
            else:
                print(f"  ⚠️  Skipping {username}: no password specified")
                continue

        password = str(password).strip()

        # Set password in pod
        force_change = not args.no_force_change
        success = set_password_in_pod(username, password, force_change, args.namespace)

        if success:
            print(f"  ✅ Set password for: {username}" + (" (force change)" if force_change else ""))
            results["success"] += 1
            output_data.append({"username": username, "password": password, "force_change": force_change})
        else:
            print(f"  ❌ Failed: {username}")
            results["failed"] += 1

    print("\n" + "=" * 50)
    print("📊 Results:")
    print(f"  ✅ Success: {results['success']}")
    print(f"  ❌ Failed: {results['failed']}")
    print("=" * 50)

    # Save output with passwords if requested
    if args.output and output_data:
        output_df = pd.DataFrame(output_data)
        if args.output.endswith(".xlsx"):
            output_df.to_excel(args.output, index=False)
        else:
            output_df.to_csv(args.output, index=False)
        print(f"\n📁 Saved passwords to: {args.output}")
        print("   ⚠️  Keep this file secure and delete after distributing passwords!")


def main():
    parser = argparse.ArgumentParser(
        description="JupyterHub User Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create users from CSV file
  python manage_users.py create users.csv

  # Grant admin privileges to users
  python manage_users.py set-admin teacher01 teacher02

  # Grant admin privileges from file
  python manage_users.py set-admin -f admins.csv

  # Revoke admin privileges
  python manage_users.py set-admin --revoke student01

  # Set passwords for users (with force change on first login)
  python manage_users.py set-passwords users.csv

  # Set same default password for all users
  python manage_users.py set-passwords users.csv --generate --default-password "Welcome123"

  # Set passwords without forcing change on first login
  python manage_users.py set-passwords users.csv --no-force-change

  # Delete users from file (with confirmation)
  python manage_users.py delete remove_list.xlsx

  # Delete users without confirmation
  python manage_users.py delete remove_list.csv --yes

  # List all users
  python manage_users.py list

  # Export users to Excel
  python manage_users.py export backup.xlsx

CSV File Format for set-passwords:
  username,password
  student01,defaultpass123
  student02,defaultpass123

Environment Variables:
  JUPYTERHUB_URL      JupyterHub base URL (default: http://localhost:30890)
  JUPYTERHUB_TOKEN    Admin API token (required)
        """,
    )

    parser.add_argument(
        "--url",
        default=os.environ.get("JUPYTERHUB_URL", "http://localhost:30890"),
        help="JupyterHub URL (default: $JUPYTERHUB_URL or http://localhost:30890)",
    )

    parser.add_argument(
        "--token", default=os.environ.get("JUPYTERHUB_TOKEN"), help="API token (default: $JUPYTERHUB_TOKEN)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create users from file")
    create_parser.add_argument("file", help="CSV or Excel file with user data")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete users from file")
    delete_parser.add_argument("file", help="CSV or Excel file with usernames")
    delete_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    # List command
    subparsers.add_parser("list", help="List all users")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export users to file")
    export_parser.add_argument("file", help="Output CSV or Excel file")

    # Set-admin command
    admin_parser = subparsers.add_parser("set-admin", help="Grant or revoke admin privileges")
    admin_parser.add_argument("users", nargs="*", help="Username(s) to modify")
    admin_parser.add_argument("--file", "-f", help="CSV or Excel file with usernames")
    admin_parser.add_argument("--revoke", "-r", action="store_true", help="Revoke admin privileges instead of granting")

    # Set-passwords command
    setpw_parser = subparsers.add_parser("set-passwords", help="Set default passwords for users (requires kubectl)")
    setpw_parser.add_argument("file", help="CSV or Excel file with user data")
    setpw_parser.add_argument(
        "--generate", "-g", action="store_true", help="Generate passwords for users without password column"
    )
    setpw_parser.add_argument("--default-password", "-p", help="Use this password for all users (with --generate)")
    setpw_parser.add_argument(
        "--no-force-change", action="store_true", help="Do not require password change on first login"
    )
    setpw_parser.add_argument("--output", "-o", help="Output file to save usernames and passwords")
    setpw_parser.add_argument(
        "--namespace", "-n", default="jupyterhub", help="Kubernetes namespace (default: jupyterhub)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Check for API token
    if not args.token:
        print("❌ Error: API token required")
        print("Set JUPYTERHUB_TOKEN environment variable or use --token")
        sys.exit(1)

    # Initialize manager
    manager = JupyterHubUserManager(args.url, args.token)

    # Check connection
    if not manager._check_connection():
        sys.exit(1)

    # Execute command
    if args.command == "create":
        cmd_create(args, manager)
    elif args.command == "delete":
        cmd_delete(args, manager)
    elif args.command == "list":
        cmd_list(args, manager)
    elif args.command == "export":
        cmd_export(args, manager)
    elif args.command == "set-admin":
        cmd_set_admin(args, manager)
    elif args.command == "set-passwords":
        cmd_set_passwords(args, manager)


if __name__ == "__main__":
    main()
