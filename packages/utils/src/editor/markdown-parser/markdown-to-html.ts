/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Inverse of convertHTMLToMarkdown in ./root.ts.
// - Parses GitHub-flavored Markdown
// - Converts to HTML using remark→rehype
// - Rewrites GFM task list items into the shape TipTap's TaskItem expects,
//   mirroring the addSpacesToCheckboxes plugin in ./root.ts

import type { Element as HASTElement, ElementContent, Parent as HASTParent } from "hast";
import rehypeStringify from "rehype-stringify";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import { unified } from "unified";

const isElement = (node: ElementContent | undefined, tagName: string): node is HASTElement =>
  !!node && node.type === "element" && node.tagName === tagName;

/**
 * remark-rehype already emits GFM-standard task markup:
 *   <ul class="contains-task-list"><li class="task-list-item"><input type="checkbox" disabled> text</li></ul>
 * TipTap additionally keys off `data-type` / `data-checked`, so annotate the existing
 * nodes rather than restructuring them.
 *
 * Deliberately NOT wrapping the item body in <label>/<div><p>: that is TipTap's *render*
 * shape, and introducing it here splits the checkbox and its text into two blocks on the
 * way back out through rehype-remark (`* [ ]` followed by an indented paragraph). The flat
 * form is what convertHTMLToMarkdown's addSpacesToCheckboxes produces, so keeping it flat
 * is what makes the round trip stable.
 */
function annotateTaskListsForTipTap() {
  return (tree: HASTParent) => {
    const helper = (node: HASTParent): void => {
      if (!Array.isArray(node.children) || node.children.length === 0) return;

      for (const child of node.children) {
        if (child.type !== "element") continue;

        if (child.tagName === "li") {
          const checkbox = child.children?.find((c) => isElement(c, "input") && c.properties?.type === "checkbox");
          if (checkbox && checkbox.type === "element") {
            const isChecked = !!checkbox.properties?.checked;
            child.properties = {
              ...child.properties,
              "data-type": "taskItem",
              "data-checked": String(isChecked),
            };
            // `disabled` would make the checkbox unclickable inside the editor.
            delete checkbox.properties?.disabled;
          }
        }

        if (
          (child.tagName === "ul" || child.tagName === "ol") &&
          child.children.some((c) => isElement(c, "li") && c.properties?.["data-type"] === "taskItem")
        ) {
          child.properties = { ...child.properties, "data-type": "taskList" };
        }

        helper(child);
      }
    };

    // Items must be annotated before their parent list is inspected, so walk depth-first
    // by running the pass twice: once to tag items, once to tag the lists holding them.
    helper(tree);
    helper(tree);
  };
}

type TArgs = {
  markdown: string;
};

export function convertMarkdownToHTML(args: TArgs): string {
  const { markdown } = args;

  const result = unified()
    .use(remarkParse)
    .use(remarkGfm)
    // allowDangerousHtml: wiki pages routinely embed raw HTML; drop it and the
    // round trip silently loses content.
    .use(remarkRehype, { allowDangerousHtml: true })
    .use(annotateTaskListsForTipTap)
    .use(rehypeStringify, { allowDangerousHtml: true })
    .processSync(markdown);

  return String(result.value ?? result);
}
