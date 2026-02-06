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
Quota SQLAlchemy ORM Models

Database models for quota management.
Uses the shared JupyterHub database with prefixed table names.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, func

from core.database import Base


class UserQuota(Base):
    """User quota balance table."""

    __tablename__ = "quota_user_quota"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, unique=True, index=True)
    balance = Column(Integer, nullable=False, default=0)
    unlimited = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class QuotaTransaction(Base):
    """Quota transaction audit log."""

    __tablename__ = "quota_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String(50), nullable=False)
    resource_type = Column(String(100))
    description = Column(Text)
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now(), index=True)
    created_by = Column(String(255))


class UsageSession(Base):
    """Usage session tracking."""

    __tablename__ = "quota_usage_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration_minutes = Column(Integer)
    quota_consumed = Column(Integer)
    status = Column(String(20), default="active", index=True)
    created_at = Column(DateTime, default=func.now())


# Add composite index for status queries
Index("idx_usage_sessions_username_status", UsageSession.username, UsageSession.status)
