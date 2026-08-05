/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Request, Response } from "express";
import { z } from "zod";
// helpers
import { Controller, Post } from "@plane/decorators";
import { convertHTMLDocumentToAllFormats } from "@plane/editor";
// logger
import { logger } from "@plane/logger";
import { convertHTMLToMarkdown, convertMarkdownToHTML } from "@plane/utils";

// Markdown -> all document formats, or HTML -> markdown. Used by the GitHub wiki sync
// worker so GFM conversion stays single-sourced in the tested TypeScript pipeline
// instead of being re-implemented in Python.
const convertMarkdownSchema = z.union([
  z.object({
    markdown: z.string(),
    variant: z.enum(["rich", "document"]).default("document"),
  }),
  z.object({
    description_html: z.string().min(1, "HTML content cannot be empty"),
  }),
]);

const EMPTY_META = { file_assets: [], user_mentions: [] };

@Controller("/convert-markdown")
export class MarkdownController {
  @Post("/")
  // eslint-disable-next-line @typescript-eslint/require-await -- @Post handlers must be async; conversion is synchronous
  async convertMarkdown(req: Request, res: Response) {
    try {
      const validatedData = convertMarkdownSchema.parse(req.body);

      if ("markdown" in validatedData) {
        const description_html = convertMarkdownToHTML({ markdown: validatedData.markdown }) || "<p></p>";
        const { description_json, description_binary } = convertHTMLDocumentToAllFormats({
          document_html: description_html,
          variant: validatedData.variant,
        });
        res.status(200).json({ description_html, description_json, description_binary });
        return;
      }

      const markdown = convertHTMLToMarkdown({
        description_html: validatedData.description_html,
        metaData: EMPTY_META,
      });
      res.status(200).json({ markdown });
    } catch (error) {
      if (error instanceof z.ZodError) {
        const validationErrors = error.errors.map((err) => ({
          path: err.path.join("."),
          message: err.message,
        }));
        logger.error("MARKDOWN_CONTROLLER: Validation error", { validationErrors });
        return res.status(400).json({
          message: "Validation error",
          context: { validationErrors },
        });
      }

      logger.error("MARKDOWN_CONTROLLER: Conversion failed", { error });
      return res.status(500).json({ message: "Markdown conversion failed" });
    }
  }
}
