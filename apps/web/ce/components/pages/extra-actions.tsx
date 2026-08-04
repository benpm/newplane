/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
import { observer } from "mobx-react";
import { FileCode2, FileUp } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CustomMenu } from "@plane/ui";
import { convertMarkdownToHTML } from "@plane/utils";
// store
import type { EPageStoreType } from "@/plane-web/hooks/store";
import type { TPageInstance } from "@/store/pages/base-page";
// local imports
import { RawMarkdownModal } from "./modals/raw-markdown-modal";

export type TPageHeaderExtraActionsProps = {
  page: TPageInstance;
  storeType: EPageStoreType;
};

export const PageDetailsHeaderExtraActions = observer(function PageDetailsHeaderExtraActions(
  props: TPageHeaderExtraActionsProps
) {
  const { page } = props;
  const { t } = useTranslation();
  const [isRawMarkdownOpen, setIsRawMarkdownOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    isContentEditable,
    editor: { editorRef },
  } = page;

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Reset immediately so re-picking the same file still fires a change event.
    event.target.value = "";
    if (!file || !editorRef) return;

    try {
      const html = convertMarkdownToHTML({ markdown: await file.text() });
      editorRef.setEditorValue(html, true);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("toast.success"),
        message: t("page_markdown.import.success"),
      });
    } catch (error) {
      console.error("Failed to import markdown file:", error);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: t("page_markdown.import.failed"),
      });
    }
  };

  // Both actions rewrite the document, so they are meaningless on a read-only or locked page.
  if (!isContentEditable) return null;

  return (
    <>
      <RawMarkdownModal editorRef={editorRef} isOpen={isRawMarkdownOpen} onClose={() => setIsRawMarkdownOpen(false)} />
      <input
        ref={fileInputRef}
        type="file"
        accept=".md,.markdown,text/markdown"
        className="hidden"
        onChange={(e) => void handleImportFile(e)}
      />
      <CustomMenu placement="bottom-end" closeOnSelect maxHeight="lg" ellipsis>
        <CustomMenu.MenuItem onClick={() => setIsRawMarkdownOpen(true)}>
          <span className="flex items-center gap-2">
            <FileCode2 className="size-3.5" />
            {t("page_markdown.raw_mode.action")}
          </span>
        </CustomMenu.MenuItem>
        <CustomMenu.MenuItem onClick={() => fileInputRef.current?.click()}>
          <span className="flex items-center gap-2">
            <FileUp className="size-3.5" />
            {t("page_markdown.import.action")}
          </span>
        </CustomMenu.MenuItem>
      </CustomMenu>
    </>
  );
});
