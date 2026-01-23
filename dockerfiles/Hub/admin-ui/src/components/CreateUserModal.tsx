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
import { Modal, Button, Form, Alert, Spinner, InputGroup } from 'react-bootstrap';
import * as api from '../api/client';

interface Props {
  show: boolean;
  onHide: () => void;
  onSuccess: () => void;
}

interface CreatedUser {
  username: string;
  password: string;
}

export function CreateUserModal({ show, onHide, onSuccess }: Props) {
  const [usernames, setUsernames] = useState('');
  const [password, setPassword] = useState('');
  const [generateRandom, setGenerateRandom] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [forceChange, setForceChange] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdUsers, setCreatedUsers] = useState<CreatedUser[]>([]);
  const [step, setStep] = useState<'input' | 'result'>('input');

  const generateRandomPassword = () => {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
    let result = '';
    for (let i = 0; i < 16; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const names = usernames
        .split('\n')
        .map(n => n.trim())
        .filter(n => n.length > 0);

      if (names.length === 0) {
        throw new Error('Please enter at least one username');
      }

      const results: CreatedUser[] = [];

      for (const username of names) {
        // Create user
        await api.createUser(username, isAdmin);

        // Set password
        const pwd = generateRandom ? generateRandomPassword() : password;
        await api.setPassword({
          username,
          password: pwd,
          force_change: forceChange,
        });

        results.push({ username, password: pwd });
      }

      setCreatedUsers(results);
      setStep('result');
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create users');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setUsernames('');
    setPassword('');
    setGenerateRandom(true);
    setIsAdmin(false);
    setForceChange(true);
    setError(null);
    setCreatedUsers([]);
    setStep('input');
    onHide();
  };

  const copyToClipboard = () => {
    const text = createdUsers
      .map(u => `${u.username}\t${u.password}`)
      .join('\n');
    navigator.clipboard.writeText(text);
  };

  return (
    <Modal show={show} onHide={handleClose} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>
          {step === 'input' ? 'Create Users' : 'Users Created'}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {step === 'input' ? (
          <Form onSubmit={handleSubmit}>
            {error && <Alert variant="danger">{error}</Alert>}

            <Form.Group className="mb-3">
              <Form.Label>Usernames (one per line)</Form.Label>
              <Form.Control
                as="textarea"
                rows={5}
                value={usernames}
                onChange={(e) => setUsernames(e.target.value)}
                placeholder="user1&#10;user2&#10;user3"
                required
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Check
                type="checkbox"
                label="Generate random passwords"
                checked={generateRandom}
                onChange={(e) => setGenerateRandom(e.target.checked)}
              />
            </Form.Group>

            {!generateRandom && (
              <Form.Group className="mb-3">
                <Form.Label>Password (same for all users)</Form.Label>
                <InputGroup>
                  <Form.Control
                    type="text"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                    required={!generateRandom}
                    minLength={8}
                  />
                  <Button
                    variant="outline-secondary"
                    onClick={() => setPassword(generateRandomPassword())}
                  >
                    Generate
                  </Button>
                </InputGroup>
                <Form.Text className="text-muted">
                  Minimum 8 characters
                </Form.Text>
              </Form.Group>
            )}

            <Form.Group className="mb-3">
              <Form.Check
                type="checkbox"
                label="Force password change on first login"
                checked={forceChange}
                onChange={(e) => setForceChange(e.target.checked)}
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Check
                type="checkbox"
                label="Grant admin privileges"
                checked={isAdmin}
                onChange={(e) => setIsAdmin(e.target.checked)}
              />
            </Form.Group>
          </Form>
        ) : (
          <div>
            <Alert variant="success">
              Successfully created {createdUsers.length} user(s)!
            </Alert>
            <p className="text-muted">
              Copy the credentials below and share them with the users:
            </p>
            <div className="table-responsive">
              <table className="table table-sm table-bordered">
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Password</th>
                  </tr>
                </thead>
                <tbody>
                  {createdUsers.map((user) => (
                    <tr key={user.username}>
                      <td><code>{user.username}</code></td>
                      <td><code>{user.password}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {forceChange && (
              <Alert variant="info" className="mt-3">
                Users will be prompted to change their password on first login.
              </Alert>
            )}
          </div>
        )}
      </Modal.Body>
      <Modal.Footer>
        {step === 'input' ? (
          <>
            <Button variant="secondary" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Spinner animation="border" size="sm" className="me-1" />
                  Creating...
                </>
              ) : (
                'Create Users'
              )}
            </Button>
          </>
        ) : (
          <>
            <Button variant="outline-primary" onClick={copyToClipboard}>
              <i className="bi bi-clipboard me-1"></i> Copy to Clipboard
            </Button>
            <Button variant="primary" onClick={handleClose}>
              Done
            </Button>
          </>
        )}
      </Modal.Footer>
    </Modal>
  );
}
