from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["proxy"])


class ProxyRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    repo_path: str = Field(..., min_length=1)


class ProxyResponse(BaseModel):
    code: str
    resolved_dependencies: list[dict]
    validation_passed: bool
    violations: list[dict]


@router.post("/generate", response_model=ProxyResponse)
async def generate(request: ProxyRequest) -> ProxyResponse:
    """
    Orchestration proxy endpoint.
    Accepts a user prompt and a local repo path.
    Returns validated, version-accurate generated code.
    """
    ...
