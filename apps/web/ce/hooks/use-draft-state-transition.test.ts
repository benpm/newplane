/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it, vi } from "vitest";
import type { TIssue } from "@plane/types";
import { useDraftStateTransition } from "./use-draft-state-transition";

// Mock the dependencies
vi.mock("@/hooks/store/use-project-state", () => ({
  useProjectState: () => ({
    getStateById: (id: string) => {
      if (id === "backlog-id") return { group: "backlog" };
      if (id === "cancelled-id") return { group: "cancelled" };
      return { group: "started" };
    },
  }),
}));

vi.mock("@plane/i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

describe("useDraftStateTransition", () => {
  it("returns no missing fields regardless of state transition", () => {
    const { validateTransition } = useDraftStateTransition();
    const issue = {} as unknown as TIssue;

    expect(validateTransition(issue, "backlog-id")).toEqual({
      missingFieldKeys: [],
      missingFieldLabels: [],
    });

    expect(validateTransition(issue, "started-id")).toEqual({
      missingFieldKeys: [],
      missingFieldLabels: [],
    });

    expect(validateTransition(issue, "cancelled-id")).toEqual({
      missingFieldKeys: [],
      missingFieldLabels: [],
    });
  });

  it("does not require assignee or frequency when moving to any state", () => {
    const { validateTransition } = useDraftStateTransition();
    const issue = {
      assignee_ids: [],
      frequency: null,
      start_date: null,
      target_date: null,
    } as unknown as TIssue;

    const result = validateTransition(issue, "started-id");

    expect(result.missingFieldKeys).toEqual([]);
    expect(result.missingFieldLabels).toEqual([]);
  });
});
