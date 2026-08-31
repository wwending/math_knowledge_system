import os
import tempfile
from unittest import TestCase, mock

from alembic import command
from sqlalchemy import create_engine, text

from app.db.migrations import get_alembic_config


class Issue147AuthMigrationTests(TestCase):
    def test_upgrade_inherits_environment_then_database_remains_authoritative(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            url = f"sqlite:///{os.path.join(temp_dir, 'auth-migration.db')}"
            config = get_alembic_config(url)
            command.upgrade(config, "20260830_0012")
            with mock.patch.dict(os.environ, {"PUBLIC_SIGNUP_ENABLED": "false"}):
                command.upgrade(config, "head")
            engine = create_engine(url)
            try:
                with engine.begin() as connection:
                    self.assertEqual(connection.execute(text("SELECT public_signup_enabled FROM auth_settings WHERE id=1")).scalar_one(), 0)
                    connection.execute(text("UPDATE auth_settings SET public_signup_enabled=1 WHERE id=1"))
                with mock.patch.dict(os.environ, {"PUBLIC_SIGNUP_ENABLED": "false"}):
                    with engine.connect() as connection:
                        self.assertEqual(connection.execute(text("SELECT public_signup_enabled FROM auth_settings WHERE id=1")).scalar_one(), 1)
                command.downgrade(config, "20260830_0012")
                command.upgrade(config, "head")
            finally:
                engine.dispose()

    def test_new_install_defaults_public_signup_on(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PUBLIC_SIGNUP_ENABLED", None)
            url = f"sqlite:///{os.path.join(temp_dir, 'fresh.db')}"
            command.upgrade(get_alembic_config(url), "head")
            engine = create_engine(url)
            try:
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(text("SELECT public_signup_enabled FROM auth_settings WHERE id=1")).scalar_one(), 1)
                    self.assertIsNotNone(connection.execute(text("SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_users_preserve_last_super_admin'")).scalar_one())
            finally:
                engine.dispose()
