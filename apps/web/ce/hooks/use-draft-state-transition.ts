import type { TIssue } from "@plane/types";

type ValidationResult = {
  missingFieldKeys: string[];
  missingFieldLabels: string[];
};

export const useDraftStateTransition = () => {
  // No fields are required when moving a task between statuses.
  const validateTransition = (_issue: TIssue, _newStateId: string, _currentStateGroup?: string): ValidationResult => ({
    missingFieldKeys: [],
    missingFieldLabels: [],
  });

  return { validateTransition };
};
