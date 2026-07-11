from typing import Optional
from datetime import datetime, timezone, timedelta
from src.tools.github import github_tool
from src.tools.deploy import deploy_tool
from src.observability import logger


class CommitWatcher:
    def __init__(self):
        self._last_seen_sha: Optional[str] = None

    async def init(self):
        commits = await github_tool.get_recent_commits(since_minutes=60, limit=1)
        if commits:
            self._last_seen_sha = commits[0].sha

    async def check_and_reload(self) -> bool:
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

        # Apply the pool_size committed at this SHA so the running service tracks GitHub
        # (a bad commit reinforces the outage; a revert/restore commit recovers it).
        # Reading from the commit — not a stale local file — is what prevents the
        # self-heal race that could resolve an incident before it is ever detected.
        pool_size = await github_tool.get_pool_size_at(latest.sha)
        if pool_size is None:
            # Fall back to local reload if we can't read the committed config.
            result = await deploy_tool.reload_config()
            return "error" not in result

        logger.info("commit_watcher", event="applying_committed_pool_size",
                    sha=latest.sha[:7], pool_size=pool_size)
        result = await deploy_tool.set_pool(pool_size)
        return "error" not in result


commit_watcher = CommitWatcher()
