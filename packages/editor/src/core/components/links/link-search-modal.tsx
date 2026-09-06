/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Dialog, Transition } from "@headlessui/react";
import React, { Fragment, useEffect, useState } from "react";
import { Search, Link as LinkIcon, FileText, CheckCircle2, Loader2 } from "lucide-react";
import type { Editor } from "@tiptap/core";
import type { TLinkSearchHandler, TLinkSearchItem } from "@/types";
import { setLinkEditor } from "@/helpers/editor-commands";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  editor: Editor;
  linkSearchHandler?: TLinkSearchHandler;
};

export function LinkSearchModal({ isOpen, onClose, editor, linkSearchHandler }: Props) {
  const [searchQuery, setSearchQuery] = useState("");
  const [recents, setRecents] = useState<TLinkSearchItem[]>([]);
  const [searchResults, setSearchResults] = useState<TLinkSearchItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  // Load recents on open
  useEffect(() => {
    if (isOpen && linkSearchHandler?.fetchRecentIssues) {
      setIsLoading(true);
      linkSearchHandler
        .fetchRecentIssues()
        .then((res) => {
          setRecents(res);
        })
        .catch((err) => {
          console.error("Failed to load recents:", err);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [isOpen, linkSearchHandler]);

  // Execute search when query changes
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    const triggerSearch = async () => {
      setIsSearching(true);
      try {
        const [issuesRes, pagesRes] = await Promise.all([
          linkSearchHandler?.searchIssues?.(searchQuery) ?? Promise.resolve([]),
          linkSearchHandler?.searchPages?.(searchQuery) ?? Promise.resolve([]),
        ]);
        setSearchResults([...issuesRes, ...pagesRes]);
      } catch (err) {
        console.error("Search failed:", err);
      } finally {
        setIsSearching(false);
      }
    };

    const debounceTimer = setTimeout(() => {
      void triggerSearch();
    }, 300);

    return () => clearTimeout(debounceTimer);
  }, [searchQuery, linkSearchHandler]);

  const handleItemSelect = (item: TLinkSearchItem) => {
    const { from, to } = editor.state.selection;
    const hasSelection = from !== to;

    if (hasSelection) {
      setLinkEditor(editor, item.redirect_uri);
    } else {
      editor
        .chain()
        .focus()
        .insertContent([
          {
            type: "text",
            text: item.title,
            marks: [{ type: "link", attrs: { href: item.redirect_uri } }],
          },
          { type: "text", text: " " },
        ])
        .run();
    }
    onClose();
  };

  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-brand-neutral-100/50 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-surface-1 border border-strong shadow-raised-300 transition-all sm:my-8 sm:w-full sm:max-w-lg">
                <div className="p-5">
                  <div className="flex items-center gap-2 border-b border-strong pb-3">
                    <Search className="size-4 text-tertiary" />
                    <input
                      type="text"
                      className="w-full bg-transparent text-13 font-normal outline-none text-primary placeholder:text-placeholder"
                      placeholder="Search issues by title or ID, or pages..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      autoFocus
                    />
                    {isSearching && <Loader2 className="size-4 animate-spin text-tertiary" />}
                  </div>

                  <div className="mt-4 max-h-[300px] overflow-y-auto pr-1">
                    {searchQuery.trim() ? (
                      <div>
                        <h4 className="text-11 font-semibold text-tertiary uppercase tracking-wider mb-2">
                          Search Results
                        </h4>
                        {searchResults.length > 0 ? (
                          <div className="space-y-1">
                            {searchResults.map((item) => (
                              <button
                                key={item.id}
                                type="button"
                                className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left text-13 hover:bg-layer-1-hover transition-colors text-secondary hover:text-primary"
                                onClick={() => handleItemSelect(item)}
                              >
                                {item.type === "issue" ? (
                                  <CheckCircle2 className="size-4 text-tertiary flex-shrink-0" />
                                ) : (
                                  <FileText className="size-4 text-tertiary flex-shrink-0" />
                                )}
                                <div className="truncate flex-1">
                                  <span className="font-medium">{item.title}</span>
                                  {item.subtitle && (
                                    <span className="text-11 text-tertiary ml-2 font-mono bg-layer-2 px-1 py-0.5 rounded">
                                      {item.subtitle}
                                    </span>
                                  )}
                                </div>
                                <LinkIcon className="size-3.5 text-placeholder opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                              </button>
                            ))}
                          </div>
                        ) : isSearching ? (
                          <p className="text-center py-6 text-13 text-placeholder">Searching...</p>
                        ) : (
                          <p className="text-center py-6 text-13 text-placeholder">No results found</p>
                        )}
                      </div>
                    ) : (
                      <div>
                        <h4 className="text-11 font-semibold text-tertiary uppercase tracking-wider mb-2">
                          Recently Viewed Issues
                        </h4>
                        {isLoading ? (
                          <div className="flex justify-center py-6">
                            <Loader2 className="size-5 animate-spin text-tertiary" />
                          </div>
                        ) : recents.length > 0 ? (
                          <div className="space-y-1">
                            {recents.map((item) => (
                              <button
                                key={item.id}
                                type="button"
                                className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left text-13 hover:bg-layer-1-hover transition-colors text-secondary hover:text-primary"
                                onClick={() => handleItemSelect(item)}
                              >
                                <CheckCircle2 className="size-4 text-tertiary flex-shrink-0" />
                                <div className="truncate flex-1">
                                  <span className="font-medium">{item.title}</span>
                                  {item.subtitle && (
                                    <span className="text-11 text-tertiary ml-2 font-mono bg-layer-2 px-1 py-0.5 rounded">
                                      {item.subtitle}
                                    </span>
                                  )}
                                </div>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <p className="text-center py-6 text-13 text-placeholder">No recent issues</p>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="mt-5 border-t border-strong pt-3 flex justify-end">
                    <button
                      type="button"
                      className="px-3 py-1.5 text-13 font-medium text-tertiary hover:bg-layer-1 rounded-md transition-colors"
                      onClick={onClose}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
