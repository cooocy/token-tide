from pydantic import BaseModel, Field


class ApplicationInfo(BaseModel):
    app: str
    ts: str
    token_tide_commit: str = Field(alias="TOKEN_TIDE_COMMIT")
