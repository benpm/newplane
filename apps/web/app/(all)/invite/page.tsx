/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
// components
import { AuthFooter } from "@/components/auth-screens/footer";
import { AuthHeader } from "@/components/auth-screens/header";
import { AuthRoot } from "@/components/account/auth-forms/auth-root";
import { LogoSpinner } from "@/components/common/logo-spinner";
// helpers
import { EAuthModes, EPageTypes } from "@/helpers/authentication.helper";
// layouts
import DefaultLayout from "@/layouts/default-layout";
import { AuthenticationWrapper } from "@/lib/wrappers/authentication-wrapper";
// services
import { WorkspaceService } from "@/services/workspace.service";
// local imports
import type { Route } from "./+types/page";

const workspaceService = new WorkspaceService();

const InviteLinkPage = observer(function InviteLinkPage({ params }: Route.ComponentProps) {
  const { token } = params;
  const { t } = useTranslation();

  // Fetching this also parks the token on the session, which is how the
  // sign-up that follows -- by password, magic code or Google -- knows which
  // workspace to join. See WorkspaceInviteLinkPublicEndpoint.
  const {
    data: linkDetail,
    error,
    isLoading,
  } = useSWR(token ? `INVITE_LINK_${token}` : null, token ? () => workspaceService.getPublicInviteLink(token) : null, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });

  return (
    <DefaultLayout>
      <AuthenticationWrapper pageType={EPageTypes.NON_AUTHENTICATED}>
        <div className="relative z-10 flex flex-col items-center w-screen h-screen overflow-hidden overflow-y-auto pt-6 pb-10 px-8">
          <AuthHeader type={EAuthModes.SIGN_UP} />
          {isLoading ? (
            <div className="flex flex-grow items-center justify-center">
              <LogoSpinner />
            </div>
          ) : error || !linkDetail ? (
            <div className="flex flex-grow flex-col items-center justify-center gap-2 text-center">
              <h3 className="text-16 font-semibold text-primary">{t("invite_link.invalid.title")}</h3>
              <p className="max-w-sm text-13 text-tertiary">{t("invite_link.invalid.description")}</p>
            </div>
          ) : (
            <>
              <div className="mt-10 flex flex-col items-center gap-2 text-center">
                <h3 className="text-16 font-semibold text-primary">
                  {t("invite_link.join_heading", { workspace: linkDetail.workspace_name })}
                </h3>
                <p className="max-w-sm text-13 text-tertiary">{t("invite_link.join_description")}</p>
              </div>
              <AuthRoot authMode={EAuthModes.SIGN_UP} />
            </>
          )}
          <AuthFooter />
        </div>
      </AuthenticationWrapper>
    </DefaultLayout>
  );
});

export default InviteLinkPage;
