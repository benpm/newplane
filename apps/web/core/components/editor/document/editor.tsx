/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { forwardRef } from "react";
// plane imports
import { DocumentEditorWithRef } from "@plane/editor";
import type { IEditorPropsExtended, EditorRefApi, IDocumentEditorProps, TFileHandler, TIssueLinkSuggestion } from "@plane/editor";
import { WorkItemsIcon } from "@plane/propel/icons";
import type { MakeOptional, TSearchEntityRequestPayload, TSearchResponse } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { useEditorConfig, useEditorMention } from "@/hooks/editor";
import { useMember } from "@/hooks/store/use-member";
import { useParseEditorContent } from "@/hooks/use-parse-editor-content";
// plane web hooks
import { useEditorFlagging } from "@/plane-web/hooks/use-editor-flagging";
// local imports
import { EditorMentionsRoot } from "../embeds/mentions";

type DocumentEditorWrapperProps = MakeOptional<
  Omit<IDocumentEditorProps, "fileHandler" | "mentionHandler" | "user" | "extendedEditorProps">,
  "disabledExtensions" | "editable" | "flaggedExtensions" | "getEditorMetaData"
> & {
  extendedEditorProps?: Partial<IEditorPropsExtended>;
  workspaceSlug: string;
  workspaceId: string;
  projectId?: string;
} & (
    | {
        editable: false;
      }
    | {
        editable: true;
        searchMentionCallback: (payload: TSearchEntityRequestPayload) => Promise<TSearchResponse>;
        uploadFile: TFileHandler["upload"];
        duplicateFile: TFileHandler["duplicate"];
      }
  );

export const DocumentEditor = forwardRef(function DocumentEditor(
  props: DocumentEditorWrapperProps,
  ref: React.ForwardedRef<EditorRefApi>
) {
  const {
    containerClassName,
    editable,
    extendedEditorProps,
    workspaceSlug,
    workspaceId,
    projectId,
    disabledExtensions: additionalDisabledExtensions = [],
    ...rest
  } = props;
  // store hooks
  const { getUserDetails } = useMember();
  // parse content
  const { getEditorMetaData } = useParseEditorContent({
    projectId,
    workspaceSlug,
  });
  // editor flaggings
  const { document: documentEditorExtensions } = useEditorFlagging({
    workspaceSlug,
    projectId,
  });
  // use editor mention
  const { fetchMentions } = useEditorMention({
    enableAdvancedMentions: true,
    searchEntity: editable ? async (payload) => await props.searchMentionCallback(payload) : async () => ({}),
  });
  // editor config
  const { getEditorFileHandlers } = useEditorConfig();

  return (
    <DocumentEditorWithRef
      ref={ref}
      disabledExtensions={[...documentEditorExtensions.disabled, ...(additionalDisabledExtensions ?? [])]}
      editable={editable}
      flaggedExtensions={documentEditorExtensions.flagged}
      fileHandler={getEditorFileHandlers({
        projectId,
        uploadFile: editable ? props.uploadFile : async () => "",
        duplicateFile: editable ? props.duplicateFile : async () => "",
        workspaceId,
        workspaceSlug,
      })}
      getEditorMetaData={getEditorMetaData}
      mentionHandler={{
        searchCallback: async (query) => {
          const res = await fetchMentions(query);
          if (!res) throw new Error("Failed in fetching mentions");
          return res;
        },
        renderComponent: EditorMentionsRoot,
        getMentionedEntityDetails: (id: string) => ({ display_name: getUserDetails(id)?.display_name ?? "" }),
      }}
      issueLinkHandler={
        editable && projectId
          ? {
              searchCallback: async (query) => {
                const res = await props.searchMentionCallback({
                  count: 10,
                  query_type: ["issue"],
                  query,
                  project_id: projectId,
                });
                const items: TIssueLinkSuggestion[] = (res?.issue ?? []).map((foundIssue) => ({
                  id: foundIssue.id ?? "",
                  entity_identifier: foundIssue.id ?? "",
                  entity_name: "issue" as const,
                  title: foundIssue.name || "Untitled",
                  subTitle:
                    foundIssue.project__identifier && foundIssue.sequence_id
                      ? `${foundIssue.project__identifier}-${foundIssue.sequence_id}`
                      : undefined,
                  icon: <WorkItemsIcon className="size-3.5 text-tertiary" />,
                  redirect_uri: `/${workspaceSlug}/projects/${projectId}/issues/${foundIssue.id}`,
                  sequence_id: foundIssue.sequence_id,
                  project_identifier: foundIssue.project__identifier,
                }));
                return items.length > 0 ? [{ key: "issues", title: "Issues", items }] : [];
              },
            }
          : undefined
      }
      extendedEditorProps={extendedEditorProps}
      {...rest}
      containerClassName={cn("relative pl-3 pb-3", containerClassName)}
    />
  );
});

DocumentEditor.displayName = "DocumentEditor";
