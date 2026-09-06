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
import type { TIssueLinkHandler, TIssueLinkSuggestion } from "@/types";

/**
 * Autocomplete for links to issues, triggered by typing `#`.
 *
 * Deliberately inserts a plain link mark rather than a mention node.
 */
export const IssueLinkSuggestionExtension = (props: TIssueLinkHandler) => {
  const { searchCallback } = props;

  return Extension.create({
    name: "issueLinkSuggestion",

    addProseMirrorPlugins() {
      if (!searchCallback) return [];

      return [
        Suggestion({
          editor: this.editor,
          char: "#",
          allowSpaces: true,
          pluginKey: new PluginKey("issueLinkSuggestion"),
          command: ({ editor, range, props: item }) => {
            const suggestion = item as TIssueLinkSuggestion;
            const text = `#${suggestion.sequence_id}`;
            editor
              .chain()
              .focus()
              .deleteRange(range)
              .insertContent([
                {
                  type: "text",
                  text: text,
                  marks: [{ type: "link", attrs: { href: suggestion.redirect_uri } }],
                },
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
