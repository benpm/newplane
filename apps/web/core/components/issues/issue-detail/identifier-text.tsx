/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { Tooltip } from "@plane/propel/tooltip";
import type { TIdentifierTextProps, TIdentifierTextVariant, TIssueIdentifierSize } from "@plane/types";
import { cn } from "@plane/utils";

const SIZE_MAP: Record<TIssueIdentifierSize, string> = {
  xs: "text-10 leading-3",
  sm: "text-11 leading-3",
  md: "text-11 leading-4",
  lg: "text-12",
};

const VARIANT_MAP: Record<TIdentifierTextVariant, string> = {
  default: "text-placeholder",
  secondary: "text-placeholder",
  tertiary: "text-placeholder",
  primary: "text-tertiary",
  "primary-subtle": "text-placeholder",
  success: "text-success-primary",
};

export function IdentifierText(props: TIdentifierTextProps) {
  const { identifier, enableClickToCopyIdentifier = false, size = "lg", variant = "default" } = props;
  // handlers
  const handleCopyIssueIdentifier = () => {
    if (enableClickToCopyIdentifier) {
      navigator.clipboard
        .writeText(identifier)
        .then(() => {
          setToast({
            type: TOAST_TYPE.SUCCESS,
            title: "Work item ID copied to clipboard",
          });
          return;
        })
        .catch(() => {
          console.error("Failed to copy work item ID");
        });
    }
  };

  const textSizeClassName = SIZE_MAP[size];
  const variantClassName = VARIANT_MAP[variant];

  return (
    <Tooltip tooltipContent="Click to copy" disabled={!enableClickToCopyIdentifier} position="top">
      <button
        type="button"
        className={cn("whitespace-nowrap font-normal text-placeholder text-10", textSizeClassName, variantClassName, {
          "cursor-pointer": enableClickToCopyIdentifier,
        })}
        onClick={handleCopyIssueIdentifier}
        disabled={!enableClickToCopyIdentifier}
      >
        {identifier}
      </button>
    </Tooltip>
  );
}
