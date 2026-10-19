/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useState } from "react";
import { EmojiIconPickerTypes, EmojiPicker, stringToEmoji } from "@plane/propel/emoji-icon-picker";

type Props = {
  buttonClassName?: string;
  label: ReactNode;
  onSelect: (emoji: string) => void;
};

/**
 * Emoji picker for the profile avatar. The propel picker reports emojis as code points;
 * this hands back the native emoji, which is what `avatar_url` stores. Icon picks are ignored.
 */
export function AvatarEmojiPicker(props: Props) {
  const { buttonClassName, label, onSelect } = props;
  const [isOpen, setIsOpen] = useState(false);

  return (
    <EmojiPicker
      isOpen={isOpen}
      handleToggle={setIsOpen}
      buttonClassName={buttonClassName}
      label={label}
      onChange={(selection) => {
        if (selection.type !== EmojiIconPickerTypes.EMOJI) return;
        const emoji = stringToEmoji(selection.value);
        if (emoji) onSelect(emoji);
      }}
    />
  );
}
