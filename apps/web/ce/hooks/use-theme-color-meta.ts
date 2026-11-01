/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";

/**
 * Normalise any CSS colour (theme tokens are OKLCH) to #rrggbb, since
 * `theme-color` parsers aren't guaranteed to accept modern colour syntax.
 */
const toHex = (ctx: CanvasRenderingContext2D, color: string): string => {
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
};

/**
 * Keeps `<meta name="theme-color">` in sync with the app's canvas colour so an
 * installed PWA's title bar (and mobile browser chrome) follows the active theme.
 * The meta tag overrides the manifest `theme_color`, and Chromium re-reads it live.
 *
 * Watches `<html>` because next-themes swaps `data-theme`/`class` there and
 * custom themes write their palette as inline CSS variables on it.
 */
export const useThemeColorMeta = () => {
  useEffect(() => {
    const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    let meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "theme-color";
      document.head.appendChild(meta);
    }
    const target = meta;

    let frame = 0;
    const sync = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const color = toHex(ctx, getComputedStyle(document.body).backgroundColor);
        if (target.content !== color) target.content = color;
      });
    };

    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class", "style"] });
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);
};
