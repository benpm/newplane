/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import type { TIssue } from "@plane/types";
import { Tooltip } from "@plane/propel/tooltip";
import { usePlatformOS } from "@/hooks/use-platform-os";

export type TaskCheckboxProgressProps = {
  issue?: TIssue | null;
  checkboxTotal?: number | null;
  checkboxCompleted?: number | null;
  descriptionHtml?: string | null;
  size?: number;
  className?: string;
};

/**
 * Parses description HTML or markdown text for task item checkboxes.
 * Matches backend logic in `plane.utils.checkbox.extract_checkbox_counts`.
 */
export function extractCheckboxCounts(html: string | null | undefined): { total: number; completed: number } {
  if (!html) return { total: 0, completed: 0 };

  // 1. TipTap taskItem <li> tags:
  const taskItems = html.match(/<li\b[^>]*(?:data-type=["']taskItem["']|data-checked=["'](?:true|false)["'])[^>]*>/gi);
  if (taskItems && taskItems.length > 0) {
    const total = taskItems.length;
    let completed = 0;
    for (const item of taskItems) {
      if (/data-checked=["']true["']/i.test(item)) {
        completed++;
      }
    }
    return { total, completed };
  }

  // 2. Standalone checkbox input elements: <input type="checkbox" ...>
  const inputs = html.match(/<input\b[^>]*type=["']checkbox["'][^>]*>/gi);
  if (inputs && inputs.length > 0) {
    const total = inputs.length;
    let completed = 0;
    for (const item of inputs) {
      if (/\bchecked\b/i.test(item)) {
        completed++;
      }
    }
    return { total, completed };
  }

  // 3. Markdown checkboxes: - [ ] or - [x] / - [X]
  const mdMatches = html.match(/^[ \t]*[-*+][ \t]+\[([ xX])\]/gm);
  if (mdMatches && mdMatches.length > 0) {
    const total = mdMatches.length;
    let completed = 0;
    for (const m of mdMatches) {
      if (/\[[xX]\]/.test(m)) {
        completed++;
      }
    }
    return { total, completed };
  }

  return { total: 0, completed: 0 };
}

export const TaskCheckboxProgress: React.FC<TaskCheckboxProgressProps> = observer((props) => {
  const { issue, checkboxTotal, checkboxCompleted, descriptionHtml, size = 15, className = "" } = props;
  const { isMobile } = usePlatformOS();

  let total = checkboxTotal;
  let completed = checkboxCompleted;

  // If descriptionHtml is provided explicitly, extract from it (e.g. while editing in issue detail)
  if (descriptionHtml !== undefined && descriptionHtml !== null) {
    const parsed = extractCheckboxCounts(descriptionHtml);
    total = parsed.total;
    completed = parsed.completed;
  } else if (total === undefined && issue) {
    total = issue.checkbox_total;
    completed = issue.checkbox_completed;
    if ((total === undefined || total === null) && issue.description_html) {
      const parsed = extractCheckboxCounts(issue.description_html);
      total = parsed.total;
      completed = parsed.completed;
    }
  }

  if (total === undefined || total === null || total <= 0) {
    return null;
  }

  const validTotal = Math.max(0, total);
  const validCompleted = Math.min(validTotal, Math.max(0, completed ?? 0));
  const remaining = Math.max(0, validTotal - validCompleted);
  const isComplete = validCompleted === validTotal;

  // Tooltip content: e.g. "3 tasks left", "1 task left", "0 tasks left"
  const tooltip = `${remaining} ${remaining === 1 ? "task" : "tasks"} left`;

  // SVG circular geometry
  const radius = 5.5;
  const circumference = 2 * Math.PI * radius; // ~34.5575
  const progressRatio = validTotal > 0 ? validCompleted / validTotal : 0;
  const strokeDashoffset = circumference - progressRatio * circumference;

  let colorClass = "text-placeholder hover:text-secondary";
  if (isComplete) {
    colorClass = "text-emerald-500 hover:text-emerald-600";
  } else if (validCompleted > 0) {
    colorClass = "text-blue-500 hover:text-blue-600 dark:text-blue-400";
  }

  return (
    <Tooltip tooltipContent={tooltip} isMobile={isMobile} renderByDefault={false}>
      <span
        className={`inline-flex flex-shrink-0 items-center justify-center cursor-default transition-colors ${colorClass} ${className}`}
        aria-label={tooltip}
        onClick={(e) => e.stopPropagation()}
        onAuxClick={(e) => e.stopPropagation()}
      >
        <svg
          width={size}
          height={size}
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="flex-shrink-0"
        >
          {/* Background track circle */}
          <circle
            cx="8"
            cy="8"
            r={radius}
            stroke="currentColor"
            strokeWidth="1.8"
            className="opacity-25"
          />
          {/* Progress circle */}
          {validCompleted > 0 && (
            <circle
              cx="8"
              cy="8"
              r={radius}
              stroke="currentColor"
              strokeWidth="1.8"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              transform="rotate(-90 8 8)"
            />
          )}
          {/* Checkmark icon when all items completed */}
          {isComplete && (
            <path
              d="M5.5 8.2L7.2 9.9L10.5 6.2"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
        </svg>
      </span>
    </Tooltip>
  );
});
