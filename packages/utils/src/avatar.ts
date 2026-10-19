/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { getFileURL } from "./file";

/**
 * A user's `avatar_url` is either an uploaded image (absolute URL or `/api/assets/...` path)
 * or an emoji the user picked. These helpers keep that distinction out of generic file handling.
 */

export const DEFAULT_AVATAR_EMOJIS = [
  "🐭",
  "🐱",
  "🐶",
  "🦊",
  "🐻",
  "🐼",
  "🐨",
  "🐯",
  "🦁",
  "🐮",
  "🐷",
  "🐸",
  "🐵",
  "🐙",
  "🦄",
  "🦉",
  "🐧",
  "🦆",
  "🦅",
  "🐝",
  "🦋",
  "🐢",
  "🐬",
  "🐳",
  "🦈",
  "🦭",
  "🦦",
  "🦥",
  "🦔",
  "🐿️",
  "🦩",
  "🦚",
  "🦜",
  "🦖",
  "🦕",
  "🐉",
  "🌵",
  "🌸",
  "🌻",
  "🍀",
  "🚀",
  "🛸",
  "🪐",
  "⭐",
  "🌈",
  "🔥",
  "⚡",
  "🍕",
  "🍔",
  "🍦",
];

const IMAGE_SOURCE_REGEX = /^(https?:|data:|blob:|\/)/i;
// emoji picker storage format: dash-separated decimal code points, e.g. "128045" or "128105-8205-128187"
const EMOJI_CODE_POINTS_REGEX = /^\d+(-\d+)*$/;
const EMOJI_REGEX = /\p{Extended_Pictographic}|\p{Regional_Indicator}/u;
const MAX_EMOJI_LENGTH = 32;

/**
 * Stable pseudorandom default avatar emoji for a key (usually the user's name).
 */
export const getRandomAvatarEmoji = (key?: string | null): string => {
  if (!key) return DEFAULT_AVATAR_EMOJIS[0];
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return DEFAULT_AVATAR_EMOJIS[hash % DEFAULT_AVATAR_EMOJIS.length];
};

/**
 * Returns the emoji when an avatar value is an emoji (native or code-point encoded), otherwise undefined.
 */
export const getAvatarEmoji = (value?: string | null): string | undefined => {
  const trimmed = value?.trim();
  if (!trimmed || trimmed.length > MAX_EMOJI_LENGTH || IMAGE_SOURCE_REGEX.test(trimmed)) return undefined;
  if (EMOJI_CODE_POINTS_REGEX.test(trimmed)) {
    const codePoints = trimmed.split("-").map(Number);
    if (codePoints.some((codePoint) => codePoint > 0x10ffff)) return undefined;
    const emoji = String.fromCodePoint(...codePoints);
    return EMOJI_REGEX.test(emoji) ? emoji : undefined;
  }
  return EMOJI_REGEX.test(trimmed) ? trimmed : undefined;
};

/**
 * Avatar-aware variant of `getFileURL`: emoji avatars pass through unchanged (as the emoji),
 * image avatars resolve like any other file. Pass the result as an Avatar `src`.
 */
export const getAvatarURL = (value?: string | null): string | undefined =>
  getAvatarEmoji(value) ?? getFileURL(value ?? "");
