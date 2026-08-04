/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Editor } from "@tiptap/core";
import { DOMParser as PMDOMParser } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
// plane imports
import { convertMarkdownToHTML } from "@plane/utils";

type TArgs = {
  editor: Editor;
};

// Markdown-only syntax. Plain prose should paste as plain prose rather than being
// pushed through a Markdown parser that might reinterpret stray punctuation.
const MARKDOWN_SIGNALS = [
  /^\s{0,3}#{1,6}\s+\S/m, // headings
  /^\s{0,3}[-*+]\s+\S/m, // bullet lists
  /^\s{0,3}\d+\.\s+\S/m, // ordered lists
  /^\s{0,3}>\s+\S/m, // blockquotes
  /^\s{0,3}(```|~~~)/m, // fenced code
  /^\s{0,3}\|.*\|/m, // tables
  /^\s{0,3}(\*\s*){3,}$|^\s{0,3}(-\s*){3,}$/m, // thematic breaks
  /\[[^\]]+\]\([^)]+\)/, // links
  /!\[[^\]]*\]\([^)]+\)/, // images
  /~~[^~]+~~/, // strikethrough
  /\[\^[^\]]+\]/, // footnotes
  /`[^`]+`/, // inline code
];

const looksLikeMarkdown = (text: string): boolean => MARKDOWN_SIGNALS.some((pattern) => pattern.test(text));

/**
 * Parses pasted plain text as GitHub-flavored Markdown using the same converter the
 * wiki sync uses, so pasted content and synced content produce identical documents.
 *
 * Only applies when the clipboard has no HTML flavour — pasting from a rich source
 * should keep that source's structure.
 */
export const MarkdownPastePlugin = (args: TArgs): Plugin => {
  const { editor } = args;

  return new Plugin({
    key: new PluginKey("markdownPaste"),
    props: {
      handlePaste: (view, event) => {
        const clipboard = event.clipboardData;
        if (!clipboard) return false;

        // Defer to the normal HTML paste path when the source offers markup.
        if (clipboard.getData("text/html")) return false;

        const text = clipboard.getData("text/plain");
        if (!text || !looksLikeMarkdown(text)) return false;

        try {
          const html = convertMarkdownToHTML({ markdown: text });
          if (!html.trim()) return false;

          const parsed = PMDOMParser.fromSchema(editor.schema).parse(
            new DOMParser().parseFromString(html, "text/html").body
          );

          const { tr } = view.state;
          view.dispatch(tr.replaceSelectionWith(parsed, false).scrollIntoView());
          event.preventDefault();
          return true;
        } catch (error) {
          // Fall through to the default paste rather than losing the user's content.
          console.error("Failed to parse pasted markdown:", error);
          return false;
        }
      },
    },
  });
};
