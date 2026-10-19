/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type React from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { Tooltip } from "@plane/propel/tooltip";
import type { TIssueCheckboxSource } from "@plane/types";
import { cn, extractCheckboxCounts } from "@plane/utils";
import { usePlatformOS } from "@/hooks/use-platform-os";

type Props = {
  issue?: TIssueCheckboxSource | null;
  size?: number;
  className?: string;
};

const RADIUS = 5.5;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Prefer the server-computed counts; fall back to parsing the description. */
const getCounts = (issue: TIssueCheckboxSource) =>
  typeof issue.checkbox_total === "number"
    ? { total: issue.checkbox_total, completed: issue.checkbox_completed ?? 0 }
    : extractCheckboxCounts(issue.description_html);

// The ring sits inside work item cards/rows that are links; keep clicks from navigating.
const stopEvent = (e: React.SyntheticEvent) => {
  e.preventDefault();
  e.stopPropagation();
};

/**
 * Progress ring for the task checkboxes in a work item's description.
 * Hidden when there are no checkboxes; completed checklists stay visible with a check mark.
 */
export const TaskCheckboxProgress = observer(function TaskCheckboxProgress(props: Props) {
  const { issue, size = 15, className } = props;
  const { t } = useTranslation();
  const { isMobile } = usePlatformOS();

  if (!issue) return null;
  const counts = getCounts(issue);
  if (counts.total <= 0) return null;

  const total = counts.total;
  const completed = Math.min(total, Math.max(0, counts.completed));
  const remaining = total - completed;
  const isComplete = remaining === 0;
  const tooltip = isComplete
    ? t("task_checkbox_progress.all_done")
    : t("task_checkbox_progress.remaining", { count: remaining });

  return (
    <Tooltip tooltipContent={tooltip} isMobile={isMobile} renderByDefault={false}>
      <span
        role="progressbar"
        tabIndex={0}
        aria-label={t("task_checkbox_progress.label")}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={completed}
        aria-valuetext={t("task_checkbox_progress.value", { completed, total })}
        className={cn(
          "inline-flex flex-shrink-0 items-center justify-center rounded-full cursor-default outline-none transition-colors focus-visible:ring-1 focus-visible:ring-accent-strong",
          {
            "text-success-primary": isComplete,
            "text-accent-primary": !isComplete && completed > 0,
            "text-placeholder": completed === 0,
          },
          className
        )}
        onClick={stopEvent}
        onAuxClick={stopEvent}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && stopEvent(e)}
      >
        <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true" className="flex-shrink-0">
          <circle cx="8" cy="8" r={RADIUS} stroke="currentColor" strokeWidth="1.8" className="opacity-25" />
          {completed > 0 && (
            <circle
              cx="8"
              cy="8"
              r={RADIUS}
              stroke="currentColor"
              strokeWidth="1.8"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={CIRCUMFERENCE * (1 - completed / total)}
              strokeLinecap="round"
              transform="rotate(-90 8 8)"
            />
          )}
          {isComplete && (
            <path
              d="M5.5 8.2L7.2 9.9L10.5 6.2"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
        </svg>
      </span>
    </Tooltip>
  );
});
