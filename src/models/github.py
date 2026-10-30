"""Pydantic models for GitHub webhook payloads.

The webhook JSON is mirrored declaratively as nested models and parsed with
``model_validate`` — no manual dict digging, no defensive ``.get()`` chains.
Fields absent for a given event type fall back to their typed defaults, and
nullable string fields (e.g. a PR body) coerce ``null`` to ``""`` via the
``NullableStr`` type rather than call-site conditionals.
"""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# GitHub sends ``null`` for optional strings like a PR/comment body; coerce to ""
# declaratively so downstream code always sees a plain str.
NullableStr = Annotated[str, BeforeValidator(lambda v: v or "")]


class _Model(BaseModel):
    """Base for all payload models: ignore the many fields we don't consume."""

    model_config = ConfigDict(extra="ignore")


class Owner(_Model):
    login: str = ""


class Repository(_Model):
    name: str = ""
    owner: Owner = Field(default_factory=Owner)
    default_branch: str = "main"


class Installation(_Model):
    id: int = 0


class Head(_Model):
    ref: str = ""
    sha: str = ""


class PullRequest(_Model):
    number: int = 0
    title: NullableStr = ""
    body: NullableStr = ""
    head: Head = Field(default_factory=Head)


class Issue(_Model):
    number: int = 0


class Comment(_Model):
    body: NullableStr = ""


class WebhookPayload(_Model):
    """Declarative mirror of the GitHub webhook JSON Julian consumes.

    Every top-level object defaults to an empty model, so a payload for one
    event type (e.g. a comment, with no ``pull_request``) validates cleanly and
    the irrelevant sections simply read as their defaults.
    """

    action: str = ""
    repository: Repository = Field(default_factory=Repository)
    installation: Installation = Field(default_factory=Installation)
    pull_request: PullRequest = Field(default_factory=PullRequest)
    issue: Issue = Field(default_factory=Issue)
    comment: Comment = Field(default_factory=Comment)


class WebhookContext(_Model):
    """Parsed webhook payload plus the event name.

    Exposes flat, typed accessors over the nested payload so handlers read
    ``ctx.pr_head_sha`` rather than walking the raw JSON.
    """

    event_type: str
    payload: WebhookPayload = Field(default_factory=WebhookPayload)

    @classmethod
    def from_webhook(cls, event_type: str, data: dict) -> "WebhookContext":
        """Parse a raw GitHub webhook payload into typed context."""
        return cls(event_type=event_type, payload=WebhookPayload.model_validate(data))

    # -- flat accessors (plain typed reads, no digging) ----------------------

    @property
    def action(self) -> str:
        return self.payload.action

    @property
    def owner(self) -> str:
        return self.payload.repository.owner.login

    @property
    def repo_name(self) -> str:
        return self.payload.repository.name

    @property
    def default_branch(self) -> str:
        return self.payload.repository.default_branch

    @property
    def installation_id(self) -> int:
        return self.payload.installation.id

    @property
    def pr_number(self) -> int:
        return self.payload.pull_request.number

    @property
    def pr_head_ref(self) -> str:
        return self.payload.pull_request.head.ref

    @property
    def pr_head_sha(self) -> str:
        return self.payload.pull_request.head.sha

    @property
    def pr_title(self) -> str:
        return self.payload.pull_request.title

    @property
    def pr_body(self) -> str:
        return self.payload.pull_request.body

    @property
    def issue_number(self) -> int:
        return self.payload.issue.number

    @property
    def comment_body(self) -> str:
        return self.payload.comment.body

    # -- event predicates ----------------------------------------------------

    @property
    def is_pr_review(self) -> bool:
        return self.event_type == "pull_request" and self.action in ("opened", "synchronize", "reopened")

    @property
    def is_mention(self) -> bool:
        return (
            self.event_type == "issue_comment"
            and self.action == "created"
            and "@julian" in self.comment_body.lower()
        )
