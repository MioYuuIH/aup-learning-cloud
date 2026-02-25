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

import { useState, memo, useCallback, useEffect, useRef } from 'react';
import type { Resource, ResourceGroup, Accelerator } from '@auplc/shared';
import { CourseCard } from './CourseCard';

interface Props {
  group: ResourceGroup;
  selectedResource: Resource | null;
  onSelectResource: (resource: Resource) => void;
  onClearResource: () => void;
  defaultExpanded?: boolean;
  accelerators: Accelerator[];
  selectedAccelerator: Accelerator | null;
  onSelectAccelerator: (accelerator: Accelerator) => void;
}

export const CategorySection = memo(function CategorySection({
  group,
  selectedResource,
  onSelectResource,
  onClearResource,
  defaultExpanded = false,
  accelerators,
  selectedAccelerator,
  onSelectAccelerator,
}: Props) {
  const [collapsed, setCollapsed] = useState(!defaultExpanded);

  // Auto-expand once when a resource in this group is pre-selected (e.g. via URL param)
  const hasAutoExpanded = useRef(false);
  useEffect(() => {
    if (hasAutoExpanded.current) return;
    const groupContainsSelected = selectedResource != null &&
      group.resources.some(r => r.key === selectedResource.key);
    if (groupContainsSelected) {
      hasAutoExpanded.current = true;
      setCollapsed(false);
    }
  }, [selectedResource, group.resources]);

  const toggleCollapsed = useCallback(() => {
    setCollapsed(prev => {
      // When collapsing, clear selection if the selected resource is in this group
      if (!prev && selectedResource != null &&
          group.resources.some(r => r.key === selectedResource.key)) {
        onClearResource();
      }
      return !prev;
    });
  }, [selectedResource, group.resources, onClearResource]);

  // Use displayName from API, fallback to group name
  const displayName = group.displayName ?? group.name;

  return (
    <div className={`resource-category ${collapsed ? 'collapsed' : ''}`}>
      <div
        className="resource-category-header"
        onClick={toggleCollapsed}
      >
        <h5>📂 {displayName}</h5>
        <span className="collapse-icon">▼</span>
      </div>
      <div className="collapsible-content">
        {group.resources.map((resource) => (
          <CourseCard
            key={resource.key}
            resource={resource}
            selected={selectedResource?.key === resource.key}
            onSelect={onSelectResource}
            accelerators={accelerators}
            selectedAccelerator={selectedAccelerator}
            onSelectAccelerator={onSelectAccelerator}
          />
        ))}
      </div>
    </div>
  );
});
