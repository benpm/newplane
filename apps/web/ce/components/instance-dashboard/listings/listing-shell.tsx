/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Input } from "@plane/propel/input";
import { Loader } from "@plane/ui";

type Props = {
  search: string;
  onSearchChange: (value: string) => void;
  placeholder: string;
  totalCount?: number;
  isLoading: boolean;
  error: unknown;
  isEmpty: boolean;
  hasNext: boolean;
  hasPrev: boolean;
  onNext: () => void;
  onPrev: () => void;
  children: ReactNode;
};

/** Search box, result count and cursor pagination around an inventory table. */
export const ListingShell = ({
  search,
  onSearchChange,
  placeholder,
  totalCount,
  isLoading,
  error,
  isEmpty,
  hasNext,
  hasPrev,
  onNext,
  onPrev,
  children,
}: Props) => {
  const { t } = useTranslation();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <Input
          type="text"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={placeholder}
          className="w-full max-w-xs bg-layer-2"
        />
        {totalCount !== undefined && (
          <span className="shrink-0 text-xs text-tertiary">
            {t("instance_dashboard.listings.total", { count: totalCount })}
          </span>
        )}
      </div>

      {isLoading ? (
        <Loader className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Loader.Item key={index} height="40px" />
          ))}
        </Loader>
      ) : error ? (
        <p className="text-sm text-danger-primary">{t("instance_dashboard.panel_error")}</p>
      ) : isEmpty ? (
        <p className="py-8 text-center text-sm text-tertiary">{t("instance_dashboard.listings.empty")}</p>
      ) : (
        <div className="overflow-x-auto">{children}</div>
      )}

      {(hasNext || hasPrev) && (
        <div className="flex items-center justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onPrev} disabled={!hasPrev}>
            {t("instance_dashboard.listings.previous")}
          </Button>
          <Button variant="secondary" size="sm" onClick={onNext} disabled={!hasNext}>
            {t("instance_dashboard.listings.next")}
          </Button>
        </div>
      )}
    </div>
  );
};
