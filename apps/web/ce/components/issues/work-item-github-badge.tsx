/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { TIssue } from "@plane/types";
import { Tooltip } from "@plane/propel/tooltip";
// assets
import GitHubInvertocatWhite from "@/app/assets/logos/GitHub_Invertocat_White.png?url";
// hooks
import { usePlatformOS } from "@/hooks/use-platform-os";

type Props = {
  issue: TIssue | undefined | null;
  className?: string;
};

/**
 * Links a work item to its GitHub issue, and shows how much discussion is happening
 * there that Plane cannot show. Comments are deliberately not synced, so a comment on
 * the GitHub side is invisible from here -- the count is the point of the badge, not
 * decoration.
 *
 * Takes the work item rather than reading the store, so it does not have to know
 * whether it is rendering an issue or an epic; every layout already has the object.
 *
 * Renders nothing without a link: a project may have no repo connected, and MobX
 * writes work items optimistically, so a newly created one has no issue number until
 * the sync has run.
 */
export const WorkItemGithubBadge: React.FC<Props> = observer((props) => {
  const { issue, className } = props;
  const { t } = useTranslation();
  const { isMobile } = usePlatformOS();

  const number = issue?.github_issue_number;
  const repository = issue?.github_repository;
  if (!number || !repository) return null;

  const commentCount = issue?.github_comment_count ?? 0;
  const tooltip =
    commentCount > 0
      ? t("work_item_github.comments", { count: commentCount })
      : t("work_item_github.open", { repository, number });

  return (
    <Tooltip tooltipContent={tooltip} isMobile={isMobile} renderByDefault={false}>
      <a
        href={`https://github.com/${repository}/issues/${number}`}
        target="_blank"
        rel="noopener noreferrer"
        // Every layout block is wrapped in a ControlLink, so without stopping the
        // event here the row's peek overview opens instead of GitHub.
        onClick={(e) => e.stopPropagation()}
        onAuxClick={(e) => e.stopPropagation()}
        className={`flex flex-shrink-0 items-center gap-1 text-tertiary hover:text-primary ${className ?? ""}`}
        aria-label={tooltip}
      >
        <img src={GitHubInvertocatWhite} alt="GitHub" className="h-3 w-3 flex-shrink-0 object-contain" />
        {commentCount > 0 && <span className="text-caption-sm-regular">{commentCount}</span>}
      </a>
    </Tooltip>
  );
});
