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

import { memo, useMemo, useCallback } from 'react';
import type { Resource, Accelerator } from '@auplc/shared';

interface Props {
  resource: Resource;
  selected: boolean;
  onSelect: (resource: Resource) => void;
  accelerators: Accelerator[];
  selectedAccelerator: Accelerator | null;
  onSelectAccelerator: (accelerator: Accelerator) => void;
  repoUrl: string;
  repoUrlError: string;
  repoValidating: boolean;
  repoBranch: string;
  onRepoUrlChange: (value: string) => void;
  allowedGitProviders: string[];
}

function formatResourceTag(resource: Resource): string {
  const req = resource.requirements;
  const memory = req.memory.replace('Gi', 'GB');
  let tag = `${req.cpu} CPU, ${memory}`;
  if (req['amd.com/gpu']) {
    tag += `, 1 ${resource.metadata?.accelerator ?? 'GPU'}`;
  }
  if (req['amd.com/npu']) {
    tag += `, 1 NPU`;
  }
  return tag;
}

export const CourseCard = memo(function CourseCard({
  resource,
  selected,
  onSelect,
  accelerators,
  selectedAccelerator,
  onSelectAccelerator,
  repoUrl,
  repoUrlError,
  repoValidating,
  repoBranch,
  onRepoUrlChange,
  allowedGitProviders,
}: Props) {
  const handleClick = useCallback(() => {
    onSelect(resource);
  }, [onSelect, resource]);

  // Memoize available accelerators computation
  const acceleratorKeys = resource.metadata?.acceleratorKeys;
  const availableAccelerators = useMemo(() => {
    if (!acceleratorKeys || acceleratorKeys.length === 0) {
      return [];
    }
    return accelerators.filter(acc => acceleratorKeys.includes(acc.key));
  }, [acceleratorKeys, accelerators]);

  // Memoize resource tag to avoid recalculation
  const resourceTag = useMemo(() => formatResourceTag(resource), [resource]);

  const acceleratorType = resource.metadata?.accelerator ?? 'GPU';

  return (
    <div
      className={`resource-container ${selected ? 'selected' : ''}`}
      onClick={handleClick}
    >
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <input
          type="radio"
          id={resource.key}
          checked={selected}
          onChange={handleClick}
          onClick={(e) => e.stopPropagation()}
        />
        <div style={{ flex: 1 }}>
          <strong>{resource.metadata?.description ?? resource.key}</strong>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <span className="env-desc">
              {resource.metadata?.subDescription ?? ''}
            </span>
            {resource.metadata?.subDescription && (
              <span className="dot">•</span>
            )}
            <span className="resource-tag">
              {resourceTag}
            </span>
            {resource.metadata?.allowGitClone && (
              <span className="git-clone-badge" title="Supports custom Git repository cloning">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M15.698 7.287 8.712.302a1.03 1.03 0 0 0-1.457 0l-1.45 1.45 1.84 1.84a1.223 1.223 0 0 1 1.55 1.56l1.773 1.774a1.224 1.224 0 0 1 1.267 2.025 1.226 1.226 0 0 1-2.002-1.334L8.445 5.644v4.237a1.226 1.226 0 1 1-1.008-.036V5.585a1.226 1.226 0 0 1-.666-1.608L4.94 2.135 .302 6.772a1.03 1.03 0 0 0 0 1.456l6.986 6.986a1.03 1.03 0 0 0 1.456 0l6.953-6.953a1.031 1.031 0 0 0 0-1.974"/>
                </svg>
                Git Repo
              </span>
            )}
          </div>
        </div>
      </div>

      {/* GPU Selection Panel - only show when this resource is selected and has accelerators */}
      {selected && availableAccelerators.length > 0 && (
        <div className="gpu-selection">
          <h6>Choose {acceleratorType} Node:</h6>
          <div className="gpu-options-container">
            {availableAccelerators.map((acc) => (
              <GpuOption
                key={acc.key}
                accelerator={acc}
                resourceKey={resource.key}
                isSelected={selectedAccelerator?.key === acc.key}
                onSelect={onSelectAccelerator}
              />
            ))}
          </div>
        </div>
      )}

      {/* Git Repository URL - only show when selected and resource allows git clone */}
      {selected && resource.metadata?.allowGitClone && (
        <div className="repo-url-section" onClick={e => e.stopPropagation()}>
          <label htmlFor={`repoUrlInput-${resource.key}`}>
            Git Repository URL <span className="optional-label">(optional)</span>
            <span className="repo-url-hint" aria-label="Git repository hint">
              ?
              <span className="repo-url-tooltip">
                The repository will be cloned at startup and available during this session only.
                {allowedGitProviders.length > 0 && ` Supports: ${allowedGitProviders.join(', ')}.`}
              </span>
            </span>
          </label>
          <input
            type="text"
            id={`repoUrlInput-${resource.key}`}
            name="repo_url"
            value={repoUrl}
            onChange={e => onRepoUrlChange(e.target.value)}
            placeholder="https://github.com/owner/repo"
            autoComplete="off"
            spellCheck={false}
            className={repoUrlError ? 'input-error' : ''}
          />
          {repoValidating && (
            <small className="repo-url-validating">Checking repository...</small>
          )}
          {repoBranch && !repoUrlError && !repoValidating && (
            <small className="repo-branch-hint">Branch: <code>{repoBranch}</code></small>
          )}
          {repoUrlError && !repoValidating && (
            <small className="repo-url-error">{repoUrlError}</small>
          )}
        </div>
      )}
    </div>
  );
});

// Separate memoized component for GPU options
interface GpuOptionProps {
  accelerator: Accelerator;
  resourceKey: string;
  isSelected: boolean;
  onSelect: (accelerator: Accelerator) => void;
}

const GpuOption = memo(function GpuOption({
  accelerator,
  resourceKey,
  isSelected,
  onSelect,
}: GpuOptionProps) {
  const handleClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(accelerator);
  }, [onSelect, accelerator]);

  const handleChange = useCallback(() => {
    onSelect(accelerator);
  }, [onSelect, accelerator]);

  return (
    <div
      className={`gpu-option ${isSelected ? 'selected' : ''}`}
      onClick={handleClick}
    >
      <input
        type="radio"
        name={`gpu_selection_${resourceKey}`}
        checked={isSelected}
        onChange={handleChange}
        onClick={(e) => e.stopPropagation()}
      />
      <div className="gpu-option-details">
        <div className="gpu-option-name">{accelerator.displayName}</div>
        <div className="gpu-option-desc">{accelerator.description}</div>
      </div>
    </div>
  );
});
