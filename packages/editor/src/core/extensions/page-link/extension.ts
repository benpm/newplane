/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Extension } from "@tiptap/core";
import { PluginKey } from "@tiptap/pm/state";
import { Suggestion } from "@tiptap/suggestion";
import type { SuggestionOptions } from "@tiptap/suggestion";
// extensions
import { renderMentionsDropdown } from "@/extensions/mentions/utils";
// helpers
import { DROPDOWN_NAVIGATION_KEYS } from "@/helpers/tippy";
// types
import type { TMentionSection, TPageLinkHandler, TPageLinkSuggestion } from "@/types";
// local imports
import { findPageLinkMatch } from "./find-page-link-match";

/**
 * The mentions dropdown, except that navigation keys (notably Enter) fall through to the
 * editor while there is nothing to pick, so a literal `[` never swallows a line break.
 */
const renderPageLinkDropdown =
  (searchCallback: (query: string) => Promise<TMentionSection[]>): SuggestionOptions["render"] =>
  () => {
    let hasResults = false;
    const dropdown = renderMentionsDropdown({
      searchCallback: async (query) => {
        const sections = await searchCallback(query);
        hasResults = sections.some((section) => section.items.length > 0);
        return sections;
      },
    })?.();

    return {
      ...dropdown,
      onStart: (props) => {
        hasResults = false;
        dropdown?.onStart?.(props);
      },
      onKeyDown: (props) => {
        if (!hasResults && DROPDOWN_NAVIGATION_KEYS.includes(props.event.key)) return false;
        // Escape closes the dropdown; keys typed afterwards belong to the editor again
        if (props.event.key === "Escape") hasResults = false;
        return dropdown?.onKeyDown?.(props) ?? false;
      },
    };
  };

/**
 * Autocomplete for links to other pages, triggered by typing `[` (or `[[`) at the start of a
 * word — see findPageLinkMatch for what keeps ordinary Markdown brackets out of its way.
 *
 * Deliberately inserts a plain link mark rather than a mention node: links survive the
 * GFM round trip as `[Title](url)` (needed by wiki sync and raw markdown mode), while
 * mention nodes have no Markdown representation and would be dropped.
 *
 * The dropdown/searching UI is the mentions one (see renderPageLinkDropdown) — only the
 * insertion command and key fall-through differ.
 */
export const PageLinkSuggestionExtension = (props: TPageLinkHandler) => {
  const { searchCallback } = props;

  return Extension.create({
    name: "pageLinkSuggestion",

    addProseMirrorPlugins() {
      // No search callback means the host editor doesn't support page links
      // (e.g. read-only or project-less editors) — contribute nothing.
      if (!searchCallback) return [];

      return [
        Suggestion({
          editor: this.editor,
          char: "[",
          findSuggestionMatch: findPageLinkMatch,
          pluginKey: new PluginKey("pageLinkSuggestion"),
          // no autocomplete inside inline code
          allow: ({ state, range }) => !state.doc.nodeAt(range.from)?.marks.some((mark) => mark.type.spec.code),
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
          render: renderPageLinkDropdown(searchCallback),
        }),
      ];
    },
  });
};
