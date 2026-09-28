import re
from collections import deque
from urllib.parse import urljoin, urlparse

import pytest
from django.test import Client

HREF = re.compile(r'(?:href|action|data-live|data-assess|data-autosave)="([^"#]+)"')


def crawl(client, starts=("/", "/dashboard/"), limit=600):
    seen, bad, queue = set(), [], deque([(s, "(start)") for s in starts])
    while queue and len(seen) < limit:
        url, src = queue.popleft()
        path = urlparse(url).path + (("?" + urlparse(url).query) if urlparse(url).query else "")
        if path in seen or not path.startswith("/") or path.startswith(("/static/", "/admin/")) or "export=csv" in path or "logout" in path:
            continue
        seen.add(path)
        r = client.get(path, follow=True)
        final = r.redirect_chain[-1][0] if r.redirect_chain else path
        if r.status_code >= 400 and r.status_code not in (405,):
            bad.append((r.status_code, path, final, src))
            continue
        if "text/html" in r.get("Content-Type", ""):
            for link in HREF.findall(r.content.decode()):
                link = link.replace("&amp;", "&")
                if link.startswith(("http://", "https://", "mailto:", "javascript:")) and "testserver" not in link:
                    continue
                queue.append((urljoin(path, link), path))
    return seen, bad


@pytest.mark.parametrize("role", [None, "receptionist", "nurse", "physician", "student", "admin"])
def test_every_link_each_role_can_reach_works(role, as_role):
    """Follow every link and form address on every reachable page, as each kind of user. Nothing may error."""
    client = as_role(role) if role else Client()
    seen, bad = crawl(client)
    assert len(seen) >= (5 if role in (None, "student") else 20)
    assert bad == [], bad


PW = "CareBoard-Demo1!"


@pytest.mark.parametrize("email,link,lands_on", [
    ("student@careboard.demo", "/patients/", "/portal/"),
    ("admin@careboard.demo", "/triage/", "/manage/"),
    ("nurse.reyes@careboard.demo", "/manage/users/", "/dashboard/"),
    ("sarah.cole@careboard.demo", "/triage/", "/dashboard/"),
    ("dr.henderson@careboard.demo", "/portal/", "/dashboard/"),
    ("nurse.reyes@careboard.demo", "/triage/", "/triage/"),          # allowed links are kept
    ("admin@careboard.demo", "/manage/logs/", "/manage/logs/"),
    ("student@careboard.demo", "/portal/visits/", "/portal/visits/"),
])
def test_signing_in_from_another_roles_link_goes_somewhere_allowed(seeded, email, link, lands_on):
    r = Client().post(f"/login/?next={link}", {"username": email, "password": PW, "next": link}, follow=True)
    assert r.status_code == 200 and r.request["PATH_INFO"] == lands_on


def test_back_button_on_an_action_goes_home_with_a_note(as_role):
    from apps.history.models import Visit

    v = Visit.objects.filter(status="registered").first()
    nurse = as_role("nurse")
    for url in (f"/triage/{v.pk}/start/", f"/history/visit/{v.pk}/close/", f"/triage/{v.pk}/takeover/"):
        r = nurse.get(url, follow=True)
        assert r.status_code == 200 and r.request["PATH_INFO"] == "/dashboard/" and b"only works from its button" in r.content
    v.refresh_from_db()
    assert v.status == "registered"                                   # nothing happened


def test_background_requests_still_get_a_plain_refusal(as_role):
    from apps.history.models import Visit

    v = Visit.objects.filter(status="with_doctor").first()
    assert as_role("physician").get(f"/triage/{v.pk}/assess/", HTTP_X_REQUESTED_WITH="fetch").status_code == 405


def test_no_access_page_is_friendly(as_role):
    r = as_role("nurse").get("/manage/")
    assert r.status_code == 403 and b"Go to my home page" in r.content and b"system administrators only" in r.content


def test_friendly_404_and_expired_form_pages(client, settings, seeded):
    settings.DEBUG = False
    r = client.get("/patients/does-not-exist/")
    assert r.status_code == 404 and b"couldn't find that page" in r.content.replace(b"&#x27;", b"'")
    csrf_client = Client(enforce_csrf_checks=True)
    r = csrf_client.post("/login/", {"username": "x", "password": "y"})
    assert r.status_code == 403 and b"Please try that again" in r.content
