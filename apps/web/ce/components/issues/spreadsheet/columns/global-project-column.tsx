import { observer } from "mobx-react";
import type { TIssue } from "@plane/types";
import { Row } from "@plane/ui";
import { useProject } from "@/hooks/store/use-project";

type Props = {
  issue: TIssue;
  onClose: () => void;
  onChange: (issue: TIssue, data: Partial<TIssue>, updates: Record<string, unknown>) => void;
  disabled: boolean;
};

export const SpreadsheetGlobalProjectColumn = observer(function SpreadsheetGlobalProjectColumn({ issue }: Props) {
  const { getProjectById } = useProject();
  const project = issue.project_id ? getProjectById(issue.project_id) : null;
  const isGlobal = project?.is_global ?? false;

  return (
    <Row className="flex h-11 w-full cursor-default items-center border-b-[0.5px] border-subtle px-2 text-11 hover:bg-layer-1 group-[.selected-issue-row]:bg-accent-primary/5 group-[.selected-issue-row]:hover:bg-accent-primary/10">
      <span
        className={`rounded px-1.5 py-0.5 text-xs font-medium ${
          isGlobal ? "bg-status-green/10 text-status-green" : "bg-layer-2 text-secondary"
        }`}
      >
        {isGlobal ? "Y" : "N"}
      </span>
    </Row>
  );
});
