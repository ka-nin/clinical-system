import pytest
from django.core.management import call_command
from django.test import Client

PW = "CareBoard-Demo1!"
EMAILS = {
    "receptionist": "sarah.cole@careboard.demo", "nurse": "nurse.reyes@careboard.demo", "physician": "dr.henderson@careboard.demo",
    "student": "student@careboard.demo", "admin": "admin@careboard.demo",
}


@pytest.fixture
def seeded(db):
    call_command("seed_demo", force=True, verbosity=0)


@pytest.fixture
def as_role(seeded):
    """as_role('nurse') -> a fresh test client signed in as that demo account."""

    def make(role):
        client = Client()
        assert client.login(username=EMAILS[role], password=PW)
        return client

    return make


@pytest.fixture(autouse=True)
def _fresh_cache():
    from django.core.cache import cache

    cache.clear()
