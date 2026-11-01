import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useUser } from "@/hooks/store/user/user-user";
import { useUserPermissions } from "@/hooks/store/user";

/**
 * Returns whether the current user can edit the given issue, mirroring the API's
 * issue PATCH rule: project admins and members edit any issue; guests edit only
 * issues they created. Returns false for guests until the issue is loaded.
 */
export const useCanEditIssue = (issueId: string | undefined, workspaceSlug?: string, projectId?: string): boolean => {
  const { allowPermissions } = useUserPermissions();
  const { data: currentUser } = useUser();
  const {
    issue: { getIssueById },
  } = useIssueDetail();

  // workspace admins are treated as project admins by allowPermissions
  const isMember = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );
  if (isMember) return true;

  if (!issueId || !currentUser?.id) return false;
  return getIssueById(issueId)?.created_by === currentUser.id;
};
