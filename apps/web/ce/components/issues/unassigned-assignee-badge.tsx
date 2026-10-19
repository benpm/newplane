/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";

type TClaimLabelKey = "get" | "yoink" | "take";

/**
 * Picks the claim label for an unassigned work item: "get" 75%, "yoink" 12.5%, "take" 12.5%.
 * Hashing the id keeps the label stable for the card, even when virtualised layouts remount it.
 */
const getClaimLabelKey = (id?: string | null): TClaimLabelKey => {
  let roll = Math.random();
  if (id) {
    let hash = 0;
    for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
    roll = (hash % 1000) / 1000;
  }
  if (roll < 0.75) return "get";
  if (roll < 0.875) return "yoink";
  return "take";
};

type Props = {
  issueId?: string | null;
  className?: string;
};

/**
 * Bold yellow button content shown in place of the assignee avatars when a work item has no assignees.
 * Rendered as the `button` of a MemberDropdown, so clicking it still opens the assignment dropdown.
 */
export function UnassignedAssigneeBadge(props: Props) {
  const { issueId, className } = props;
  const { t } = useTranslation();
  // computed once per mount so the label never flickers between renders
  const [labelKey] = useState(() => getClaimLabelKey(issueId));

  return (
    <span
      className={cn(
        "inline-flex h-5 items-center justify-center rounded-sm px-2 text-11 leading-4 font-bold shadow-raised-100 select-none transition-colors",
        "bg-label-yellow-bg-strong text-black hover:bg-label-yellow-focus",
        className
      )}
      title={t("unassigned_claim.tooltip")}
    >
      {t(`unassigned_claim.${labelKey}`)}
    </span>
  );
}
