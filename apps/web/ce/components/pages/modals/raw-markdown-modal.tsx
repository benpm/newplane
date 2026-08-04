/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
// plane imports
import type { EditorRefApi } from "@plane/editor";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { convertMarkdownToHTML } from "@plane/utils";

type Props = {
  editorRef: EditorRefApi | null;
  isOpen: boolean;
  onClose: () => void;
};

export function RawMarkdownModal(props: Props) {
  const { editorRef, isOpen, onClose } = props;
  const { t } = useTranslation();
  const [markdown, setMarkdown] = useState("");
  const [isApplying, setIsApplying] = useState(false);

  // Re-read the document each time the modal opens; the page may have changed since last time.
  useEffect(() => {
    if (isOpen && editorRef) setMarkdown(editorRef.getMarkDown());
  }, [isOpen, editorRef]);

  const handleApply = () => {
    if (!editorRef) return;
    setIsApplying(true);
    try {
      editorRef.setEditorValue(convertMarkdownToHTML({ markdown }), true);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("toast.success"),
        message: t("page_markdown.raw_mode.applied"),
      });
      onClose();
    } catch (error) {
      console.error("Failed to apply markdown:", error);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: t("page_markdown.raw_mode.apply_failed"),
      });
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XXXXL}>
      <div className="p-5 space-y-4">
        <div className="space-y-1">
          <h3 className="text-lg font-medium text-primary">{t("page_markdown.raw_mode.title")}</h3>
          <p className="text-13 text-secondary">{t("page_markdown.raw_mode.description")}</p>
        </div>

        <div className="flex items-start gap-2 rounded-md bg-warning-subtle p-3">
          <AlertTriangle className="size-4 flex-shrink-0 text-warning-primary mt-0.5" />
          <p className="text-13 text-secondary">{t("page_markdown.raw_mode.lossy_warning")}</p>
        </div>

        <textarea
          value={markdown}
          onChange={(e) => setMarkdown(e.target.value)}
          spellCheck={false}
          className="w-full h-96 resize-y rounded-md border-[0.5px] border-subtle bg-layer-2 p-3 font-mono text-13 text-primary outline-none focus:border-accent-strong"
          aria-label={t("page_markdown.raw_mode.title")}
        />

        <div className="flex items-center justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button variant="primary" size="sm" onClick={handleApply} loading={isApplying}>
            {t("page_markdown.raw_mode.apply")}
          </Button>
        </div>
      </div>
    </ModalCore>
  );
}
