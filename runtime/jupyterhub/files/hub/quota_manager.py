# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# SPDX-License-Identifier: MIT

"""
Quota Manager Module for JupyterHub
Manages user quota balances and usage tracking for container time limits.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime


class QuotaManager:
    """Thread-safe quota management for JupyterHub users."""

    def __init__(self, db_path: str = "/srv/jupyterhub/quota.sqlite"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize the database schema if not exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(
                """
                -- User quota balances
                CREATE TABLE IF NOT EXISTS user_quota (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    balance INTEGER NOT NULL DEFAULT 0,
                    unlimited INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Quota transaction audit log
                CREATE TABLE IF NOT EXISTS quota_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    resource_type TEXT,
                    description TEXT,
                    balance_before INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                );

                -- Usage session tracking
                CREATE TABLE IF NOT EXISTS usage_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    duration_minutes INTEGER,
                    quota_consumed INTEGER,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_user_quota_username
                    ON user_quota(username);
                CREATE INDEX IF NOT EXISTS idx_quota_transactions_username
                    ON quota_transactions(username);
                CREATE INDEX IF NOT EXISTS idx_quota_transactions_created_at
                    ON quota_transactions(created_at);
                CREATE INDEX IF NOT EXISTS idx_usage_sessions_username
                    ON usage_sessions(username);
                CREATE INDEX IF NOT EXISTS idx_usage_sessions_status
                    ON usage_sessions(status);
            """
            )
            conn.commit()
            # Run migrations for existing databases
            self._migrate_db(conn)

    def _migrate_db(self, conn):
        """Run database migrations for schema updates."""
        cursor = conn.cursor()
        # Check if 'unlimited' column exists in user_quota
        cursor.execute("PRAGMA table_info(user_quota)")
        columns = [row[1] for row in cursor.fetchall()]
        if "unlimited" not in columns:
            cursor.execute("ALTER TABLE user_quota ADD COLUMN unlimited INTEGER NOT NULL DEFAULT 0")
            conn.commit()

    def get_balance(self, username: str) -> int:
        """Get user's current quota balance."""
        username = username.lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM user_quota WHERE username = ?", (username,))
            row = cursor.fetchone()
            return row["balance"] if row else 0

    def set_balance(self, username: str, amount: int, admin: str | None = None) -> int:
        """Set user's quota balance to a specific amount."""
        username = username.lower()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # Query balance directly within same connection to avoid race condition
            cursor.execute("SELECT balance FROM user_quota WHERE username = ?", (username,))
            row = cursor.fetchone()
            current = row["balance"] if row else 0

            cursor.execute(
                """
                INSERT INTO user_quota (username, balance)
                VALUES (?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    balance = excluded.balance,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (username, amount),
            )

            # Record transaction
            cursor.execute(
                """
                INSERT INTO quota_transactions
                (username, amount, transaction_type, balance_before,
                 balance_after, created_by, description)
                VALUES (?, ?, 'admin_set', ?, ?, ?, ?)
            """,
                (username, amount - current, current, amount, admin, f"Balance set to {amount}"),
            )

            conn.commit()
            return amount

    def add_quota(self, username: str, amount: int, admin: str | None = None, description: str | None = None) -> int:
        """Add quota to user's balance."""
        username = username.lower()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # Query balance directly within same connection to avoid race condition
            cursor.execute("SELECT balance FROM user_quota WHERE username = ?", (username,))
            row = cursor.fetchone()
            current = row["balance"] if row else 0
            new_balance = current + amount

            cursor.execute(
                """
                INSERT INTO user_quota (username, balance)
                VALUES (?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    balance = user_quota.balance + ?,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (username, amount, amount),
            )

            cursor.execute(
                """
                INSERT INTO quota_transactions
                (username, amount, transaction_type, balance_before,
                 balance_after, created_by, description)
                VALUES (?, ?, 'admin_add', ?, ?, ?, ?)
            """,
                (username, amount, current, new_balance, admin, description or f"Added {amount} quota"),
            )

            conn.commit()
            return new_balance

    def deduct_quota(
        self, username: str, amount: int, resource_type: str | None = None, description: str | None = None
    ) -> tuple[bool, int]:
        """
        Deduct quota from user's balance for usage.
        Returns (success, new_balance).
        """
        username = username.lower()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # Query balance directly within same connection to avoid race condition
            cursor.execute("SELECT balance FROM user_quota WHERE username = ?", (username,))
            row = cursor.fetchone()
            current = row["balance"] if row else 0

            if current < amount:
                return False, current

            new_balance = current - amount

            cursor.execute(
                """
                UPDATE user_quota
                SET balance = ?, updated_at = CURRENT_TIMESTAMP
                WHERE username = ?
            """,
                (new_balance, username),
            )

            cursor.execute(
                """
                INSERT INTO quota_transactions
                (username, amount, transaction_type, resource_type,
                 balance_before, balance_after, description)
                VALUES (?, ?, 'usage', ?, ?, ?, ?)
            """,
                (
                    username,
                    -amount,
                    resource_type,
                    current,
                    new_balance,
                    description or f"Usage deduction for {resource_type}",
                ),
            )

            conn.commit()
            return True, new_balance

    def is_unlimited_in_db(self, username: str) -> bool:
        """Check if user is marked as unlimited in the database."""
        username = username.lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT unlimited FROM user_quota WHERE username = ?", (username,))
            row = cursor.fetchone()
            return bool(row and row["unlimited"])

    def set_unlimited(self, username: str, unlimited: bool, admin: str | None = None) -> bool:
        """Set user's unlimited quota status in the database."""
        username = username.lower()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_quota (username, balance, unlimited)
                VALUES (?, 0, ?)
                ON CONFLICT(username) DO UPDATE SET
                    unlimited = excluded.unlimited,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (username, 1 if unlimited else 0),
            )

            # Record transaction
            action = "granted" if unlimited else "revoked"
            cursor.execute(
                """
                INSERT INTO quota_transactions
                (username, amount, transaction_type, balance_before,
                 balance_after, created_by, description)
                VALUES (?, 0, 'unlimited_change', 0, 0, ?, ?)
            """,
                (username, admin, f"Unlimited quota {action}"),
            )

            conn.commit()
            return unlimited

    def has_unlimited_quota(
        self,
        username: str,
        is_admin: bool = False,
        admins_unlimited: bool = True,
        unlimited_users: list[str] | None = None,
    ) -> bool:
        """
        Check if user has unlimited quota.
        Returns True if:
        - User is admin and admins_unlimited is True
        - User is in the unlimited_users config list
        - User is marked as unlimited in the database
        """
        username = username.lower()
        # Check config: admin unlimited
        if is_admin and admins_unlimited:
            return True
        # Check config: unlimited users list
        if unlimited_users and username in [u.lower() for u in unlimited_users]:
            return True
        # Check database
        return self.is_unlimited_in_db(username)

    def can_start_container(
        self,
        username: str,
        resource_type: str,
        duration_minutes: int,
        quota_rates: dict,
        is_admin: bool = False,
        admins_unlimited: bool = True,
        unlimited_users: list[str] | None = None,
    ) -> tuple[bool, str, int]:
        """
        Check if user has sufficient quota to start a container.
        Returns (can_start, message, estimated_cost).
        """
        username = username.lower()
        rate = quota_rates.get(resource_type, 1)
        estimated_cost = rate * duration_minutes

        # Check for unlimited quota
        if self.has_unlimited_quota(username, is_admin, admins_unlimited, unlimited_users):
            return True, "Unlimited quota", 0

        balance = self.get_balance(username)

        if balance < estimated_cost:
            return (
                False,
                f"Insufficient quota. Required: {estimated_cost}, Available: {balance}",
                estimated_cost,
            )

        return True, "Sufficient quota available", estimated_cost

    def start_usage_session(self, username: str, resource_type: str) -> int:
        """Start a new usage session and return session ID."""
        username = username.lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO usage_sessions
                (username, resource_type, start_time, status)
                VALUES (?, ?, CURRENT_TIMESTAMP, 'active')
            """,
                (username, resource_type),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def end_usage_session(self, session_id: int, quota_rates: dict) -> tuple[int, int]:
        """
        End a usage session and deduct quota.
        Returns (duration_minutes, quota_consumed).
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # Get session details
            cursor.execute(
                """
                SELECT username, resource_type, start_time
                FROM usage_sessions WHERE id = ? AND status = 'active'
            """,
                (session_id,),
            )
            session = cursor.fetchone()

            if not session:
                return 0, 0

            username = session["username"]
            resource_type = session["resource_type"]

            # Calculate duration
            start_time = datetime.fromisoformat(session["start_time"])
            duration = (datetime.now() - start_time).total_seconds() / 60
            duration_minutes = max(1, int(duration))  # Minimum 1 minute

            # Calculate quota consumed
            rate = quota_rates.get(resource_type, 1)
            quota_consumed = rate * duration_minutes

            # Update session status atomically (only if still active)
            cursor.execute(
                """
                UPDATE usage_sessions
                SET end_time = CURRENT_TIMESTAMP,
                    duration_minutes = ?,
                    quota_consumed = ?,
                    status = 'completed'
                WHERE id = ? AND status = 'active'
            """,
                (duration_minutes, quota_consumed, session_id),
            )

            # Check if session was actually updated (guard against race conditions)
            if cursor.rowcount == 0:
                return 0, 0

            # Inline quota deduction (avoid nested locking)
            cursor.execute("SELECT balance FROM user_quota WHERE username = ?", (username,))
            row = cursor.fetchone()
            current_balance = row["balance"] if row else 0
            new_balance = max(0, current_balance - quota_consumed)

            cursor.execute(
                """
                UPDATE user_quota
                SET balance = ?, updated_at = CURRENT_TIMESTAMP
                WHERE username = ?
            """,
                (new_balance, username),
            )

            # Record transaction
            cursor.execute(
                """
                INSERT INTO quota_transactions
                (username, amount, transaction_type, resource_type,
                 balance_before, balance_after, description)
                VALUES (?, ?, 'usage', ?, ?, ?, ?)
            """,
                (
                    username,
                    -quota_consumed,
                    resource_type,
                    current_balance,
                    new_balance,
                    f"Session {session_id}: {duration_minutes} minutes",
                ),
            )

            conn.commit()
            return duration_minutes, quota_consumed

    def get_active_session(self, username: str) -> dict | None:
        """Get user's active session if any."""
        username = username.lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, resource_type, start_time
                FROM usage_sessions
                WHERE username = ? AND status = 'active'
                ORDER BY start_time DESC
                LIMIT 1
            """,
                (username,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def cleanup_stale_sessions(self, max_duration_minutes: int = 480) -> list[dict]:
        """
        Clean up stale sessions that have been active too long.
        This handles cases where containers crashed or Hub restarted.

        Args:
            max_duration_minutes: Maximum session duration before considered stale (default 8 hours)

        Returns:
            List of cleaned up sessions with deducted quota
        """
        cleaned = []
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # Find stale active sessions
            cursor.execute(
                """
                SELECT id, username, resource_type, start_time
                FROM usage_sessions
                WHERE status = 'active'
                AND datetime(start_time, '+' || ? || ' minutes') < datetime('now')
            """,
                (max_duration_minutes,),
            )
            stale_sessions = cursor.fetchall()

            for session in stale_sessions:
                session_id = session["id"]
                username = session["username"]
                resource_type = session["resource_type"]
                start_time = datetime.fromisoformat(session["start_time"])

                # Calculate duration (cap at max_duration_minutes)
                duration = (datetime.now() - start_time).total_seconds() / 60
                duration_minutes = min(int(duration), max_duration_minutes)

                # Mark session as cleaned up
                cursor.execute(
                    """
                    UPDATE usage_sessions
                    SET end_time = CURRENT_TIMESTAMP,
                        duration_minutes = ?,
                        status = 'cleaned_up'
                    WHERE id = ?
                """,
                    (duration_minutes, session_id),
                )

                cleaned.append(
                    {
                        "session_id": session_id,
                        "username": username,
                        "resource_type": resource_type,
                        "duration_minutes": duration_minutes,
                    }
                )

                print(f"[QUOTA] Cleaned up stale session {session_id} for {username}: {duration_minutes} min")

            conn.commit()

        # Note: We don't deduct quota for cleaned up sessions to avoid double charging.
        # The session was likely interrupted abnormally.
        # If you want to charge for stale sessions, uncomment and modify the deduct_quota
        # call inside the loop above.

        return cleaned

    def get_active_sessions_count(self) -> int:
        """Get count of currently active sessions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM usage_sessions WHERE status = 'active'")
            row = cursor.fetchone()
            return row["count"] if row else 0

    def get_user_transactions(self, username: str, limit: int = 50) -> list[dict]:
        """Get user's transaction history."""
        username = username.lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM quota_transactions
                WHERE username = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (username, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_balances(self) -> list[dict]:
        """Get all user balances for admin."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT username, balance, unlimited, updated_at
                FROM user_quota
                ORDER BY username
            """
            )
            return [dict(row) for row in cursor.fetchall()]

    def batch_set_quota(self, users: list[tuple[str, int]], admin: str | None = None) -> dict:
        """Set quota for multiple users at once."""
        results = {"success": 0, "failed": 0}
        for username, amount in users:
            try:
                self.set_balance(username, amount, admin)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                print(f"Failed to set quota for {username}: {e}")
        return results

    def _match_targets(self, username: str, balance: int, is_unlimited: bool, targets: dict) -> bool:
        """
        Check if user matches the target criteria.
        All conditions are AND-ed together.
        """
        # includeUnlimited: include unlimited users (default: false)
        if is_unlimited and not targets.get("includeUnlimited", False):
            return False

        # balanceBelow: only if balance < this value
        balance_below = targets.get("balanceBelow")
        if balance_below is not None and balance >= balance_below:
            return False

        # balanceAbove: only if balance > this value
        balance_above = targets.get("balanceAbove")
        if balance_above is not None and balance <= balance_above:
            return False

        # includeUsers: only these users (empty = no restriction)
        include_users = targets.get("includeUsers", [])
        if include_users and username not in [u.lower() for u in include_users]:
            return False

        # excludeUsers: exclude these users
        exclude_users = targets.get("excludeUsers", [])
        if username in [u.lower() for u in exclude_users]:
            return False

        pattern = targets.get("usernamePattern")
        if pattern:
            try:
                if not re.match(pattern, username, re.IGNORECASE):
                    return False
            except re.error:
                return False

        return True

    def batch_refresh_quota(
        self,
        amount: int,
        action: str = "add",
        max_balance: int | None = None,
        min_balance: int | None = None,
        targets: dict | None = None,
        rule_name: str = "manual",
    ) -> dict:
        """
        Batch refresh quota for users with flexible targeting and action modes.

        Args:
            amount: Quota amount (positive = add, negative = deduct for "add" action)
            action: Operation mode - "add" (default) or "set"
            max_balance: Maximum balance cap for positive add (None = no cap)
            min_balance: Minimum balance floor for negative add (None = 0)
            targets: Targeting criteria dict with keys:
                - includeUnlimited: bool (default False)
                - balanceBelow: int (only if balance < this)
                - balanceAbove: int (only if balance > this)
                - includeUsers: list[str] (only these users)
                - excludeUsers: list[str] (exclude these users)
                - usernamePattern: str (regex pattern)
            rule_name: Name of the refresh rule (for logging)

        Returns:
            {"users_updated": N, "total_change": M, "skipped": K, "action": str, "rule_name": str}
        """
        if targets is None:
            targets = {}
        if min_balance is None:
            min_balance = 0

        # Validate action
        if action not in ("add", "set"):
            return {"error": f"Invalid action: {action}. Use 'add' or 'set'.", "rule_name": rule_name}

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # Get all users with quota records
            cursor.execute("SELECT username, balance, unlimited FROM user_quota")
            users = cursor.fetchall()

            users_updated = 0
            total_change = 0
            skipped = 0

            for user in users:
                username = user["username"]
                current = user["balance"]
                is_unlimited = bool(user["unlimited"])

                # Check if user matches target criteria
                if not self._match_targets(username, current, is_unlimited, targets):
                    skipped += 1
                    continue

                # Calculate new balance based on action
                if action == "add":
                    new_balance = current + amount
                    # Apply cap/floor based on direction
                    if amount > 0 and max_balance is not None:
                        new_balance = min(new_balance, max_balance)
                    elif amount < 0:
                        new_balance = max(new_balance, min_balance)
                elif action == "set":
                    new_balance = amount
                else:
                    skipped += 1
                    continue

                # Skip if no change
                if new_balance == current:
                    skipped += 1
                    continue

                change = new_balance - current

                # Update balance
                cursor.execute(
                    "UPDATE user_quota SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
                    (new_balance, username),
                )

                # Record transaction with rule name and action
                cursor.execute(
                    """
                    INSERT INTO quota_transactions
                    (username, amount, transaction_type, balance_before, balance_after, description)
                    VALUES (?, ?, 'auto_refresh', ?, ?, ?)
                    """,
                    (username, change, current, new_balance, f"Auto {action}: {rule_name}"),
                )

                users_updated += 1
                total_change += change

            conn.commit()
            print(
                f"[QUOTA] Refresh '{rule_name}' ({action}): {users_updated} users updated, {skipped} skipped, change={total_change:+d}"
            )
            return {
                "users_updated": users_updated,
                "total_change": total_change,
                "skipped": skipped,
                "action": action,
                "rule_name": rule_name,
            }


# Global instance
_quota_manager: QuotaManager | None = None


def get_quota_manager() -> QuotaManager:
    """Get the global QuotaManager instance."""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager
