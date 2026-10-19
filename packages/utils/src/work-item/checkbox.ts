/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TCheckboxCounts = { total: number; completed: number };

const CODE_BLOCK_RE = /<pre\b[\s\S]*?<\/pre>/gi;
// Ordered by precedence: the first pattern with any matches wins.
const CHECKBOX_PATTERNS: { item: RegExp; checked: RegExp }[] = [
  // TipTap taskItem <li> tags
  {
    item: /<li\b[^>]*(?:data-type=["']taskItem["']|data-checked=["'](?:true|false)["'])[^>]*>/gi,
    checked: /data-checked=["']true["']/i,
  },
  // Standalone checkbox inputs
  { item: /<input\b[^>]*type=["']checkbox["'][^>]*>/gi, checked: /\bchecked\b/i },
  // Markdown checkboxes: - [ ] / - [x]
  { item: /^[ \t]*[-*+][ \t]+\[[ xX]\]/gm, checked: /\[[xX]\]/ },
];

/**
 * Counts task checkboxes in a work item description.
 * Mirrors the backend's `plane.utils.checkbox.extract_checkbox_counts`.
 */
export const extractCheckboxCounts = (html: string | null | undefined): TCheckboxCounts => {
  if (!html) return { total: 0, completed: 0 };
  // Checkbox syntax quoted in a code block is an example, not a task.
  const content = html.replace(CODE_BLOCK_RE, "");
  for (const { item, checked } of CHECKBOX_PATTERNS) {
    const matches = content.match(item);
    if (matches && matches.length > 0)
      return { total: matches.length, completed: matches.filter((match) => checked.test(match)).length };
  }
  return { total: 0, completed: 0 };
};
