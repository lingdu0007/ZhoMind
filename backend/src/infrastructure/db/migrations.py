from pathlib import Path

from alembic import command
from alembic.config import Config

from src.infrastructure.config.settings import get_settings


def run_migrations() -> None:
    backend_dir = Path(__file__).resolve().parents[3]
    alembic_ini = backend_dir / "alembic.ini"
    settings = get_settings()

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
