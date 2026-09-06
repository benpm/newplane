/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import type { TIssueIdentifierProps, TIssueTypeIdentifier } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { IdentifierText } from "@/components/issues/issue-detail/identifier-text";

export const IssueIdentifier = observer(function IssueIdentifier(props: TIssueIdentifierProps) {
  const { variant, size, displayProperties, enableClickToCopyIdentifier = false } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // Determine if the component is using store data or not
  const isUsingStoreData = "issueId" in props;
  // derived values
  const issue = isUsingStoreData ? getIssueById(props.issueId) : null;
  const issueSequenceId = isUsingStoreData ? issue?.sequence_id : props.issueSequenceId;
  const shouldRenderIssueID = displayProperties ? displayProperties.key : true;

  if (!shouldRenderIssueID || issueSequenceId === undefined || issueSequenceId === null) return null;

  return (
    <div className="shrink-0 flex items-center space-x-2">
      <IdentifierText
        identifier={`#${issueSequenceId}`}
        enableClickToCopyIdentifier={enableClickToCopyIdentifier}
        variant={variant}
        size={size}
      />
    </div>
  );
});

export const IssueTypeIdentifier = observer(function IssueTypeIdentifier(_props: TIssueTypeIdentifier) {
  return <></>;
});
