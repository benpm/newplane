/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Input } from "@plane/propel/input";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { InstanceDashboardService } from "@plane/services";
import type { TDashboardUser } from "@plane/types";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";

const service = new InstanceDashboardService();

type Props = {
  user: TDashboardUser | null;
  onClose: () => void;
  onRenamed: () => void;
};

/** Change the label an account shows under. Email and username are untouched. */
export const RenameUserModal = ({ user, onClose, onRenamed }: Props) => {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setName(user?.display_name ?? "");
    // Move focus into the field when the dialog opens. Done with a ref rather
    // than autoFocus, which fires on mount regardless of whether the dialog is
    // showing and is flagged as an accessibility hazard.
    if (user) {
      const timer = setTimeout(() => inputRef.current?.select(), 0);
      return () => clearTimeout(timer);
    }
  }, [user]);

  const handleSave = async () => {
    if (!user || !name.trim()) return;
    setIsSaving(true);
    try {
      await service.updateUser(user.id, { display_name: name.trim() });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("instance_dashboard.users.renamed") });
      onRenamed();
      onClose();
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("instance_dashboard.users.rename_failed"),
        message: (error as { error?: string })?.error,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <ModalCore isOpen={!!user} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XL}>
      <div className="p-5">
        <h3 className="text-lg font-medium text-primary">{t("instance_dashboard.users.rename_title")}</h3>
        <p className="mt-1 text-sm text-tertiary">
          {t("instance_dashboard.users.rename_description", { email: user?.email ?? "" })}
        </p>

        <div className="mt-4 space-y-1">
          <label htmlFor="display-name" className="block text-13 font-medium text-primary">
            {t("instance_dashboard.users.display_name")}
          </label>
          <Input
            id="display-name"
            ref={inputRef}
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && void handleSave()}
            className="w-full bg-layer-2"
          />
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void handleSave()}
            loading={isSaving}
            disabled={!name.trim() || name.trim() === user?.display_name}
          >
            {t("save")}
          </Button>
        </div>
      </div>
    </ModalCore>
  );
};
