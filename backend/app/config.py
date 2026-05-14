from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_user: str = "crypto_user"
    postgres_password: str = "crypto_password"
    postgres_db: str = "crypto_signal_radar"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")
    kafka_bootstrap_servers: str = "kafka:9092"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
