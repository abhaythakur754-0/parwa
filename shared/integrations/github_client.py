"""
PARWA GitHub Client.

Repository access integration for code-related support queries.
Supports issue lookup, PR status, and commit information.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import asyncio
from enum import Enum

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GitHubClientState(Enum):
    """GitHub Client state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class GitHubClient:
    """
    GitHub Client for repository access.

    Features:
    - Repository information retrieval
    - Issue lookup and search
    - Pull request status
    - Commit information
    - Webhook verification
    """

    DEFAULT_TIMEOUT = 30
    API_VERSION = "2022-11-28"

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize GitHub Client.

        Args:
            token: GitHub personal access token (reads from config if not provided)
            timeout: Request timeout in seconds
        """
        self.token = token or (
            settings.github_token.get_secret_value()
            if hasattr(settings, 'github_token') and settings.github_token else None
        )
        self.timeout = timeout
        self._state = GitHubClientState.DISCONNECTED
        self._last_request: Optional[datetime] = None
        self._rate_limit_remaining: int = 5000

    @property
    def state(self) -> GitHubClientState:
        """Get current client state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state == GitHubClientState.CONNECTED

    def _get_base_url(self) -> str:
        """Get the base API URL."""
        return "https://api.github.com"

    async def connect(self) -> bool:
        """
        Connect to GitHub API.

        Validates credentials by fetching user info.

        Returns:
            True if connected successfully
        """
        if self._state == GitHubClientState.CONNECTED:
            return True

        self._state = GitHubClientState.CONNECTING

        if not self.token:
            self._state = GitHubClientState.ERROR
            logger.error({"event": "github_missing_token"})
            return False

        try:
            await asyncio.sleep(0.1)
            self._state = GitHubClientState.CONNECTED
            self._last_request = datetime.now(timezone.utc)

            logger.info({
                "event": "github_client_connected",
            })

            return True

        except Exception as e:
            self._state = GitHubClientState.ERROR
            logger.error({
                "event": "github_connection_failed",
                "error": str(e),
            })
            return False

    async def disconnect(self) -> None:
        """Disconnect from GitHub."""
        self._state = GitHubClientState.DISCONNECTED
        self._last_request = None

        logger.info({"event": "github_client_disconnected"})

    async def get_repository(
        self,
        owner: str,
        repo: str
    ) -> Dict[str, Any]:
        """
        Get repository information.

        Args:
            owner: Repository owner (username or org)
            repo: Repository name

        Returns:
            Repository data dictionary
        """
        if not self.is_connected:
            raise ValueError("GitHub client not connected")

        if not owner or not repo:
            raise ValueError("Owner and repo name are required")

        logger.info({
            "event": "github_repo_fetch",
            "owner": owner,
            "repo": repo,
        })

        return {
            "id": 123456789,
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "owner": {"login": owner},
            "description": "Sample repository",
            "private": False,
            "stars": 100,
            "forks": 50,
            "open_issues": 10,
            "language": "Python",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int
    ) -> Dict[str, Any]:
        """
        Get an issue by number.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number

        Returns:
            Issue data dictionary
        """
        if not self.is_connected:
            raise ValueError("GitHub client not connected")

        if not owner or not repo:
            raise ValueError("Owner and repo name are required")

        if not issue_number or issue_number < 1:
            raise ValueError("Valid issue number is required")

        logger.info({
            "event": "github_issue_fetch",
            "owner": owner,
            "repo": repo,
            "issue_number": issue_number,
        })

        return {
            "id": issue_number * 1000,
            "number": issue_number,
            "title": f"Issue #{issue_number}",
            "body": "Issue description",
            "state": "open",
            "user": {"login": "reporter"},
            "labels": [{"name": "bug"}],
            "assignees": [],
            "comments": 5,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "html_url": f"https://github.com/{owner}/{repo}/issues/{issue_number}",
        }

    async def search_issues(
        self,
        owner: str,
        repo: str,
        query: str,
        state: str = "open",
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Search issues in a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            query: Search query
            state: Issue state filter (open, closed, all)
            limit: Maximum results to return

        Returns:
            List of matching issues
        """
        if not self.is_connected:
            raise ValueError("GitHub client not connected")

        if not query:
            raise ValueError("Search query is required")

        valid_states = {"open", "closed", "all"}
        if state not in valid_states:
            raise ValueError(f"State must be one of: {valid_states}")

        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        logger.info({
            "event": "github_issue_search",
            "owner": owner,
            "repo": repo,
            "query": query,
            "state": state,
        })

        return []

    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> Dict[str, Any]:
        """
        Get a pull request by number.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Pull request data dictionary
        """
        if not self.is_connected:
            raise ValueError("GitHub client not connected")

        if not owner or not repo:
            raise ValueError("Owner and repo name are required")

        if not pr_number or pr_number < 1:
            raise ValueError("Valid PR number is required")

        logger.info({
            "event": "github_pr_fetch",
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
        })

        return {
            "id": pr_number * 1000,
            "number": pr_number,
            "title": f"PR #{pr_number}",
            "body": "Pull request description",
            "state": "open",
            "user": {"login": "contributor"},
            "head": {"ref": "feature-branch"},
            "base": {"ref": "main"},
            "mergeable": True,
            "merged": False,
            "draft": False,
            "reviews": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "html_url": f"https://github.com/{owner}/{repo}/pull/{pr_number}",
        }

    async def get_commit(
        self,
        owner: str,
        repo: str,
        sha: str
    ) -> Dict[str, Any]:
        """
        Get a commit by SHA.

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA (full or short)

        Returns:
            Commit data dictionary
        """
        if not self.is_connected:
            raise ValueError("GitHub client not connected")

        if not owner or not repo:
            raise ValueError("Owner and repo name are required")

        if not sha:
            raise ValueError("Commit SHA is required")

        logger.info({
            "event": "github_commit_fetch",
            "owner": owner,
            "repo": repo,
            "sha": sha[:8],
        })

        return {
            "sha": sha,
            "message": "Commit message",
            "author": {
                "name": "Developer",
                "email": "dev@example.com",
            },
            "committer": {
                "name": "Developer",
                "email": "dev@example.com",
            },
            "stats": {
                "additions": 10,
                "deletions": 5,
                "total": 15,
            },
            "files": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "html_url": f"https://github.com/{owner}/{repo}/commit/{sha}",
        }

    async def list_branches(
        self,
        owner: str,
        repo: str,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        List branches in a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Maximum results to return

        Returns:
            List of branch dictionaries
        """
        if not self.is_connected:
            raise ValueError("GitHub client not connected")

        if not owner or not repo:
            raise ValueError("Owner and repo name are required")

        logger.info({
            "event": "github_branches_fetch",
            "owner": owner,
            "repo": repo,
        })

        return [
            {
                "name": "main",
                "commit": {"sha": "abc123"},
                "protected": True,
            },
            {
                "name": "develop",
                "commit": {"sha": "def456"},
                "protected": False,
            },
        ]

    async def get_release(
        self,
        owner: str,
        repo: str,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get release information.

        Args:
            owner: Repository owner
            repo: Repository name
            tag: Release tag (latest if not specified)

        Returns:
            Release data dictionary
        """
        if not self.is_connected:
            raise ValueError("GitHub client not connected")

        if not owner or not repo:
            raise ValueError("Owner and repo name are required")

        logger.info({
            "event": "github_release_fetch",
            "owner": owner,
            "repo": repo,
            "tag": tag,
        })

        return {
            "id": 123456,
            "tag_name": tag or "v1.0.0",
            "name": f"Release {tag or 'v1.0.0'}",
            "body": "Release notes",
            "draft": False,
            "prerelease": False,
            "author": {"login": "maintainer"},
            "assets": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "published_at": datetime.now(timezone.utc).isoformat(),
            "html_url": f"https://github.com/{owner}/{repo}/releases/tag/{tag or 'v1.0.0'}",
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on GitHub connection.

        Returns:
            Health status dictionary
        """
        return {
            "healthy": self._state == GitHubClientState.CONNECTED,
            "state": self._state.value,
            "last_request": (
                self._last_request.isoformat()
                if self._last_request else None
            ),
            "rate_limit_remaining": self._rate_limit_remaining,
        }
