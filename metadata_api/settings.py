"""Default configuration settings for the Metadata API."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Default app settings."""
    ENV: str = "production"  # Environment: production or development
    STATIC: Path = Path(__file__).parent / "static"
    ROOT_PATH: str = ""  # Root path for the API, e.g. "/metadata-api" if served from a subpath

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(levelname)s - %(message)s"
    LOG_DIR: Path = Path("logs")
    LOG_TO_FILE: bool = True  # Always log to console; if True, also log to a file in LOG_DIR

    RESOURCE_TYPES: list[str] = ["corpus", "lexicon", "model", "analysis", "utility", "collection"]
    # Resource types and their corresponding data files (relative to "static" directory)
    RESOURCES: dict[str, str] = {
        "corpora": "corpus.json",
        "lexicons": "lexicon.json",
        "models": "model.json",
        "analyses": "analysis.json",
        "utilities": "utility.json",
    }
    # Resource texts file and collections file (relative to "static" directory)
    RESOURCE_TEXTS_FILE: str = "resource-texts.json"
    COLLECTIONS_FILE: str = "collection.json"

    # Absolute path to directory containing the metadata yaml files (https://github.com/spraakbanken/metadata)
    METADATA_DIR: Path = Path("/home/fksbwww/metadata-api/dev/metadata")
    # Paths relative to metadata directory
    SCHEMA_FILE: str = "schema/metadata.json"
    YAML_DIR: str = "yaml"
    LOCALIZATIONS_DIR: str = "localizations"

    # GitHub limit for modified/added files to list in a webhook payload
    GITHUB_FILE_LIMIT: int = 3000

    # Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    PENDING_KEY: str = "metadata_api:renew_cache:pending"  # Redis key to track pending cache renewal tasks
    MAX_PENDING: int = 3  # Maximum number of pending cache renewal tasks

    # Caching settings
    MEMCACHED_SERVER: str = ""  # e.g. "localhost:11211". Set to "" to disable caching

    # Slack incoming webhook URL, used to send error messages to a Slack channel
    SLACK_WEBHOOK: str = ""

    # Override Settings with variables from a .env file or environment variables
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
