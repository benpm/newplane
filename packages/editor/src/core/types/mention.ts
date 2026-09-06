/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane types
import type { TSearchEntities } from "@plane/types";

export type TMentionSuggestion = {
  entity_identifier: string;
  entity_name: TSearchEntities;
  icon: React.ReactNode;
  id: string;
  subTitle?: string;
  title: string;
};

export type TMentionSection = {
  key: string;
  title?: string;
  items: TMentionSuggestion[];
};

export type TCallbackMentionComponentProps = Pick<TMentionSuggestion, "entity_identifier" | "entity_name">;

export type TMentionHandler = {
  getMentionedEntityDetails?: (entity_identifier: string) => { display_name: string } | undefined;
  renderComponent: (props: TCallbackMentionComponentProps) => React.ReactNode;
  searchCallback?: (query: string) => Promise<TMentionSection[]>;
};

// Page-link autocomplete ([[ trigger). Items must be TPageLinkSuggestion — i.e. carry a
// redirect_uri — since the picked entry is inserted as a plain link mark.
export type TPageLinkSuggestion = TMentionSuggestion & {
  /** app-relative URL of the target page */
  redirect_uri: string;
};

export type TPageLinkHandler = {
  searchCallback?: (query: string) => Promise<TMentionSection[]>;
};

// Issue-link autocomplete (# trigger). Items must be TIssueLinkSuggestion — i.e. carry a
// redirect_uri, sequence_id, and project_identifier — since the picked entry is inserted as a plain link mark.
export type TIssueLinkSuggestion = TMentionSuggestion & {
  /** app-relative URL of the target issue */
  redirect_uri: string;
  sequence_id: string | number;
  project_identifier: string;
};

export type TIssueLinkHandler = {
  searchCallback?: (query: string) => Promise<TMentionSection[]>;
};

// Advanced link search modal handler types.
export type TLinkSearchItem = {
  id: string;
  title: string;
  subtitle?: string;
  redirect_uri: string;
  type: "issue" | "page";
};

export type TLinkSearchHandler = {
  searchIssues?: (query: string) => Promise<TLinkSearchItem[]>;
  searchPages?: (query: string) => Promise<TLinkSearchItem[]>;
  fetchRecentIssues?: () => Promise<TLinkSearchItem[]>;
};
