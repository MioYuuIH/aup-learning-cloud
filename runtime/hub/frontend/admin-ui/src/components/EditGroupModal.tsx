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

import { useState } from 'react';
import { Modal, Button, Form, InputGroup, ListGroup, Alert, Badge } from 'react-bootstrap';
import type { Group, User } from '../types';
import * as api from '../api/client';

interface Props {
  show: boolean;
  group: Group | null;
  onHide: () => void;
  onUpdate: () => void;
  onDelete: () => void;
}

export function EditGroupModal({ show, group, onHide, onUpdate, onDelete }: Props) {
  const [newUsername, setNewUsername] = useState('');
  const [newPropertyKey, setNewPropertyKey] = useState('');
  const [newPropertyValue, setNewPropertyValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [members, setMembers] = useState<string[]>([]);
  const [properties, setProperties] = useState<Record<string, unknown>>({});
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Initialize state when modal opens
  const handleEnter = async () => {
    if (group) {
      setMembers([...group.users]);
      setProperties({ ...group.properties });
      setError(null);

      // Load all users for dropdown
      try {
        setLoadingUsers(true);
        const response = await api.getUsers({ offset: 0, limit: 1000 });
        setAllUsers(response.items || response as unknown as User[]);
      } catch (err) {
        console.error('Failed to load users:', err);
      } finally {
        setLoadingUsers(false);
      }
    }
  };

  const handleAddUser = async () => {
    if (!group || !newUsername || newUsername === '') {
      setError('Please select a user');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await api.addUserToGroup(group.name, newUsername);
      setMembers([...members, newUsername]);
      setNewUsername('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add user');
    } finally {
      setLoading(false);
    }
  };

  // Get available users (not already in group)
  const availableUsers = (allUsers || []).filter(user => !members.includes(user.name));

  const handleRemoveUser = async (username: string) => {
    if (!group) return;

    try {
      setLoading(true);
      setError(null);
      await api.removeUserFromGroup(group.name, username);
      setMembers(members.filter(u => u !== username));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove user');
    } finally {
      setLoading(false);
    }
  };

  const handleAddProperty = () => {
    if (!newPropertyKey.trim()) {
      setError('Property key cannot be empty');
      return;
    }

    if (newPropertyKey in properties) {
      setError('Property key already exists');
      return;
    }

    setProperties({
      ...properties,
      [newPropertyKey]: newPropertyValue,
    });
    setNewPropertyKey('');
    setNewPropertyValue('');
    setError(null);
  };

  const handleRemoveProperty = (key: string) => {
    const newProps = { ...properties };
    delete newProps[key];
    setProperties(newProps);
  };

  const handleApply = async () => {
    if (!group) return;

    try {
      setLoading(true);
      setError(null);
      await api.updateGroup(group.name, { properties });
      onUpdate();
      onHide();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update group');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteGroup = async () => {
    if (!group) return;

    if (!window.confirm(`Are you sure you want to delete group "${group.name}"? This cannot be undone.`)) {
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await api.deleteGroup(group.name);
      onDelete();
      onHide();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete group');
    } finally {
      setLoading(false);
    }
  };

  if (!group) return null;

  return (
    <Modal show={show} onHide={onHide} onEnter={handleEnter} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>Editing Group {group.name}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {error && <Alert variant="danger" dismissible onClose={() => setError(null)}>{error}</Alert>}

        {/* Manage Members */}
        <div className="mb-4">
          <h5>Manage group members</h5>

          <InputGroup className="mb-3">
            <Form.Select
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              disabled={loading || loadingUsers}
            >
              <option value="">
                {loadingUsers ? 'Loading users...' : availableUsers.length === 0 ? 'No users available' : 'Select a user...'}
              </option>
              {availableUsers.map((user) => (
                <option key={user.name} value={user.name}>
                  {user.name}{user.admin ? ' (Admin)' : ''}
                </option>
              ))}
            </Form.Select>
            <Button variant="dark" onClick={handleAddUser} disabled={loading || loadingUsers || !newUsername}>
              Add user
            </Button>
          </InputGroup>

          <ListGroup>
            {members.length === 0 ? (
              <ListGroup.Item className="text-muted">No members</ListGroup.Item>
            ) : (
              members.map((username) => (
                <ListGroup.Item key={username} className="d-flex justify-content-between align-items-center">
                  {username}
                  <Button
                    variant="outline-danger"
                    size="sm"
                    onClick={() => handleRemoveUser(username)}
                    disabled={loading}
                  >
                    Remove
                  </Button>
                </ListGroup.Item>
              ))
            )}
          </ListGroup>
        </div>

        {/* Manage Properties */}
        <div className="mb-4">
          <h5>Manage group properties</h5>

          <div className="mb-3">
            <div className="row g-2">
              <div className="col-5">
                <Form.Control
                  placeholder="Key"
                  value={newPropertyKey}
                  onChange={(e) => setNewPropertyKey(e.target.value)}
                  disabled={loading}
                />
              </div>
              <div className="col-5">
                <Form.Control
                  placeholder="Value"
                  value={newPropertyValue}
                  onChange={(e) => setNewPropertyValue(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleAddProperty()}
                  disabled={loading}
                />
              </div>
              <div className="col-2">
                <Button variant="dark" onClick={handleAddProperty} disabled={loading} className="w-100">
                  Add Item
                </Button>
              </div>
            </div>
          </div>

          <ListGroup>
            {Object.keys(properties).length === 0 ? (
              <ListGroup.Item className="text-muted">No properties</ListGroup.Item>
            ) : (
              Object.entries(properties).map(([key, value]) => (
                <ListGroup.Item key={key} className="d-flex justify-content-between align-items-center">
                  <div>
                    <Badge bg="secondary" className="me-2">{key}</Badge>
                    <span>{String(value)}</span>
                  </div>
                  <Button
                    variant="outline-danger"
                    size="sm"
                    onClick={() => handleRemoveProperty(key)}
                    disabled={loading}
                  >
                    Remove
                  </Button>
                </ListGroup.Item>
              ))
            )}
          </ListGroup>
        </div>
      </Modal.Body>
      <Modal.Footer className="d-flex justify-content-between">
        <div>
          <Button variant="secondary" onClick={onHide} disabled={loading} className="me-2">
            Back
          </Button>
          <Button variant="dark" onClick={handleApply} disabled={loading}>
            {loading ? 'Applying...' : 'Apply'}
          </Button>
        </div>
        <Button variant="danger" onClick={handleDeleteGroup} disabled={loading}>
          Delete Group
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
