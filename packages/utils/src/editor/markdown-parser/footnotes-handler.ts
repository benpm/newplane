/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// rehype-remark has no built-in understanding of the footnote HTML that remark-rehype
// generates, so without these handlers a `[^1]` degrades on the way back into a numbered
// link plus a "## Footnotes" heading — and the original syntax is gone for good.
// These map that HTML back onto the mdast footnote nodes remark-gfm serialises.

import type { Element as HASTElement } from "hast";
import type { Handle } from "hast-util-to-mdast";
import type { BlockContent, DefinitionContent, FootnoteDefinition, FootnoteReference } from "mdast";

/** `#user-content-fn-3` / `#fn-3` -> `3` */
const identifierFromHref = (href: string): string => href.replace(/^#(user-content-)?fn-?/, "");

/** `user-content-fn-3` / `fn-3` -> `3` */
const identifierFromId = (id: string): string => id.replace(/^(user-content-)?fn-?/, "");

const isElement = (node: unknown, tagName: string): node is HASTElement =>
  !!node &&
  typeof node === "object" &&
  (node as HASTElement).type === "element" &&
  (node as HASTElement).tagName === tagName;

/** The trailing "↩" link inside a definition is generated chrome, not content. */
const stripBackref = (node: HASTElement): void => {
  node.children = node.children.filter(
    (child) =>
      !(
        isElement(child, "a") &&
        ("dataFootnoteBackref" in (child.properties ?? {}) || "data-footnote-backref" in (child.properties ?? {}))
      )
  );

  for (const child of node.children) {
    if (child.type === "element") stripBackref(child);
  }
};

/**
 * `<sup><a data-footnote-ref href="#user-content-fn-1">1</a></sup>` -> `[^1]`
 */
const supHandler: Handle = (state, node) => {
  const link = node.children?.find((child) => isElement(child, "a"));
  const props = link?.properties ?? {};
  const isFootnoteRef = "dataFootnoteRef" in props || "data-footnote-ref" in props;

  if (!link || !isFootnoteRef) {
    // Not a footnote — fall back to the element's own children.
    return state.all(node);
  }

  const reference: FootnoteReference = {
    type: "footnoteReference",
    identifier: identifierFromHref(String(props.href ?? "")),
    label: identifierFromHref(String(props.href ?? "")),
  };
  return reference;
};

/**
 * `<section data-footnotes><ol><li id="user-content-fn-1">…</li></ol></section>`
 * -> one `footnoteDefinition` per list item.
 */
const sectionHandler: Handle = (state, node) => {
  const props = node.properties ?? {};
  const isFootnoteSection = "dataFootnotes" in props || "data-footnotes" in props;

  if (!isFootnoteSection) return state.all(node);

  const list = node.children?.find((child) => isElement(child, "ol"));
  if (!list) return state.all(node);

  const definitions: FootnoteDefinition[] = [];

  for (const item of list.children) {
    if (!isElement(item, "li")) continue;

    stripBackref(item);
    const identifier = identifierFromId(String(item.properties?.id ?? ""));

    definitions.push({
      type: "footnoteDefinition",
      identifier,
      label: identifier,
      children: state.all(item) as (BlockContent | DefinitionContent)[],
    });
  }

  return definitions;
};

export const parseFootnotes: Record<string, Handle> = {
  sup: supHandler,
  section: sectionHandler,
};
