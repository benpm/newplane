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
  it("returns no missing fields if the new state group is backlog or cancelled", () => {
    const { validateTransition } = useDraftStateTransition();
    const issue = {} as unknown as TIssue;

    expect(validateTransition(issue, "backlog-id")).toEqual({
      missingFieldKeys: [],
      missingFieldLabels: [],
    });

    expect(validateTransition(issue, "cancelled-id")).toEqual({
      missingFieldKeys: [],
      missingFieldLabels: [],
    });
  });

  it("checks for assignee and frequency but NOT start_date or target_date in non-backlog/cancelled states", () => {
    const { validateTransition } = useDraftStateTransition();
    const issue = {
      assignee_ids: [],
      frequency: null,
      start_date: null,
      target_date: null,
    } as unknown as TIssue;

    const result = validateTransition(issue, "started-id");

    // It should require assignee_ids and frequency
    expect(result.missingFieldKeys).toContain("assignee_ids");
    expect(result.missingFieldKeys).toContain("frequency");

    // It should NOT require start_date or target_date
    expect(result.missingFieldKeys).not.toContain("start_date");
    expect(result.missingFieldKeys).not.toContain("target_date");
  });

  it("returns no missing fields if assignee and frequency are set, even if dates are missing", () => {
    const { validateTransition } = useDraftStateTransition();
    const issue = {
      assignee_ids: ["member-1"],
      frequency: "daily",
      start_date: null,
      target_date: null,
    } as unknown as TIssue;

    const result = validateTransition(issue, "started-id");

    expect(result.missingFieldKeys).toEqual([]);
    expect(result.missingFieldLabels).toEqual([]);
  });
});
