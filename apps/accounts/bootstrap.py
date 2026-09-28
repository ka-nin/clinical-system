"""First-start setup for hosted demos: bring the database up to date and add the demo data once.

Runs when the web app starts (AUTO_SETUP=1), so a fresh Wasmer deployment works with no manual steps.
A database lock makes sure only one copy of the app does this, even if several start at the same moment.
"""
import logging
import os
from contextlib import contextmanager

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

logger = logging.getLogger(__name__)
LOCK_NAME = "careboard_setup"


@contextmanager
def _setup_lock(timeout=120):
    """A lock shared by every app instance. MySQL has named locks; other databases fall back to no lock."""
    if connection.vendor != "mysql":
        yield True
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, %s)", [LOCK_NAME, timeout])
        got = cursor.fetchone()[0] == 1
    try:
        yield got
    finally:
        if got:
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", [LOCK_NAME])


def pending_migrations():
    executor = MigrationExecutor(connection)
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


def prepare_database():
    try:
        with _setup_lock() as got:
            if not got:
                logger.warning("Another instance is setting up the database; continuing without waiting.")
                return
            if pending_migrations():
                logger.info("Applying database migrations.")
                call_command("migrate", interactive=False, verbosity=0)
            if os.environ.get("DEMO_MODE") == "1":
                call_command("seed_demo", force=True, if_empty=True, verbosity=0)
    except Exception:  # noqa: BLE001 - never stop the site from starting; the error is in the logs
        logger.exception("Automatic database setup failed.")
    finally:
        if not connection.in_atomic_block:  # hand each web worker a fresh connection; never close one mid-transaction
            connection.close()
