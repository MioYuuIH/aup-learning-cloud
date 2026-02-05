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
import { Table, Button, Form, InputGroup, Alert, Spinner, Modal } from 'react-bootstrap';
import type { Group } from '../types';
import * as api from '../api/client';
import { EditGroupModal } from '../components/EditGroupModal';

export function GroupList() {
  const navigate = useNavigate();
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [newGroupName, setNewGroupName] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const loadGroups = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const groupList = await api.getGroups();
      setGroups(groupList);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load groups');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);

  const filteredGroups = groups.filter(group =>
    group.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) {
      setCreateError('Group name cannot be empty');
      return;
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(newGroupName)) {
      setCreateError('Group name can only contain letters, numbers, hyphens, and underscores');
      return;
    }

    try {
      setCreateLoading(true);
      setCreateError(null);
      await api.createGroup(newGroupName);
      setShowCreateModal(false);
      setNewGroupName('');
      await loadGroups();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create group');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleEditGroup = (group: Group) => {
    setSelectedGroup(group);
    setShowEditModal(true);
  };

  const handleCloseEditModal = () => {
    setShowEditModal(false);
    setSelectedGroup(null);
  };

  const handleUpdateGroup = async () => {
    await loadGroups();
  };

  const handleDeleteGroup = async () => {
    await loadGroups();
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
          <Button variant="dark" onClick={() => setShowCreateModal(true)}>
            Create Group
          </Button>
        </div>
        <div className="d-flex gap-2">
          <Button
            variant="outline-secondary"
            onClick={() => navigate('/users')}
          >
            Back to Users
          </Button>
          <Button
            variant="outline-secondary"
            as="a"
            href={`${window.jhdata?.base_url ?? '/hub/'}admin`}
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

      {/* Search */}
      <div className="mb-3">
        <InputGroup style={{ maxWidth: '400px' }}>
          <InputGroup.Text><i className="bi bi-search"></i></InputGroup.Text>
          <Form.Control
            placeholder="Search groups..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <Button variant="outline-secondary" onClick={() => setSearch('')}>
              Clear
            </Button>
          )}
        </InputGroup>
      </div>

      {/* Groups Table */}
      <Table striped hover responsive>
        <thead>
          <tr>
            <th>Group Name</th>
            <th>Members</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredGroups.map((group) => (
            <tr key={group.name}>
              <td>{group.name}</td>
              <td>
                {group.users.length === 0 ? (
                  <span className="text-muted">No members</span>
                ) : (
                  <span>{group.users.length} member{group.users.length > 1 ? 's' : ''}</span>
                )}
              </td>
              <td>
                <Button
                  variant="dark"
                  size="sm"
                  onClick={() => handleEditGroup(group)}
                  className="me-2"
                >
                  Edit
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>

      {filteredGroups.length === 0 && (
        <div className="text-center text-muted py-4">
          {search ? 'No groups match your search.' : 'No groups found. Create one to get started.'}
        </div>
      )}

      {/* Create Group Modal */}
      <Modal show={showCreateModal} onHide={() => setShowCreateModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Create New Group</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {createError && <Alert variant="danger">{createError}</Alert>}

          <Form.Group className="mb-3">
            <Form.Label>Group Name</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter group name"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              disabled={createLoading}
            />
            <Form.Text className="text-muted">
              Only letters, numbers, hyphens, and underscores allowed
            </Form.Text>
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowCreateModal(false)} disabled={createLoading}>
            Cancel
          </Button>
          <Button variant="dark" onClick={handleCreateGroup} disabled={createLoading}>
            {createLoading ? 'Creating...' : 'Create Group'}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Edit Group Modal */}
      <EditGroupModal
        show={showEditModal}
        group={selectedGroup}
        onHide={handleCloseEditModal}
        onUpdate={handleUpdateGroup}
        onDelete={handleDeleteGroup}
      />
    </div>
  );
}
