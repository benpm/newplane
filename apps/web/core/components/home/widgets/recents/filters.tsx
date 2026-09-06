/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { ChevronDownIcon } from "@plane/propel/icons";
import { CustomMenu } from "@plane/ui";
import { cn } from "@plane/utils";

export type TFilterOption = {
  name: string;
  icon?: React.ReactNode;
  label?: string;
  i18n_key?: string;
};

export type TFiltersDropdown = {
  className?: string;
  activeFilter: string;
  setActiveFilter: (filter: string) => void;
  filters: TFilterOption[];
};

export const FiltersDropdown = observer(function FiltersDropdown(props: TFiltersDropdown) {
  const { className, activeFilter, setActiveFilter, filters } = props;
  const { t } = useTranslation();

  function DropdownOptions() {
    return filters?.map((filter) => (
      <CustomMenu.MenuItem
        key={filter.name}
        className="flex items-center gap-2 truncate text-secondary"
        onClick={() => {
          setActiveFilter(filter.name);
        }}
      >
        {filter.icon && <div className="flex-shrink-0">{filter.icon}</div>}
        <div className="truncate font-medium text-11">
          {filter.label || (filter.i18n_key ? t(filter.i18n_key) : filter.name)}
        </div>
      </CustomMenu.MenuItem>
    ));
  }

  const activeItem = filters?.find((filter) => filter.name === activeFilter);
  const title = activeItem?.label || (activeItem?.i18n_key ? t(activeItem.i18n_key) : activeFilter || "");
  return (
    <CustomMenu
      maxHeight={"md"}
      className={cn("flex justify-center text-11 text-secondary w-fit", className)}
      placement="bottom-start"
      customButton={
        <button className="flex hover:bg-layer-transparent-hover px-2 py-1 rounded-sm gap-1 border border-subtle">
          <span className="font-medium text-13 my-auto">{title}</span>
          <ChevronDownIcon className={cn("size-3 my-auto text-tertiary hover:text-secondary duration-300")} />
        </button>
      }
      customButtonClassName="flex justify-center"
      closeOnSelect
    >
      <DropdownOptions />
    </CustomMenu>
  );
});
