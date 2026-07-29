from pydantic import BaseModel, ConfigDict


def to_kebab(field_name: str) -> str:
    return field_name.replace("_", "-")


class ConfigurationModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_kebab,
        populate_by_name=False,
        extra="forbid",
    )
