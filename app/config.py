from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/bodhrik"
    REDIS_URL: str = "redis://redis:6379/0"
    SECRET_KEY: str = "supersecretjwtkeychangeinproduction12345!@#"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
