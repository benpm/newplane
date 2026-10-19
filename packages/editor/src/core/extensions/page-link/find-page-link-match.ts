/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { SuggestionMatch, Trigger } from "@tiptap/suggestion";

const LEAF_TEXT = "\uFFFC";

/**
 * `[` or `[[` at the start of a block or after whitespace / an inline node, followed by a
 * query that doesn't start with a space and contains no brackets, parentheses or line
 * breaks. Typing `]`, `(` or a space straight after the bracket therefore ends the match,
 * so Markdown links (`[text](url)`), task-list syntax (`[ ]`, `[x]`) and literal brackets
 * keep working as plain text.
 */
const PAGE_LINK_MATCH = /(^|[\s\uFFFC])(\[\[?)((?:[^\s[\]()\uFFFC][^[\]()\uFFFC]{0,99})?)$/;

/**
 * Suggestion matcher for page links. Reads the whole textblock up to the cursor (not just
 * the text node before it) so the trigger is found across marks such as bold or italic.
 */
export function findPageLinkMatch(config: Trigger): SuggestionMatch {
  const { $position } = config;
  if (!$position.parent.isTextblock || $position.parent.type.spec.code) return null;

  const blockStart = $position.start();
  // inline leaf nodes (hard breaks, mentions) count as one placeholder character, keeping offsets aligned
  const text = $position.doc.textBetween(blockStart, $position.pos, LEAF_TEXT, LEAF_TEXT);
  const match = PAGE_LINK_MATCH.exec(text);
  if (!match) return null;

  const [, prefix, trigger, query] = match;
  const from = blockStart + match.index + prefix.length;

  return {
    range: { from, to: $position.pos },
    query,
    text: `${trigger}${query}`,
  };
}
