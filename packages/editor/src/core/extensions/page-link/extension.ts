/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Extension } from "@tiptap/core";
import { PluginKey } from "@tiptap/pm/state";
import { Suggestion } from "@tiptap/suggestion";
// extensions
import { renderMentionsDropdown } from "@/extensions/mentions/utils";
// types
import type { TPageLinkHandler, TPageLinkSuggestion } from "@/types";

/**
 * Autocomplete for links to other pages, triggered by typing `[[`.
 *
 * Deliberately inserts a plain link mark rather than a mention node: links survive the
 * GFM round trip as `[Title](url)` (needed by wiki sync and raw markdown mode), while
 * mention nodes have no Markdown representation and would be dropped.
 *
 * The dropdown/searching UI is the mentions one, reused unchanged — only the insertion
 * command differs.
 */
export const PageLinkSuggestionExtension = (props: TPageLinkHandler) => {
  const { searchCallback } = props;

  return Extension.create({
    name: "pageLinkSuggestion",

    addProseMirrorPlugins() {
      // No search callback means the host editor doesn't support page links
      // (work-item descriptions, comments) — contribute nothing.
      if (!searchCallback) return [];

      return [
        Suggestion({
          editor: this.editor,
          char: "[[",
          allowSpaces: true,
          pluginKey: new PluginKey("pageLinkSuggestion"),
          command: ({ editor, range, props: item }) => {
            const suggestion = item as TPageLinkSuggestion;
            editor
              .chain()
              .focus()
              .deleteRange(range)
              .insertContent([
                {
                  type: "text",
                  text: suggestion.title || "Untitled",
                  marks: [{ type: "link", attrs: { href: suggestion.redirect_uri } }],
                },
                // trailing space ends the link mark so typing continues as plain text
                { type: "text", text: " " },
              ])
              .run();
          },
          render: renderMentionsDropdown({ searchCallback }),
        }),
      ];
    },
  });
};
