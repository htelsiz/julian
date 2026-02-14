"""Pydantic models for GitHub webhook payloads."""

from pydantic import BaseModel, model_validator


class WebhookContext(BaseModel):
    """Typed context parsed from a raw GitHub webhook payload.

    Flattens the nested webhook JSON into a single object with the fields
    that Julian's handlers actually use.
    """

    event_type: str
    action: str

    # Repository
    owner: str
    repo_name: str
    default_branch: str

    # Installation
    installation_id: int

    # PR fields (only present for pull_request events)
    pr_number: int | None = None
    pr_head_ref: str | None = None

    # Comment fields (only present for issue_comment events)
    issue_number: int | None = None
    comment_body: str | None = None

    @classmethod
    def from_webhook(cls, event_type: str, data: dict) -> "WebhookContext":
        """Parse a raw GitHub webhook payload into typed context."""
        action = data.get("action", "")
        repo = data.get("repository", {})
        installation = data.get("installation", {})

        fields: dict = {
            "event_type": event_type,
            "action": action,
            "owner": repo.get("owner", {}).get("login", ""),
            "repo_name": repo.get("name", ""),
            "default_branch": repo.get("default_branch", "main"),
            "installation_id": installation.get("id", 0),
        }

        # PR-specific
        pr = data.get("pull_request")
        if pr:
            fields["pr_number"] = pr.get("number")
            fields["pr_head_ref"] = pr.get("head", {}).get("ref")

        # Comment-specific
        issue = data.get("issue")
        if issue:
            fields["issue_number"] = issue.get("number")

        comment = data.get("comment")
        if comment:
            fields["comment_body"] = comment.get("body", "")

        return cls(**fields)

    @property
    def is_pr_review(self) -> bool:
        return self.event_type == "pull_request" and self.action in (
            "opened",
            "synchronize",
            "reopened",
        )

    @property
    def is_mention(self) -> bool:
        if self.event_type != "issue_comment" or self.action != "created":
            return False
        return self.comment_body is not None and "@julian" in self.comment_body.lower()
