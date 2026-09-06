/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const EMOJIS = ["⚡", "🚀", "✨", "🔮", "🛸", "👾", "🎯", "🛠️", "🪐", "🌀", "🧩", "🎲", "🔥", "💎"];
const SYMBOLS = ["::", "//", "~", "#", "$", "@", "*", "&", "^", "_"];
const NUMBERS = ["00", "01", "42", "77", "99", "404", "777", "2026"];
const DEFAULT_PROJECT_WORDS = ["plane", "project", "workspace", "orbit"];
const DEFAULT_TASK_WORDS = ["task", "sync", "flow", "craft", "patch", "build"];

const extractWords = (text?: string): string[] => {
  if (!text) return [];
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/[\s-]+/)
    .filter((w) => w.length >= 2 && w.length <= 15);
};

export const generateCreativeIdentifier = (
  projectName?: string,
  projectIdentifier?: string,
  taskName?: string,
  taskIdentifier?: string
): string => {
  const pClean = [
    ...(projectIdentifier ? [projectIdentifier.toLowerCase().replace(/[^a-z0-9]/g, "")] : []),
    ...extractWords(projectName),
  ].filter(Boolean);

  const projectWords = pClean.length > 0 ? pClean : DEFAULT_PROJECT_WORDS;

  const tClean = [
    ...(taskIdentifier ? [taskIdentifier.toLowerCase().replace(/[^a-z0-9]/g, "")] : []),
    ...extractWords(taskName),
  ].filter(Boolean);

  const taskWords = tClean.length > 0 ? tClean : DEFAULT_TASK_WORDS;

  const emoji = EMOJIS[Math.floor(Math.random() * EMOJIS.length)];
  const pWord = projectWords[Math.floor(Math.random() * projectWords.length)];
  const tWord = taskWords[Math.floor(Math.random() * taskWords.length)];
  const sym1 = SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];
  const sym2 = SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];
  const num = NUMBERS[Math.floor(Math.random() * NUMBERS.length)];

  const templates = [
    `${emoji}${pWord}${sym1}${tWord}${sym2}${num}`,
    `${pWord}${sym1}${emoji}${tWord}${sym2}${num}`,
    `${emoji}${num}${sym1}${pWord}${sym2}${tWord}`,
    `${emoji}${pWord}-${num}${sym1}${tWord}`,
  ];

  const selected = templates[Math.floor(Math.random() * templates.length)];
  return selected.slice(0, 64);
};
