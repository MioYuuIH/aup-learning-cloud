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

import { useState, useMemo, useCallback } from 'react';
import type { Resource, Accelerator } from '@auplc/shared';
import { CategorySection } from './components/CategorySection';
import { useResources } from './hooks/useResources';
import { useAccelerators } from './hooks/useAccelerators';
import { useQuota } from './hooks/useQuota';


function App() {

  const { resources, groups, loading: resourcesLoading, error: resourcesError } = useResources();
  const { accelerators, loading: acceleratorsLoading } = useAccelerators();
  const { quota, loading: quotaLoading } = useQuota();

  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [selectedAcceleratorKey, setSelectedAcceleratorKey] = useState<string | null>(null);
  const [runtime, setRuntime] = useState(20);
  const [runtimeInput, setRuntimeInput] = useState('20');
  const [repoUrl, setRepoUrl] = useState('');

  const loading = resourcesLoading || acceleratorsLoading || quotaLoading;

  // Compute available accelerators based on selected resource
  const availableAccelerators = useMemo(() => {
    if (!selectedResource?.metadata?.acceleratorKeys) {
      return [];
    }
    return accelerators.filter(acc =>
      selectedResource.metadata?.acceleratorKeys?.includes(acc.key)
    );
  }, [selectedResource, accelerators]);

  // Derive selected accelerator: use user selection if valid, otherwise first available
  const selectedAccelerator = useMemo(() => {
    if (availableAccelerators.length === 0) return null;
    const userSelected = availableAccelerators.find(acc => acc.key === selectedAcceleratorKey);
    return userSelected ?? availableAccelerators[0];
  }, [availableAccelerators, selectedAcceleratorKey]);

  // Memoize quota calculations
  const { cost, canAfford, insufficientQuota, maxRuntime } = useMemo(() => {
    const rate = selectedAccelerator?.quotaRate ?? quota?.rates?.cpu ?? 1;
    const calculatedCost = quota?.enabled ? rate * runtime : 0;
    const balance = quota?.balance ?? 0;

    return {
      cost: calculatedCost,
      canAfford: quota?.unlimited || balance >= calculatedCost,
      insufficientQuota: quota?.enabled && !quota?.unlimited && balance < 10,
      maxRuntime: quota?.enabled && !quota?.unlimited
        ? Math.min(240, Math.floor(balance / rate))
        : 240,
    };
  }, [quota, selectedAccelerator?.quotaRate, runtime]);

  const canStart = selectedResource && canAfford;

  // Memoize non-empty groups filter
  const nonEmptyGroups = useMemo(
    () => groups.filter(g => g.resources.length > 0),
    [groups]
  );

  // Memoize callbacks to prevent child re-renders
  const handleSelectResource = useCallback((resource: Resource) => {
    setSelectedResource(resource);
  }, []);

  const handleSelectAccelerator = useCallback((accelerator: Accelerator) => {
    setSelectedAcceleratorKey(accelerator.key);
  }, []);

  const handleRuntimeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setRuntimeInput(e.target.value);
    const value = parseInt(e.target.value);
    if (!isNaN(value) && value > 0) {
      setRuntime(value);
    }
  }, []);

  const handleRuntimeBlur = useCallback(() => {
    const value = parseInt(runtimeInput);
    const min = 10;
    const max = Math.min(240, maxRuntime);
    if (isNaN(value) || value < min) {
      setRuntime(min);
      setRuntimeInput(String(min));
    } else if (value > max) {
      setRuntime(max);
      setRuntimeInput(String(max));
    } else {
      setRuntime(value);
      setRuntimeInput(String(value));
    }
  }, [runtimeInput, maxRuntime]);

  if (loading) {
    return (
      <div className="loading-spinner">
        <span className="spinner-icon"></span>
        Loading available resources...
      </div>
    );
  }

  if (resourcesError) {
    return (
      <div className="warning-box">
        <strong>Error:</strong> {resourcesError}
      </div>
    );
  }

  return (
    <>
      {/* Hidden inputs for form submission */}
      <input type="hidden" name="resource_type" value={selectedResource?.key ?? ''} />
      {selectedResource && (
        <input
          type="hidden"
          name={`gpu_selection_${selectedResource.key}`}
          value={selectedAccelerator?.key ?? ''}
        />
      )}

      {/* Insufficient quota warning */}
      {insufficientQuota && (
        <div className="warning-box">
          <strong>Insufficient Quota</strong><br />
          You don't have enough quota to start a container. Please contact administrator.
        </div>
      )}

      {/* Resource list */}
      {resources.length === 0 ? (
        <div className="warning-box">
          <strong>No resources available</strong><br />
          Please contact administrator for access.
        </div>
      ) : (
        <>
          <div id="resourceList">
            {nonEmptyGroups.map((group, index) => (
              <CategorySection
                key={group.name}
                group={group}
                selectedResource={selectedResource}
                onSelectResource={handleSelectResource}
                defaultExpanded={index === 0}
                accelerators={accelerators}
                selectedAccelerator={selectedAccelerator}
                onSelectAccelerator={handleSelectAccelerator}
              />
            ))}
          </div>

          {/* Runtime input */}
          <div className="runtime-container">
            <label htmlFor="runtimeInput">Run my server for (minutes):</label>
            <input
              type="number"
              id="runtimeInput"
              name="runtime"
              min={10}
              max={Math.min(240, maxRuntime)}
              step={5}
              value={runtimeInput}
              onChange={handleRuntimeChange}
              onBlur={handleRuntimeBlur}
            />

            {/* Quota cost preview */}
            {quota?.enabled && !quota?.unlimited && (
              <div className="quota-cost-preview">
                <span style={{ color: '#666' }}>Estimated cost: </span>
                <strong style={{ color: canAfford ? '#2e7d32' : '#c62828' }}>{cost}</strong>
                <span style={{ color: '#666' }}> quota (Remaining: </span>
                <strong style={{ color: canAfford ? '#2e7d32' : '#c62828' }}>{(quota?.balance ?? 0) - cost}</strong>
                <span style={{ color: '#666' }}>)</span>
              </div>
            )}
          </div>

          {/* Git repository URL */}
          <div className="repo-url-section">
            <label htmlFor="repoUrlInput">Git Repository URL <span className="optional-label">(optional)</span></label>
            <input
              type="text"
              id="repoUrlInput"
              name="repo_url"
              value={repoUrl}
              onChange={e => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              autoComplete="off"
              spellCheck={false}
            />
            <small>The repository will be cloned into your home directory at startup. Supports GitHub, GitLab, and Bitbucket.</small>
          </div>

          {/* Launch section */}
          <div className="launch-section">
            <button
              type="submit"
              className="launch-button"
              disabled={!canStart}
            >
              Launch
            </button>

            {quota?.enabled && (
              <span className="quota-display-simple">
                Quota: <strong style={{ color: quota?.unlimited ? '#28a745' : ((quota?.balance ?? 0) < 10 ? '#dc3545' : '#2c3e50') }}>
                  {quota?.unlimited ? 'Unlimited' : quota?.balance ?? 0}
                </strong>
              </span>
            )}
          </div>
        </>
      )}
    </>
  );
}

export default App;
