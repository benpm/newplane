/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useMemo, useState } from "react";

/**
 * Returns a stable pseudo-random action text ("Get", "Yoink", or "Take")
 * for an unassigned task based on its id, with "Get" having 75% probability.
 */
export const getUnassignedActionText = (id?: string | null): "Get" | "Yoink" | "Take" => {
  if (!id) {
    const r = Math.random();
    if (r < 0.75) return "Get";
    if (r < 0.875) return "Yoink";
    return "Take";
  }
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  const norm = (hash % 1000) / 1000;
  if (norm < 0.75) return "Get";
  if (norm < 0.875) return "Yoink";
  return "Take";
};

type Props = {
  issueId?: string | null;
  className?: string;
};

export const UnassignedAssigneeBadge: React.FC<Props> = ({ issueId, className = "" }) => {
  const [isHovered, setIsHovered] = useState(false);
  const text = useMemo(() => getUnassignedActionText(issueId), [issueId]);

  return (
    <span
      className={`unassigned-claim-btn inline-flex items-center justify-center h-5 px-2 py-0.5 rounded font-bold shadow-xs transition-colors cursor-pointer select-none ${className}`}
      style={{
        backgroundColor: isHovered ? "#eab308" : "#ffd600",
        color: "#000000",
        fontWeight: 700,
        fontSize: "0.6875rem",
        lineHeight: "1rem",
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      title="Assignees"
    >
      {text}
    </span>
  );
};
