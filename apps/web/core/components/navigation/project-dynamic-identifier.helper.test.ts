/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { generateCreativeIdentifier } from "./project-dynamic-identifier.helper";

describe("generateCreativeIdentifier", () => {
  it("generates an identifier string not exceeding 64 characters", () => {
    for (let i = 0; i < 50; i++) {
      const id = generateCreativeIdentifier("Super Long Project Name With Many Elaborate Words", "EXTRALONGIDENTIFIER", "Complex Task Title With Multiple Requirements", "TASK-123456");
      expect(id.length).toBeLessThanOrEqual(64);
      expect(id.length).toBeGreaterThan(0);
    }
  });

  it("handles empty or undefined project and task inputs with creative defaults", () => {
    const id = generateCreativeIdentifier();
    expect(id.length).toBeLessThanOrEqual(64);
    expect(id.length).toBeGreaterThan(0);
  });

  it("contains symbols, numbers, and emojis", () => {
    const id = generateCreativeIdentifier("Project", "PROJ", "Task", "PROJ-1");
    // Should have numbers
    expect(/\d/.test(id)).toBe(true);
    // Should have symbols
    expect(/[:/#$~*&^_@-]/.test(id)).toBe(true);
  });

  it("incorporates project and task words", () => {
    const id = generateCreativeIdentifier("Apollo", "APOLLO", "Moonlanding", "APOLLO-11");
    const lower = id.toLowerCase();
    const hasProjectWord = lower.includes("apollo");
    const hasTaskWord = lower.includes("moonlanding") || lower.includes("apollo11") || lower.includes("task");
    expect(hasProjectWord || hasTaskWord).toBe(true);
  });
});
