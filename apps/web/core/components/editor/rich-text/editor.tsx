/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { forwardRef } from "react";
// plane imports
import { RichTextEditorWithRef } from "@plane/editor";
import type { EditorRefApi, IRichTextEditorProps, TFileHandler, TIssueLinkSuggestion } from "@plane/editor";
import { WorkItemsIcon } from "@plane/propel/icons";
import type { MakeOptional, TSearchEntityRequestPayload, TSearchResponse } from "@plane/types";
import { cn } from "@plane/utils";
// components
import { EditorMentionsRoot } from "@/components/editor/embeds/mentions";
// hooks
import { useEditorConfig, useEditorMention } from "@/hooks/editor";
import { useMember } from "@/hooks/store/use-member";
import { useParseEditorContent } from "@/hooks/use-parse-editor-content";
import { WorkspaceService } from "@/services/workspace.service";
// plane web hooks

const workspaceService = new WorkspaceService();
import { useEditorFlagging } from "@/plane-web/hooks/use-editor-flagging";

type RichTextEditorWrapperProps = MakeOptional<
  Omit<IRichTextEditorProps, "fileHandler" | "mentionHandler" | "extendedEditorProps">,
  "disabledExtensions" | "editable" | "flaggedExtensions" | "getEditorMetaData"
> & {
  workspaceSlug: string;
  workspaceId: string;
  projectId?: string;
  issueSequenceId?: number;
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

export const RichTextEditor = forwardRef(function RichTextEditor(
  props: RichTextEditorWrapperProps,
  ref: React.ForwardedRef<EditorRefApi>
) {
  const {
    containerClassName,
    editable,
    workspaceSlug,
    workspaceId,
    projectId,
    disabledExtensions: additionalDisabledExtensions = [],
    ...rest
  } = props;
  // store hooks
  const { getUserDetails } = useMember();
  // editor flaggings
  const { richText: richTextEditorExtensions } = useEditorFlagging({
    workspaceSlug,
    projectId,
  });
  // use editor mention
  const { fetchMentions } = useEditorMention({
    searchEntity: editable ? async (payload) => await props.searchMentionCallback(payload) : async () => ({}),
  });
  // editor config
  const { getEditorFileHandlers } = useEditorConfig();
  // parse content
  const { getEditorMetaData } = useParseEditorContent({
    projectId,
    workspaceSlug,
  });

  return (
    <RichTextEditorWithRef
      ref={ref}
      disabledExtensions={[...richTextEditorExtensions.disabled, ...(additionalDisabledExtensions ?? [])]}
      editable={editable}
      flaggedExtensions={richTextEditorExtensions.flagged}
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
        getMentionedEntityDetails: (id) => ({
          display_name: getUserDetails(id)?.display_name ?? "",
        }),
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
      linkSearchHandler={
        editable && projectId
          ? {
              fetchRecentIssues: async () => {
                if (!workspaceSlug) return [];
                try {
                  const res = await workspaceService.fetchWorkspaceRecents(workspaceSlug.toString(), "issue");
                  return res.map((r: any) => ({
                    id: r.entity_data?.id ?? "",
                    title: r.entity_data?.name || "Untitled",
                    subtitle:
                      r.entity_data?.project_identifier && r.entity_data?.sequence_id
                        ? `${r.entity_data?.project_identifier}-${r.entity_data?.sequence_id}`
                        : undefined,
                    redirect_uri: `/${workspaceSlug}/projects/${r.entity_data?.project_id}/issues/${r.entity_data?.id}`,
                    type: "issue" as const,
                  }));
                } catch {
                  return [];
                }
              },
              searchIssues: async (query: string) => {
                try {
                  const res = await props.searchMentionCallback({
                    count: 10,
                    query_type: ["issue"],
                    query,
                    project_id: projectId,
                  });
                  return (res?.issue ?? []).map((r) => ({
                    id: r.id ?? "",
                    title: r.name || "Untitled",
                    subtitle:
                      r.project__identifier && r.sequence_id ? `${r.project__identifier}-${r.sequence_id}` : undefined,
                    redirect_uri: `/${workspaceSlug}/projects/${projectId}/issues/${r.id}`,
                    type: "issue" as const,
                  }));
                } catch {
                  return [];
                }
              },
              searchPages: async (query: string) => {
                try {
                  const res = await props.searchMentionCallback({
                    count: 10,
                    query_type: ["page"],
                    query,
                    project_id: projectId,
                  });
                  return (res?.page ?? []).map((r) => ({
                    id: r.id ?? "",
                    title: r.name || "Untitled",
                    redirect_uri: `/${workspaceSlug}/projects/${projectId}/pages/${r.id}`,
                    type: "page" as const,
                  }));
                } catch {
                  return [];
                }
              },
            }
          : undefined
      }
      extendedEditorProps={{}}
      {...rest}
      containerClassName={cn("relative pl-3 pb-3", containerClassName)}
    />
  );
});

RichTextEditor.displayName = "RichTextEditor";
