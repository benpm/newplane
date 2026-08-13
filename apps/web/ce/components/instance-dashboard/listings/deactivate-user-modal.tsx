/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { InstanceDashboardService } from "@plane/services";
import type { TDashboardUser } from "@plane/types";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";

const service = new InstanceDashboardService();

type Props = {
  user: TDashboardUser | null;
  onClose: () => void;
  onChanged: () => void;
};

/**
 * Suspend or restore an account.
 *
 * There is no delete here on purpose: accounts are not soft-deletable and
 * Django cascades in Python, so removing one takes its work items, pages and
 * projects with it. Deactivation is reversible from the same menu.
 */
export const DeactivateUserModal = ({ user, onClose, onChanged }: Props) => {
  const { t } = useTranslation();
  const [isSaving, setIsSaving] = useState(false);
  const isReactivating = user ? !user.is_active : false;

  const handleConfirm = async () => {
    if (!user) return;
    setIsSaving(true);
    try {
      await service.updateUser(user.id, { is_active: isReactivating });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: isReactivating ? t("instance_dashboard.users.reactivated") : t("instance_dashboard.users.deactivated"),
      });
      onChanged();
      onClose();
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("instance_dashboard.users.change_failed"),
        message: (error as { error?: string })?.error,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <ModalCore isOpen={!!user} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XL}>
      <div className="p-5">
        <h3 className="text-lg font-medium text-primary">
          {isReactivating
            ? t("instance_dashboard.users.reactivate_title")
            : t("instance_dashboard.users.deactivate_title")}
        </h3>
        <p className="mt-2 text-sm text-tertiary">
          {isReactivating
            ? t("instance_dashboard.users.reactivate_description", { name: user?.display_name ?? "" })
            : t("instance_dashboard.users.deactivate_description", { name: user?.display_name ?? "" })}
        </p>
        {!isReactivating && (
          <p className="mt-2 text-sm text-tertiary">{t("instance_dashboard.users.deactivate_note")}</p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button
            variant={isReactivating ? "primary" : "error-fill"}
            size="sm"
            onClick={() => void handleConfirm()}
            loading={isSaving}
          >
            {isReactivating
              ? t("instance_dashboard.users.reactivate_action")
              : t("instance_dashboard.users.deactivate_action")}
          </Button>
        </div>
      </div>
    </ModalCore>
  );
};
