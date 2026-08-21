type FieldRules = Record<string, unknown>;

/**
 * Work item properties are never mandatory.
 *
 * Category, sub-category, assignee, start date, due date and frequency used to be
 * required unless the work item sat in a backlog or cancelled state. That blocked
 * the most common way a tracker actually gets used -- jot the item down now, fill
 * in the details once you know them -- so the requirement is gone for every field
 * routed through this hook, in every state.
 *
 * Two things are deliberately still enforced elsewhere and are not affected here:
 * the title, because the API rejects a work item with no name, and custom
 * work-item-type properties an admin explicitly ticked as required, which run
 * through handlePropertyValuesValidation in the modal form instead.
 */
const clearRules = (originalRules: FieldRules): FieldRules => {
  // Each key must be explicitly set to undefined -- returning {} does not override
  // rules already registered in RHF's internal field map, because register()
  // spreads the new options onto the existing _f object and omitted keys survive.
  const cleared: FieldRules = {};
  for (const key of Object.keys(originalRules)) {
    cleared[key] = undefined;
  }
  return cleared;
};

export const useIssueFormValidation = (_projectId?: string | null) => ({
  isDraftState: false,
  getFieldRules: clearRules,
  getTaskCategoryFieldRules: (originalRules: FieldRules, _categoriesExist: boolean) => clearRules(originalRules),
});
