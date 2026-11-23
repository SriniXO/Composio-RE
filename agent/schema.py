"""Fixed record schema. One JSON record per app. Unknown => 'unclear' / 'unverified', never a guess."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

AuthMethod = Literal["oauth2", "api_key", "basic", "bearer_token", "jwt", "other"]
SelfServe = Literal["yes", "trial", "paid_required", "admin_approval", "partner_gated", "contact_sales", "unclear"]
Blocker = Literal["none", "partner_approval", "paid_plan", "no_public_api", "enterprise_only",
                  "review_process", "tos_restriction", "cli_only", "other"]
Buildability = Literal["ready_now", "ready_with_caveats", "blocked", "unverified"]
Form = Literal["MCP server", "agent skills", "CLI wrapper", "not feasible", "unverified"]


class Evidence(BaseModel):
    url: str
    quote_snippet: str = Field(description="<25 words, copied verbatim from the fetched page text")
    field_supported: str
    fetched_at: str = ""
    quote_verified: bool = False  # set by code (substring check), never by the LLM


class ApiSurface(BaseModel):
    type: Literal["REST", "GraphQL", "SOAP", "SDK-only", "none", "unclear"] = "unclear"
    breadth: Literal["narrow", "medium", "broad", "unclear"] = "unclear"
    docs_quality: Literal["good", "ok", "poor", "unclear"] = "unclear"
    openapi_spec_url: Optional[str] = None
    rate_limits: Optional[str] = None


class ExistingMcp(BaseModel):
    exists: Optional[bool] = None  # None = unverified
    official: Optional[bool] = None
    url: Optional[str] = None


class NeedsHuman(BaseModel):
    flag: bool = False
    reason: str = ""


class AppRecord(BaseModel):
    id: int
    app: str
    category: str
    one_line_description: str = ""
    website: str = ""
    auth_methods: list[AuthMethod] = []
    auth_notes: str = ""
    self_serve: SelfServe = "unclear"
    gate_detail: str = ""
    api_surface: ApiSurface = ApiSurface()
    existing_mcp: ExistingMcp = ExistingMcp()
    composio_status: Literal["has_toolkit", "no_toolkit", "unverified"] = "unverified"
    buildability: Buildability = "unverified"
    main_blocker: Blocker = "other"
    blocker_detail: str = ""
    suggested_form: Form = "unverified"
    webhooks: Optional[bool] = None
    pagination: str = ""
    sandbox_test_env: Optional[bool] = None
    sdk_languages: list[str] = []
    api_access_pricing: str = ""
    time_to_first_call: Literal["minutes", "hours", "days", "weeks", "unclear"] = "unclear"
    outreach_needed: Optional[bool] = None
    evidence: list[Evidence] = []
    confidence: Literal["high", "med", "low"] = "low"
    needs_human: NeedsHuman = NeedsHuman()
    pass_name: str = ""
    verification_log: list[str] = []
