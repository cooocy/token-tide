from pydantic import SecretStr, field_validator

from token_tide.configuration import ConfigurationModel


class TokenUsageSettings(ConfigurationModel):
    auth_token: SecretStr

    @field_validator("auth_token")
    @classmethod
    def validate_auth_token(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("auth-token must not be empty")
        return value
