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

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Button, Form, InputGroup, Badge, Spinner, Alert, ButtonGroup } from 'react-bootstrap';
import type { User } from '../types';
import * as api from '../api/client';
import { CreateUserModal } from '../components/CreateUserModal';
import { SetPasswordModal } from '../components/SetPasswordModal';
import { EditUserModal } from '../components/EditUserModal';

export function UserList() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [selectedUsers, setSelectedUsers] = useState<Set<string>>(new Set());
  const [onlyActiveServers, setOnlyActiveServers] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(50);

  const jhdata = (window as any).jhdata || {};
  const baseUrl = jhdata.base_url || '/hub/';

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getUsers(0, 1000);
      setUsers(response.items || response as unknown as User[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.name.toLowerCase().includes(search.toLowerCase());
    const matchesActiveFilter = !onlyActiveServers || user.server !== null;
    return matchesSearch && matchesActiveFilter;
  });

  // Pagination
  const totalPages = Math.ceil(filteredUsers.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedUsers = filteredUsers.slice(startIndex, startIndex + itemsPerPage);

  // Filter out GitHub users for password operations
  const isNativeUser = (user: User) => !user.name.startsWith('github:');

  const handleStartServer = async (user: User) => {
    try {
      setActionLoading(`start-${user.name}`);
      await api.startServer(user.name);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start server');
    } finally {
      setActionLoading(null);
    }
  };

  const handleStopServer = async (user: User) => {
    try {
      setActionLoading(`stop-${user.name}`);
      await api.stopServer(user.name);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop server');
    } finally {
      setActionLoading(null);
    }
  };

  const handleStartAll = async () => {
    const usersToStart = selectedUsers.size > 0
      ? filteredUsers.filter(u => selectedUsers.has(u.name) && !u.server)
      : filteredUsers.filter(u => !u.server);

    setActionLoading('start-all');
    for (const user of usersToStart) {
      try {
        await api.startServer(user.name);
      } catch (err) {
        console.error(`Failed to start server for ${user.name}:`, err);
      }
    }
    setActionLoading(null);
    await loadUsers();
  };

  const handleStopAll = async () => {
    const usersToStop = selectedUsers.size > 0
      ? filteredUsers.filter(u => selectedUsers.has(u.name) && u.server)
      : filteredUsers.filter(u => u.server);

    setActionLoading('stop-all');
    for (const user of usersToStop) {
      try {
        await api.stopServer(user.name);
      } catch (err) {
        console.error(`Failed to stop server for ${user.name}:`, err);
      }
    }
    setActionLoading(null);
    await loadUsers();
  };

  const handleShutdownHub = () => {
    if (window.confirm('Are you sure you want to shutdown the hub? This will stop all services.')) {
      window.location.href = `${baseUrl}shutdown`;
    }
  };

  const toggleUserSelection = (username: string) => {
    const newSelected = new Set(selectedUsers);
    if (newSelected.has(username)) {
      newSelected.delete(username);
    } else {
      newSelected.add(username);
    }
    setSelectedUsers(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedUsers.size === paginatedUsers.length) {
      setSelectedUsers(new Set());
    } else {
      setSelectedUsers(new Set(paginatedUsers.map(u => u.name)));
    }
  };

  const openPasswordModal = (user: User) => {
    setSelectedUser(user);
    setShowPasswordModal(true);
  };

  const openEditModal = (user: User) => {
    setSelectedUser(user);
    setShowEditModal(true);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  };

  const getServerStatus = (user: User) => {
    if (user.pending) {
      return <Badge bg="warning">{user.pending}</Badge>;
    }
    if (user.server) {
      return <Badge bg="success">Running</Badge>;
    }
    return <Badge bg="secondary">Stopped</Badge>;
  };

  if (loading) {
    return (
      <div className="text-center py-5">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    );
  }

  return (
    <div>
      {/* Top Controls */}
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div className="d-flex gap-2">
          <Button variant="primary" onClick={() => setShowCreateModal(true)}>
            Add Users
          </Button>
          <Button
            variant="primary"
            onClick={handleStartAll}
            disabled={actionLoading === 'start-all'}
          >
            {actionLoading === 'start-all' ? <Spinner animation="border" size="sm" /> : 'Start All'}
          </Button>
          <Button
            variant="warning"
            onClick={handleStopAll}
            disabled={actionLoading === 'stop-all'}
          >
            {actionLoading === 'stop-all' ? <Spinner animation="border" size="sm" /> : 'Stop All'}
          </Button>
          <Button
            variant="danger"
            onClick={handleShutdownHub}
          >
            Shutdown Hub
          </Button>
        </div>
        <div className="d-flex gap-2">
          <Button
            variant="outline-secondary"
            onClick={() => navigate('/groups')}
          >
            Manage Groups
          </Button>
          <Button
            variant="outline-secondary"
            as="a"
            href={`${baseUrl}admin`}
          >
            Legacy Admin
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Search and Filter */}
      <div className="d-flex gap-2 mb-3">
        <InputGroup style={{ maxWidth: '400px' }}>
          <InputGroup.Text><i className="bi bi-search"></i></InputGroup.Text>
          <Form.Control
            placeholder="Search users..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
          />
          {search && (
            <Button variant="outline-secondary" onClick={() => setSearch('')}>
              Clear
            </Button>
          )}
        </InputGroup>

        <Form.Check
          type="checkbox"
          label="only active servers"
          checked={onlyActiveServers}
          onChange={(e) => {
            setOnlyActiveServers(e.target.checked);
            setCurrentPage(1);
          }}
          className="d-flex align-items-center"
        />
      </div>

      {/* User Table */}
      <Table striped hover responsive>
        <thead>
          <tr>
            <th style={{ width: '40px' }}>
              <Form.Check
                type="checkbox"
                checked={selectedUsers.size === paginatedUsers.length && paginatedUsers.length > 0}
                onChange={toggleSelectAll}
              />
            </th>
            <th>User</th>
            <th>Admin</th>
            <th>Server</th>
            <th>Last Activity</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {paginatedUsers.map((user) => (
            <tr key={user.name}>
              <td>
                <Form.Check
                  type="checkbox"
                  checked={selectedUsers.has(user.name)}
                  onChange={() => toggleUserSelection(user.name)}
                />
              </td>
              <td>
                {user.name}
                {user.name.startsWith('github:') && (
                  <Badge bg="info" className="ms-2">GitHub</Badge>
                )}
              </td>
              <td>
                {user.admin ? (
                  <Badge bg="success">Admin</Badge>
                ) : (
                  <Badge bg="secondary">User</Badge>
                )}
              </td>
              <td>{getServerStatus(user)}</td>
              <td>{formatDate(user.last_activity)}</td>
              <td>
                <ButtonGroup size="sm">
                  {user.server ? (
                    <Button
                      variant="primary"
                      onClick={() => handleStopServer(user)}
                      disabled={actionLoading === `stop-${user.name}`}
                      title="Stop Server"
                    >
                      {actionLoading === `stop-${user.name}` ? (
                        <Spinner animation="border" size="sm" />
                      ) : (
                        'Stop Server'
                      )}
                    </Button>
                  ) : (
                    <Button
                      variant="primary"
                      onClick={() => handleStartServer(user)}
                      disabled={actionLoading === `start-${user.name}` || !!user.pending}
                      title="Start Server"
                    >
                      {actionLoading === `start-${user.name}` ? (
                        <Spinner animation="border" size="sm" />
                      ) : (
                        'Start Server'
                      )}
                    </Button>
                  )}

                  <Button
                    variant="light"
                    as="a"
                    href={`${baseUrl}spawn/${user.name}`}
                    title="Spawn Page"
                  >
                    Spawn Page
                  </Button>

                  <Button
                    variant="light"
                    onClick={() => openEditModal(user)}
                    title="Edit User"
                  >
                    Edit User
                  </Button>

                  {isNativeUser(user) && user.name !== 'admin' && (
                    <Button
                      variant="light"
                      onClick={() => openPasswordModal(user)}
                      title="Reset Password"
                    >
                      <i className="bi bi-key"></i> Reset PW
                    </Button>
                  )}
                </ButtonGroup>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>

      {filteredUsers.length === 0 && (
        <div className="text-center text-muted py-4">
          {search || onlyActiveServers ? 'No users match your filters.' : 'No users found.'}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="d-flex justify-content-between align-items-center mt-3">
          <div>
            Displaying {startIndex + 1}-{Math.min(startIndex + itemsPerPage, filteredUsers.length)} of {filteredUsers.length}
          </div>
          <div className="d-flex align-items-center gap-2">
            <span>Items per page:</span>
            <Form.Select
              value={itemsPerPage}
              onChange={(e) => {
                setItemsPerPage(Number(e.target.value));
                setCurrentPage(1);
              }}
              style={{ width: 'auto' }}
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </Form.Select>
            <ButtonGroup>
              <Button
                variant="outline-secondary"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <Button
                variant="outline-secondary"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                Next
              </Button>
            </ButtonGroup>
          </div>
        </div>
      )}

      <CreateUserModal
        show={showCreateModal}
        onHide={() => setShowCreateModal(false)}
        onSuccess={loadUsers}
      />

      <SetPasswordModal
        show={showPasswordModal}
        user={selectedUser}
        onHide={() => {
          setShowPasswordModal(false);
          setSelectedUser(null);
        }}
      />

      <EditUserModal
        show={showEditModal}
        user={selectedUser}
        onHide={() => {
          setShowEditModal(false);
          setSelectedUser(null);
        }}
        onUpdate={loadUsers}
      />
    </div>
  );
}
