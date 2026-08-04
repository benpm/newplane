/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Round-trip contract for GitHub-flavored Markdown.
//
// The property that matters is IDEMPOTENCE, not byte-equality with the input:
// remark normalises syntax (e.g. `*a*` -> `_a_`, setext headings -> ATX), so the
// first pass may legitimately reformat. What must hold is that a second pass
// changes nothing further. Page <-> wiki sync repeatedly converts the same
// content, so any construct that keeps mutating would drift on every sync.

import { describe, expect, it } from "vitest";
import { convertMarkdownToHTML } from "./markdown-to-html";
import { convertHTMLToMarkdown } from "./root";

const EMPTY_META = { file_assets: [], user_mentions: [] };

const toMarkdown = (markdown: string): string =>
  convertHTMLToMarkdown({
    description_html: convertMarkdownToHTML({ markdown }),
    metaData: EMPTY_META,
  });

/** Convert twice; the second pass must be a no-op. */
const expectStable = (markdown: string): string => {
  const once = toMarkdown(markdown);
  const twice = toMarkdown(once);
  expect(twice.trim()).toBe(once.trim());
  return once.trim();
};

describe("GFM round-trip stability", () => {
  const cases: Record<string, string> = {
    "atx headings": "# H1\n\n## H2\n\n### H3",
    "bold and italic": "**bold** and _italic_ and **_both_**",
    strikethrough: "~~struck through~~",
    "inline code": "use `const x = 1` here",
    "fenced code with language": '```ts\nconst x: number = 1;\nconsole.log("hi");\n```',
    "fenced code without language": "```\nplain block\n```",
    "inline link": "[Plane](https://plane.so)",
    autolink: "<https://plane.so>",
    image: "![alt text](https://example.com/a.png)",
    blockquote: "> quoted line\n>\n> second paragraph",
    "unordered list": "- one\n- two\n- three",
    "ordered list": "1. one\n2. two\n3. three",
    "nested list": "- parent\n  - child\n    - grandchild",
    "horizontal rule": "above\n\n***\n\nbelow",
    "hard line break": "line one\\\nline two",
    "table left aligned": "| a | b |\n| :- | :- |\n| 1 | 2 |",
    "table center aligned": "| a | b |\n| :-: | :-: |\n| 1 | 2 |",
    "table right aligned": "| a | b |\n| -: | -: |\n| 1 | 2 |",
    "table mixed alignment": "| l | c | r |\n| :- | :-: | -: |\n| 1 | 2 | 3 |",
    footnote: "Text with a note[^1]\n\n[^1]: The note body.",
    "task list": "- [ ] todo\n- [x] done",
    "nested task list": "- [ ] parent\n  - [x] child",
    "mixed document": [
      "# Title",
      "",
      "Intro with **bold**, _italic_ and ~~struck~~ text.",
      "",
      "- [ ] open item",
      "- [x] closed item",
      "",
      "| col | val |",
      "| :- | -: |",
      "| a | 1 |",
      "",
      "> a quote",
      "",
      "```js",
      "const answer = 42;",
      "```",
    ].join("\n"),
  };

  for (const [name, markdown] of Object.entries(cases)) {
    it(`is stable across repeated conversion: ${name}`, () => {
      expectStable(markdown);
    });
  }
});

describe("GFM content preservation", () => {
  it("keeps heading text and level", () => {
    expect(expectStable("## A heading")).toContain("## A heading");
  });

  it("keeps strikethrough syntax", () => {
    expect(expectStable("~~gone~~")).toContain("~~gone~~");
  });

  it("keeps the code fence language", () => {
    expect(expectStable("```python\nx = 1\n```")).toContain("```python");
  });

  it("keeps link target and label", () => {
    const out = expectStable("[Plane](https://plane.so)");
    expect(out).toContain("https://plane.so");
    expect(out).toContain("Plane");
  });

  it("keeps table column alignment markers", () => {
    const out = expectStable("| l | c | r |\n| :- | :-: | -: |\n| 1 | 2 | 3 |");
    expect(out).toContain(":-");
    expect(out).toContain(":-:");
    expect(out).toContain("-:");
  });

  it("keeps task list checked state distinct from unchecked", () => {
    const out = expectStable("- [ ] todo\n- [x] done");
    expect(out).toContain("[ ] todo");
    expect(out).toContain("[x] done");
  });

  it("keeps footnote reference and definition", () => {
    const out = expectStable("Body[^1]\n\n[^1]: Note text.");
    expect(out).toContain("[^1]");
    expect(out).toContain("Note text.");
  });

  it("keeps nested list depth", () => {
    // remark-stringify normalises the bullet marker to `*`; only the nesting must survive.
    const out = expectStable("- parent\n  - child");
    expect(out).toMatch(/^[-*]\s+parent/m);
    expect(out).toMatch(/\n\s+[-*]\s+child/);
  });
});

describe("convertMarkdownToHTML", () => {
  it("emits task items in the shape TipTap's TaskItem parses", () => {
    const html = convertMarkdownToHTML({ markdown: "- [x] done" });
    expect(html).toContain('data-type="taskList"');
    expect(html).toContain('data-type="taskItem"');
    expect(html).toContain('data-checked="true"');
  });

  it("marks unchecked task items as unchecked", () => {
    const html = convertMarkdownToHTML({ markdown: "- [ ] todo" });
    expect(html).toContain('data-checked="false"');
  });

  it("leaves plain bullet lists untouched", () => {
    const html = convertMarkdownToHTML({ markdown: "- just a bullet" });
    expect(html).not.toContain("taskItem");
    expect(html).toContain("<ul>");
  });

  it("passes raw HTML through rather than dropping it", () => {
    const html = convertMarkdownToHTML({ markdown: "<div class='raw'>kept</div>" });
    expect(html).toContain("kept");
  });

  it("returns empty output for empty input", () => {
    expect(convertMarkdownToHTML({ markdown: "" }).trim()).toBe("");
  });
});
