import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useUser } from "@/hooks/store/user/user-user";
import { useUserPermissions } from "@/hooks/store/user";

/**
 * Returns whether the current user can edit the given issue.
 * Allowed: workspace admin, project admin, issue creator, issue assignee.
 * Returns false when issue data is not yet loaded (safe read-only default).
 */
export const useCanEditIssue = (issueId: string | undefined, workspaceSlug?: string, projectId?: string): boolean => {
  const { allowPermissions } = useUserPermissions();
  const { data: currentUser } = useUser();
  const {
    issue: { getIssueById },
  } = useIssueDetail();

  // Admin check — workspace admin is treated as project admin by allowPermissions
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT, workspaceSlug, projectId);

  if (isAdmin) return true;

  if (!issueId || !currentUser?.id) return false;

  const issue = getIssueById(issueId);
  if (!issue) return false;

  // Creator or assignee check
  if (issue.created_by === currentUser.id) return true;
  if (issue.assignee_ids?.includes(currentUser.id)) return true;

  return false;
};

/**
 * Returns whether the current user can attach things to an issue: sub-work items, relations, links, attachments.
 * Mirrors the API's ProjectEntityPermission (project admin or member), which is looser than useCanEditIssue —
 * only editing the issue's own fields is restricted to admin, creator and assignee.
 */
export const useCanAddToIssue = (workspaceSlug?: string, projectId?: string): boolean => {
  const { allowPermissions } = useUserPermissions();
  return allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );
};
