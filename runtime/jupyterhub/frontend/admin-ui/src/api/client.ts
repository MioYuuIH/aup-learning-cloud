// Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

import type { User, UsersResponse, HubInfo, SetPasswordRequest, Group } from '../types';

// Get base URL from window.jhdata
function getBaseUrl(): string {
  // JupyterHub sets this in window.jhdata
  const jhdata = window.jhdata ?? {};
  return jhdata.base_url ?? '/hub/';
}

// Get XSRF token from window.jhdata
function getXsrfToken(): string {
  // Try window.jhdata first (most reliable)
  const jhdata = window.jhdata ?? {};
  if (jhdata.xsrf_token) {
    return jhdata.xsrf_token;
  }
  // Fallback to cookie
  const match = document.cookie.match(/(?:^|;\s*)_xsrf=([^;]+)/);
  return match ? match[1] : '';
}

// Common fetch options
function getHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    'X-XSRFToken': getXsrfToken(),
  };
}

// Generic API request handler
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}api${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      ...getHeaders(),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `API Error: ${response.status}`);
  }

  // Handle empty responses (202 Accepted, 204 No Content)
  if (response.status === 202 || response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ============ Hub API ============

export async function getHubInfo(): Promise<HubInfo> {
  return apiRequest<HubInfo>('/info');
}

// ============ Users API ============

export async function getUsers(offset = 0, limit = 100): Promise<UsersResponse> {
  return apiRequest<UsersResponse>(`/users?offset=${offset}&limit=${limit}&include_stopped_servers=true`);
}

export async function getUser(username: string): Promise<User> {
  return apiRequest<User>(`/users/${encodeURIComponent(username)}`);
}

export async function createUser(username: string, admin = false): Promise<User> {
  return apiRequest<User>(`/users/${encodeURIComponent(username)}`, {
    method: 'POST',
    body: JSON.stringify({ admin }),
  });
}

export async function createUsers(usernames: string[], admin = false): Promise<User[]> {
  return apiRequest<User[]>('/users', {
    method: 'POST',
    body: JSON.stringify({ usernames, admin }),
  });
}

export async function deleteUser(username: string): Promise<void> {
  return apiRequest<void>(`/users/${encodeURIComponent(username)}`, {
    method: 'DELETE',
  });
}

export async function updateUser(username: string, data: { admin?: boolean; name?: string; groups?: string[] }): Promise<User> {
  return apiRequest<User>(`/users/${encodeURIComponent(username)}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

// ============ Server API ============

export async function startServer(username: string, serverName = ''): Promise<void> {
  const endpoint = serverName
    ? `/users/${encodeURIComponent(username)}/servers/${encodeURIComponent(serverName)}`
    : `/users/${encodeURIComponent(username)}/server`;
  return apiRequest<void>(endpoint, {
    method: 'POST',
  });
}

export async function stopServer(username: string, serverName = ''): Promise<void> {
  const endpoint = serverName
    ? `/users/${encodeURIComponent(username)}/servers/${encodeURIComponent(serverName)}`
    : `/users/${encodeURIComponent(username)}/server`;
  return apiRequest<void>(endpoint, {
    method: 'DELETE',
  });
}

// ============ Custom Password API ============
// These endpoints are custom additions to JupyterHub

export async function setPassword(data: SetPasswordRequest): Promise<{ message: string }> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}admin/api/set-password`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `API Error: ${response.status}`);
  }

  return response.json();
}

export async function generatePassword(): Promise<{ password: string }> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}admin/api/generate-password`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    throw new Error('Failed to generate password');
  }

  return response.json();
}

// ============ Groups API ============

export async function getGroups(): Promise<Group[]> {
  const response = await apiRequest<Record<string, Group>>('/groups');
  // Convert object to array
  return Object.values(response);
}

export async function getGroup(groupName: string): Promise<Group> {
  return apiRequest<Group>(`/groups/${encodeURIComponent(groupName)}`);
}

export async function createGroup(groupName: string): Promise<Group> {
  return apiRequest<Group>(`/groups/${encodeURIComponent(groupName)}`, {
    method: 'POST',
  });
}

export async function deleteGroup(groupName: string): Promise<void> {
  return apiRequest<void>(`/groups/${encodeURIComponent(groupName)}`, {
    method: 'DELETE',
  });
}

export async function updateGroup(groupName: string, data: { properties?: Record<string, unknown> }): Promise<Group> {
  return apiRequest<Group>(`/groups/${encodeURIComponent(groupName)}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function addUserToGroup(groupName: string, username: string): Promise<Group> {
  return apiRequest<Group>(`/groups/${encodeURIComponent(groupName)}/users`, {
    method: 'POST',
    body: JSON.stringify({ users: [username] }),
  });
}

export async function removeUserFromGroup(groupName: string, username: string): Promise<Group> {
  return apiRequest<Group>(`/groups/${encodeURIComponent(groupName)}/users`, {
    method: 'DELETE',
    body: JSON.stringify({ users: [username] }),
  });
}

// ============ Quota API ============

export interface UserQuota {
  username: string;
  balance: number;
  unlimited?: boolean | number;
  updated_at?: string;
  recent_transactions?: QuotaTransaction[];
}

export interface QuotaTransaction {
  id: number;
  username: string;
  amount: number;
  transaction_type: string;
  resource_type?: string;
  description?: string;
  balance_before: number;
  balance_after: number;
  created_at: string;
  created_by?: string;
}

export interface QuotaRates {
  rates: Record<string, number>;
  minimum_to_start: number;
  enabled: boolean;
}

export async function getAllQuota(): Promise<{ users: UserQuota[] }> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}admin/api/quota`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to get quota');
  }

  return response.json();
}

export async function getUserQuota(username: string): Promise<UserQuota> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}admin/api/quota/${encodeURIComponent(username)}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to get user quota');
  }

  return response.json();
}

export async function setUserQuota(
  username: string,
  amount: number,
  action: 'set' | 'add' | 'deduct' = 'set',
  description?: string
): Promise<UserQuota> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}admin/api/quota/${encodeURIComponent(username)}`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ action, amount, description }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to set quota');
  }

  return response.json();
}

export async function batchSetQuota(
  users: Array<{ username: string; amount: number }>
): Promise<{ success: number; failed: number }> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}admin/api/quota/batch`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ users }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to batch set quota');
  }

  return response.json();
}

export async function setUserUnlimited(
  username: string,
  unlimited: boolean
): Promise<UserQuota> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}admin/api/quota/${encodeURIComponent(username)}`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ action: 'set_unlimited', unlimited }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to set unlimited status');
  }

  return response.json();
}

export async function getQuotaRates(): Promise<QuotaRates> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}api/quota/rates`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    throw new Error('Failed to get quota rates');
  }

  return response.json();
}
