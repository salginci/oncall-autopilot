from typing import Optional
from github import Github, Auth
from src.config import settings
from src.orchestrator.models import CommitInfo
from src.observability import logger


class GitHubTool:
    def __init__(self):
        auth = Auth.Token(settings.GITHUB_TOKEN)
        self._gh = Github(auth=auth)
        self._repo_name = settings.DEMO_REPO

    @property
    def repo(self):
        return self._gh.get_repo(self._repo_name)

    async def get_recent_commits(self, since_minutes: int = 10, limit: int = 5) -> list[CommitInfo]:
        commits = []
        for c in self.repo.get_commits(since=None, sha="main")[:limit]:
            files = [f.filename for f in c.files]
            commits.append(CommitInfo(
                sha=c.sha,
                message=c.commit.message,
                author=c.commit.author.name,
                timestamp=c.commit.author.date.replace(tzinfo=None),
                files_changed=files,
            ))
        return commits

    async def get_commit_diff(self, commit_sha: str) -> str:
        commit = self.repo.get_commit(commit_sha)
        if not commit.files:
            return ""
        diffs = []
        for f in commit.files:
            diffs.append(f"--- {f.filename}\n+++ {f.filename}\n{f.patch or ''}")
            diffs.append("")
        return "\n".join(diffs)

    async def revert_commit(self, commit_sha: str, reason: str) -> str:
        commit = self.repo.get_commit(commit_sha)
        parent_sha = commit.parents[0].sha if commit.parents else None

        if parent_sha:
            new_branch_name = f"revert-{commit_sha[:7]}"
            main_ref = self.repo.get_git_ref("heads/main")
            self.repo.create_git_ref(f"refs/heads/{new_branch_name}", main_ref.object.sha)

            try:
                commit_obj = self.repo.get_git_commit(commit_sha)
                parent_obj = self.repo.get_git_commit(parent_sha)
                base_tree = commit_obj.tree
                parent_tree = parent_obj.tree

                files = self.repo.get_commit(commit_sha).files
                changes = []
                for f in files:
                    if f.status in ("added",):
                        changes.append(("file", f.filename))
                    elif f.status in ("removed",):
                        file_content = self.repo.get_contents(f.filename, ref=parent_sha)
                        blob = self.repo.create_git_blob(file_content.decoded_content.decode(), "utf-8")
                        changes.append(("tree_entry", f.filename, blob.sha, "100644"))
                    else:
                        file_content = self.repo.get_contents(f.filename, ref=parent_sha)
                        blob = self.repo.create_git_blob(file_content.decoded_content.decode(), "utf-8")
                        changes.append(("tree_entry", f.filename, blob.sha, "100644"))

                tree_elements = []
                for change in changes:
                    if change[0] == "file":
                        tree_elements.append({"path": change[1], "mode": "100644", "type": "blob", "sha": None})
                    else:
                        tree_elements.append({"path": change[1], "mode": change[3], "type": "blob", "sha": change[2]})

                new_tree = self.repo.create_git_tree(tree_elements, base_tree=commit_obj.tree)
                new_commit_msg = f"Revert \"{commit.commit.message}\"\n\nReason: {reason}"
                new_commit = self.repo.create_git_commit(
                    new_commit_msg, new_tree, [self.repo.get_git_commit("main")]
                )
                self.repo.get_git_ref("heads/main").edit(new_commit.sha)
                self.repo.get_git_ref(f"heads/{new_branch_name}").delete()
                return new_commit.sha
            except Exception as e:
                try:
                    self.repo.get_git_ref(f"heads/{new_branch_name}").delete()
                except Exception:
                    pass
                raise e

        return ""

    async def push_revert(self, commit_sha: str, reason: str) -> dict:
        try:
            revert_sha = await self.revert_commit(commit_sha, reason)
            return {"success": True, "revert_sha": revert_sha, "message": f"Reverted {commit_sha[:7]}: {reason}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


github_tool = GitHubTool()
