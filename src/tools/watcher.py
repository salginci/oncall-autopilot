from typing import Optional
from src.tools.github import github_tool
from src.observability import logger


class CommitWatcher:
    def __init__(self):
        self._last_seen_sha: Optional[str] = None

    async def init(self):
        commits = await github_tool.get_recent_commits(since_minutes=60, limit=1)
        if commits:
            self._last_seen_sha = commits[0].sha

    async def check_and_reload(self) -> bool:
        """Detect a new config-changing commit and log it — DO NOT mutate the service.

        The running pool is controlled solely by the dashboard trigger (breaks it via
        /admin/pool/0) and by approval (restores it via /admin/pool/20). Earlier this method
        also re-applied the pool_size committed at the latest SHA, but that raced with the
        trigger's two commits (baseline 20 + breaking 0) and GitHub's commit-ordering lag,
        causing the live pool to oscillate 0→20→0 and reset the metrics mid-incident.
        Detect-and-log keeps the "agent noticed the deploy" narrative without those artifacts,
        and also inherently avoids the old self-heal race (nothing here reloads the service).
        """
        commits = await github_tool.get_recent_commits(since_minutes=60, limit=5)
        if not commits:
            return False

        latest = commits[0]

        if self._last_seen_sha == latest.sha:
            return False

        self._last_seen_sha = latest.sha

        config_files = [f for f in latest.files_changed if "config" in f or f.endswith(".yaml") or f.endswith(".yml")]
        if not config_files:
            return False

        logger.info("commit_watcher", event="config_change_detected", sha=latest.sha[:7],
                    message=latest.message, files=latest.files_changed)
        return True


commit_watcher = CommitWatcher()
