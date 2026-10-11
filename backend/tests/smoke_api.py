"""One-shot API smoke test against a running server. Not part of the unit suite.

Letters with codes are read from MAIL_FILE_DIR (MAIL_MODE=file, as in CI) or, when MAILPIT_URL is set,
from Mailpit (the docker compose stand: `make check`).
"""
import glob
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8010/api/v1")
_SIGNIN_COOKIE = ""
# The API must run with MAIL_MODE=file and the same MAIL_FILE_DIR, or deliver to Mailpit at MAILPIT_URL.
MAIL_DIR = os.environ.get("MAIL_FILE_DIR", "/tmp/fsp-talent-mail")
MAILPIT = os.environ.get("MAILPIT_URL", "").rstrip("/")
# SMOKE_MAIL=demo: a public demo stand without a mailbox we can read; the confirmation code comes in the
# registration answer (DEMO_MODE and DEMO_SHOW_CODE on the stand), steps that need other letters are skipped.
DEMO_MAIL = os.environ.get("SMOKE_MAIL", "") == "demo"
DEMO_CODES = {}
SUBJECT_PURPOSE = {"Код подтверждения": "verify", "Сброс пароля": "reset",
                   "Согласие законного представителя": "guardian"}
EMPLOYER = {"username": "hr@sibcode.demo", "password": "demo12345"}
CANDIDATE = {"username": "fsp001@demo.talent", "password": "demo12345"}
REQUIRED_CANDIDATE_CONSENTS = ["terms", "pd_candidate"]


def _note_signin_cookie(headers) -> None:
    global _SIGNIN_COOKIE
    raw = headers.get("Set-Cookie") or ""
    if "fsp_signin=" not in raw:
        return
    pair = raw.split(";", 1)[0]
    value = pair.split("=", 1)[1]
    _SIGNIN_COOKIE = "" if not value or "Max-Age=0" in raw else pair


def call(method, path, body=None, token=None, form=None, cookie=None):
    data = None
    headers = {}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            _note_signin_cookie(response.headers)
            raw = response.read().decode()
            payload = json.loads(raw) if raw else None
            if isinstance(payload, dict) and payload.get("demo_code"):
                DEMO_CODES[payload["email"]] = payload["demo_code"]
            return response.status, payload
    except urllib.error.HTTPError as error:
        _note_signin_cookie(error.headers)
        raw = error.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return error.code, payload


def _mailpit_letter(email, purpose):
    query = urllib.parse.urlencode({"query": f'to:"{email}"'})
    with urllib.request.urlopen(f"{MAILPIT}/api/v1/search?{query}", timeout=5) as resp:
        messages = json.load(resp).get("messages") or []
    for message in messages:   # newest first
        if not any(message["Subject"].startswith(p) and k == purpose for p, k in SUBJECT_PURPOSE.items()):
            continue
        with urllib.request.urlopen(f"{MAILPIT}/api/v1/message/{message['ID']}", timeout=5) as resp:
            text = json.load(resp)["Text"]
        code = re.search(r"\b(\d{6})\b", text)
        token = re.search(r"token=([\w.-]+)", text)
        return {"to": email, "purpose": purpose, "code": code.group(1) if code else None,
                "token": token.group(1) if token else None}
    return None


def last_letter(email, purpose="verify", timeout=10.0):
    if DEMO_MAIL:
        assert purpose == "verify" and email in DEMO_CODES, f"stand did not return demo_code for {email}"
        return {"to": email, "purpose": purpose, "code": DEMO_CODES[email], "token": None}
    deadline = time.time() + timeout
    while time.time() < deadline:
        if MAILPIT:
            letter = _mailpit_letter(email, purpose)
            if letter:
                return letter
            time.sleep(0.3)
            continue
        for path in sorted(glob.glob(os.path.join(MAIL_DIR, "*.json")), reverse=True):
            with open(path, encoding="utf-8") as fh:
                letter = json.load(fh)
            if letter["to"] == email and letter.get("purpose") == purpose:
                return letter
        time.sleep(0.2)
    raise AssertionError(f"no {purpose} letter for {email} in {MAIL_DIR}")


def link_fsp(token, fsp_id, password="test"):
    """FSP ID by OpenID Connect: start, log in on the (demo) provider page, return with code and state."""
    status, started = call("POST", "/candidates/me/fsp/authorize", token=token)
    assert status == 200 and started["provider"] == "mock", started
    query = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(started["authorize_url"]).query).items()}
    assert query["code_challenge_method"] == "S256", query
    status, login = call("POST", "/fsp-id-demo/login", {"fsp_id": fsp_id, "password": password, **{
        k: query[k] for k in ("client_id", "redirect_uri", "state", "code_challenge", "code_challenge_method")}})
    if status != 200:
        return status, login
    back = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(login["redirect_to"]).query).items()}
    return call("POST", "/candidates/me/fsp/callback", {"code": back["code"], "state": back["state"]}, token=token)


def check_registration():
    """TZ 2.2 п.4 and TZ 2.1: email registration with confirmation, a candidate without FSP history."""
    email = f"smoke-{int(time.time() * 1000)}@example.com"
    body = {"email": email, "password": "smoke-pass-1", "display_name": "Смоук Тест", "is_adult": True}
    status, refused = call("POST", "/auth/participant/register", {**body, "consents": ["terms"]})
    assert status == 422 and refused["error"]["code"] == "consent_required", refused
    assert refused["error"]["details"]["missing"] == ["pd_candidate"], refused
    status, sent = call("POST", "/auth/participant/register", {**body, "consents": REQUIRED_CANDIDATE_CONSENTS})
    assert status == 202 and sent["status"] == "verification_sent", sent
    status, early = call("POST", "/auth/participant/token", form={"username": email, "password": "smoke-pass-1"})
    assert status == 403 and early["error"]["code"] == "email_not_verified", early
    status, wrong = call("POST", "/auth/verify-email", {"email": email, "code": "000000"})
    letter = last_letter(email)
    if letter["code"] != "000000":
        assert status == 400 and wrong["error"]["code"] == "verification_invalid", wrong
    status, tokens = call("POST", "/auth/verify-email", {"email": email, "code": letter["code"]})
    assert status == 200 and tokens["role"] == "participant", tokens
    if letter["token"]:
        status, again = call("POST", "/auth/verify-email", {"token": letter["token"]})
        assert status == 400 and again["error"]["code"] == "verification_invalid", again
    status, taken = call("POST", "/auth/participant/register", {**body, "consents": REQUIRED_CANDIDATE_CONSENTS})
    assert status == 202 and taken["status"] == "verification_sent" and taken.get("demo_code") in (None, ""), taken
    status, login = call("POST", "/auth/participant/token", form={"username": email, "password": "smoke-pass-1"})
    assert status == 200, login
    token = login["access_token"]
    status, me = call("GET", "/candidates/me", token=token)
    assert status == 200 and me["has_fsp"] is False and me["email_verified"] and me["email"] == email, me
    status, consents = call("GET", "/me/consents", token=token)
    active = sorted(c["kind"] for c in consents if c["active"])
    assert status == 200 and active == sorted(REQUIRED_CANDIDATE_CONSENTS), consents
    status, public = call("PUT", "/candidates/me/profile", {"public_profile": True}, token=token)
    assert status == 409 and public["error"]["details"]["missing"] == ["pd_distribution"], public
    status, taken_fsp = link_fsp(token, "FSP001")
    assert status == 409 and taken_fsp["error"]["code"] == "fsp_taken", taken_fsp
    status, bad_fsp = link_fsp(token, "FSP2001", password="nope")
    assert status == 400 and bad_fsp["error"]["code"] == "fsp_invalid", bad_fsp
    # A random free id from the mock's unclaimed range; ids linked by earlier runs answer 409 and are skipped.
    for fsp_id in unclaimed_ids():
        status, linked = link_fsp(token, fsp_id)
        if status != 409:
            break
        assert linked["error"]["code"] == "fsp_taken", linked
    if status == 409:   # every unclaimed id is linked already (a database after 100 runs)
        print("FSP LINK skipped: no unclaimed mock id left")
    else:
        assert status == 200 and linked["fsp_id"] == fsp_id and linked["results"] >= 1, linked
        status, me = call("GET", "/candidates/me", token=token)
        assert me["has_fsp"] and me["display_name"] == "Смоук Тест", me
    status, reset = call("POST", "/auth/password/forgot", {"email": email, "role": "participant"})
    assert status == 202, reset
    if DEMO_MAIL:
        print("REGISTRATION OK by demo code; password reset letter skipped: no mailbox on the stand")
        return
    code = last_letter(email, "reset")["code"]
    status, changed = call("POST", "/auth/password/reset",
                           {"email": email, "role": "participant", "code": code, "new_password": "smoke-pass-2"})
    assert status == 200, changed
    status, old = call("POST", "/auth/participant/token", form={"username": email, "password": "smoke-pass-1"})
    assert status == 401 and old["error"]["code"] == "invalid_credentials", old


def _new_candidate(tag: str) -> tuple[str, str, str]:
    email = f"{tag}-{int(time.time() * 1000)}@example.com"
    status, sent = call("POST", "/auth/participant/register", {
        "email": email, "password": "smoke-pass-1", "display_name": "Удаляемый Кандидат", "is_adult": True,
        "consents": REQUIRED_CANDIDATE_CONSENTS})
    assert status == 202, sent
    status, tokens = call("POST", "/auth/verify-email", {"email": email, "code": last_letter(email)["code"]})
    assert status == 200, tokens
    # Employers see only a candidate with a birth date on file (Participant.discoverable); the 18+ box is not one.
    status, saved = call("PUT", "/candidates/me/profile", {"birth_date": "2000-01-01"}, token=tokens["access_token"])
    assert status == 200, saved
    status, me = call("GET", "/candidates/me", token=tokens["access_token"])
    return email, tokens["access_token"], me["id"]


def check_erasure(employer_token):
    """152-FZ: no contacts after the consent is withdrawn; deleting the account erases the person."""
    email, token, cid = _new_candidate("erase")
    status, offer = call("POST", "/offers/", {
        "candidate_id": cid, "salary_from_gross": 150000, "salary_to_gross": 200000, "role": "Backend",
        "work_format": "remote", "contact_method": "hr@sibcode.demo"}, token=employer_token)
    assert status == 201, offer
    status, _ = call("POST", f"/candidates/me/offers/{offer['id']}/respond", {"action": "accept"}, token=token)
    assert status == 200
    status, contacts = call("GET", f"/offers/{offer['id']}/contacts", token=employer_token)
    assert status == 200 and contacts["email"] == email, contacts
    status, _ = call("DELETE", "/me/consents/pd_candidate", token=token)
    assert status == 200
    status, closed = call("GET", f"/offers/{offer['id']}/contacts", token=employer_token)
    assert status == 403 and closed["error"]["code"] == "consent_withdrawn", closed
    status, wrong = call("DELETE", "/candidates/me", {"confirm": "да"}, token=token)
    assert status == 422 and wrong["error"]["code"] == "delete_confirm", wrong
    status, gone = call("DELETE", "/candidates/me", {"confirm": "удалить", "password": "smoke-pass-1"}, token=token)
    assert status == 200 and gone["deleted"], gone
    status, login = call("POST", "/auth/participant/token", form={"username": email, "password": "smoke-pass-1"})
    assert status == 401, login
    status, me = call("GET", "/candidates/me", token=token)
    assert status == 401, me
    status, closed = call("GET", f"/offers/{offer['id']}/contacts", token=employer_token)
    assert status == 403, closed


def main():
    with urllib.request.urlopen(BASE.replace("/api/v1", "/health")) as response:
        print("health", json.loads(response.read().decode()))
    status, document = call("GET", "/public/issuer")
    assert status == 200 and document["verificationMethod"][0]["publicKeyMultibase"].startswith("z"), document
    status, employer = call("POST", "/auth/employer/token", form=EMPLOYER)
    assert status == 200, employer
    employer_token = employer["access_token"]
    status, bank = call("GET", "/search/bank", token=employer_token)
    assert status == 200 and bank["cells"], bank
    assert all(c["candidates"] is None or c["candidates"] >= bank["min_cell"] for c in bank["cells"]), bank
    status, participant = call("POST", "/auth/participant/token", form=CANDIDATE)
    assert status == 200, participant
    participant_token = participant["access_token"]
    status, me = call("GET", "/candidates/me", token=participant_token)
    assert status == 200 and me["fsp_id"] == "FSP001" and me["grade"] == "middle", me
    # TZ 2.1, regular tasks: an employer's vacancy offers this week's short task; solving it refreshes the card.
    status, weekly = call("GET", "/assessment/practice/weekly", token=participant_token)
    assert status == 200 and weekly and weekly["vacancy_id"] and weekly["company"], weekly
    status, task = call("POST", "/assessment/practice/start", {"vacancy_id": weekly["vacancy_id"]},
                        token=participant_token)
    assert status == 200 and task["stem"], task
    answer = {"answer_text": "0"} if task["answer_mode"] == "number" else {"answer_index": 0}
    status, done = call("POST", f"/assessment/practice/{task['id']}/answer", answer, token=participant_token)
    assert status == 200 and done["answered"], done
    status, weekly = call("GET", "/assessment/practice/weekly", token=participant_token)
    assert weekly["done"] is True, weekly
    status, legacy = call("POST", "/auth/participant/token", form={"username": "FSP001", "password": "test"})
    assert status == 401 and legacy["error"]["code"] == "invalid_credentials", legacy
    check_registration()
    status, bad_salary = call("POST", "/offers/", {
        "candidate_id": me["id"], "salary_from_gross": 200, "salary_to_gross": 100,
        "role": "Backend", "work_format": "remote", "contact_method": "hr@sibcode.demo",
    }, token=employer_token)
    assert status == 422, bad_salary
    status, found = call("GET", "/search/candidates?q=Python%20backend&skills=Go,FastAPI&limit=10",
                         token=employer_token)
    assert status == 200 and found["total"] > 0, found
    card = next(item for item in found["items"] if item["candidate_id"] == me["id"])
    assert "display_name" not in card and "Go" in card["matched_skills"] and card["why"], card
    status, offer = call("POST", "/offers/", {
        "candidate_id": me["id"], "salary_from_gross": 180000, "salary_to_gross": 260000,
        "role": "Backend-разработчик", "work_format": "remote", "message": "Ждём в команде",
        "contact_method": "@sibcode_hr",
    }, token=employer_token)
    assert status == 201, offer
    status, seen = call("GET", "/candidates/me/offers", token=participant_token)
    mine = next(o for o in seen if o["id"] == offer["id"])
    assert status == 200 and mine["contact_method"] == "@sibcode_hr", mine
    status, listed = call("GET", "/offers/", token=employer_token)
    assert next(o for o in listed if o["id"] == offer["id"])["candidate_viewed_at"], "viewed status not recorded"
    status, no_salary = call("POST", "/vacancies/", {"title": "Без вилки", "skills": ["Python"]}, token=employer_token)
    assert status == 422, no_salary
    status, denied = call("GET", f"/offers/{offer['id']}/contacts", token=employer_token)
    assert status == 403, denied
    status, bell = call("GET", "/notifications", token=participant_token)
    note = next(n for n in bell["items"] if n["kind"] == "offer_new")
    assert status == 200 and bell["unread"] >= 1 and "180 000" in note["body"], bell
    letters = []
    for path in glob.glob(os.path.join(MAIL_DIR, "*.json")):
        with open(path, encoding="utf-8") as fh:
            letters.append(json.load(fh))
    if letters:   # file mail mode: the invitation letter went to the candidate
        assert any(x["to"] == CANDIDATE["username"] and "Приглашение" in x["subject"] for x in letters)
    status, read = call("POST", f"/notifications/{note['id']}/read", token=participant_token)
    assert status == 200 and read["read"], read
    status, foreign = call("POST", f"/notifications/{note['id']}/read", token=employer_token)
    assert status == 404, foreign
    status, accepted = call("POST", f"/candidates/me/offers/{offer['id']}/respond",
                            {"action": "accept"}, token=participant_token)
    assert status == 200 and accepted["status"] == "accepted", accepted
    status, again = call("POST", f"/candidates/me/offers/{offer['id']}/respond",
                         {"action": "reject"}, token=participant_token)
    assert status == 409, again
    status, contacts = call("GET", f"/offers/{offer['id']}/contacts", token=employer_token)
    assert status == 200 and contacts["display_name"] and contacts["email"], contacts
    check_messages(offer["id"], employer_token, participant_token)
    status, bell = call("GET", "/notifications", token=employer_token)
    assert status == 200 and any(n["kind"] == "offer_accepted" for n in bell["items"]), bell
    status, public = call("GET", f"/public/candidates/{me['id']}")
    assert status == 200 and "fsp_id" not in public and public["display_name"], public
    status, board = call("GET", "/public/leaderboard?discipline=algorithmic")
    assert status == 200 and board and "fsp_id" not in board[0]
    assert all(row["display_name"].startswith("Участник ") for row in board)    # /jury: a list without names
    assert board == sorted(board, key=lambda row: -row["lcb"])
    status, credentials = call("GET", f"/public/credentials/{me['id']}")
    assert status == 200 and credentials and credentials[0]["valid"]
    status, verified = call("GET", f"/public/credentials/verify/{credentials[0]['id']}")
    assert status == 200 and verified["valid"]
    tampered = json.loads(json.dumps(credentials[0]["credential"]))
    tampered["credentialSubject"]["achievement"]["place"] = 999
    status, forged = call("POST", "/public/credentials/verify", tampered)
    assert status == 200 and forged["valid"] is False, forged
    status, parsed = call("POST", "/ai/parse-resume",
                          {"text": "Пишу сервисы на Python и FastAPI, немного С++"}, token=participant_token)
    names = sorted(item["name"] for item in parsed["skills"])
    assert status == 200 and names == ["C++", "FastAPI", "Python"], parsed
    status, query = call("POST", "/ai/parse-query", {"q": "сеньор бэкенд python ctf"}, token=employer_token)
    assert status == 200 and query["role"] == "backend" and query["grade"] == "senior", query
    assert "Python" in query["skills"], query
    check_needs(employer_token)
    check_employer_tasks(employer_token, participant_token, me["id"])
    check_fsp_signin(me["id"])
    check_survey_gate(employer_token)
    check_revoke_contacts(offer["id"], employer_token, participant_token)
    check_erasure(employer_token)
    check_assessment()
    check_demo_guard()
    check_jury_accounts()
    check_minor()
    check_idor(employer_token, participant_token)
    check_trust(participant_token, offer["id"])
    print("SMOKE OK", contacts["display_name"], "|", card["why"][0])


def check_trust(participant_token, offer_id):
    """A candidate can complain about their own invitation, not about someone else's."""
    status, filed = call("POST", "/candidates/me/complaints",
                         {"offer_id": offer_id, "reason": "не_вакансия"}, token=participant_token)
    assert status == 201 and filed["paused"] is False, filed
    status, again = call("POST", "/candidates/me/complaints",
                         {"offer_id": offer_id, "reason": "другое"}, token=participant_token)
    assert status == 409 and again["error"]["code"] == "complaint_duplicate", again
    status, foreign = call("POST", "/candidates/me/complaints",
                           {"offer_id": str(uuid.uuid4()), "reason": "оскорбление"}, token=participant_token)
    assert status == 404, foreign
    print("TRUST OK")


def check_employer_tasks(employer_token, participant_token, candidate_id):
    """Q&A: the employer writes a task; a reference answer is checked by the system, an open one by the employer."""
    status, task = call("POST", "/tasks/", {
        "title": "Сколько раз выполнится тело цикла", "answer_type": "number", "reference_number": "12",
        "statement": "for i in range(3):\n    for j in range(4):\n        work()\nСколько раз вызовется work()?",
        "visibility": "addressed", "candidate_id": candidate_id}, token=employer_token)
    assert status == 201 and task["reference_number"] == "12", task
    status, mine = call("GET", "/tasks/for-me", token=participant_token)
    seen = next(t for t in mine if t["id"] == task["id"])
    assert status == 200 and seen["addressed"] and "reference" not in seen and "reference_number" not in seen, seen
    _, other, _ = _new_candidate("task-other")
    status, foreign = call("POST", f"/tasks/{task['id']}/answer", {"answer_text": "12"}, token=other)
    assert status == 404, foreign   # an addressed task does not exist for anyone else
    status, done = call("POST", f"/tasks/{task['id']}/answer", {"answer_text": " 12 "}, token=participant_token)
    assert status == 200 and done["submission"]["status"] == "checked" and done["submission"]["passed"], done
    assert done["reference"] == "12", done
    status, twice = call("POST", f"/tasks/{task['id']}/answer", {"answer_text": "13"}, token=participant_token)
    assert status == 409 and twice["error"]["code"] == "task_answered", twice
    status, subs = call("GET", f"/tasks/{task['id']}/submissions", token=employer_token)
    assert status == 200 and len(subs["submissions"]) == 1 and "display_name" not in subs["submissions"][0], subs
    status, review = call("POST", f"/tasks/submissions/{subs['submissions'][0]['id']}/review",
                          {"passed": False}, token=employer_token)
    assert status == 409, review   # the system already checked it
    # An open task: the employer reviews the answer.
    status, open_task = call("POST", "/tasks/", {
        "title": "Как ускорить отчёт", "answer_type": "open", "visibility": "addressed",
        "statement": "Отчёт строится 40 минут. Опишите, с чего начнёте и что измерите.",
        "candidate_id": candidate_id}, token=employer_token)
    assert status == 201, open_task
    status, sent = call("POST", f"/tasks/{open_task['id']}/answer",
                        {"answer_text": "Сначала профилирую самый долгий запрос, потом индекс и кэш."},
                        token=participant_token)
    assert status == 200 and sent["submission"]["status"] == "review" and "reference" not in sent, sent
    status, subs = call("GET", f"/tasks/{open_task['id']}/submissions", token=employer_token)
    status, reviewed = call("POST", f"/tasks/submissions/{subs['submissions'][0]['id']}/review",
                            {"passed": True, "comment": "Верный порядок"}, token=employer_token)
    assert status == 200 and reviewed["status"] == "reviewed" and reviewed["passed"], reviewed
    status, bell = call("GET", "/notifications", token=participant_token)
    assert {"task_new", "task_reviewed"} <= {n["kind"] for n in bell["items"]}, bell
    status, alien = call("GET", f"/tasks/{open_task['id']}/submissions", token=_employer_login("hr@quantumlab.demo"))
    assert status == 404, alien
    status, found = call("GET", "/search/candidates?q=Python%20backend&skills=Go,FastAPI&limit=10",
                         token=employer_token)
    card = next(item for item in found["items"] if item["candidate_id"] == candidate_id)
    assert any(line.startswith("Задание работодателя «Как ускорить отчёт»: зачтено") for line in card["why"]), card
    print("TASKS OK", task["title"], "|", open_task["title"])


def unclaimed_ids():
    """The mock registry's unclaimed ids (FSP2000–FSP2099) in a random order."""
    numbers = list(range(2000, 2100))
    random.SystemRandom().shuffle(numbers)
    return [f"FSP{n}" for n in numbers]


def _fsp_signin(fsp_id):
    status, started = call("POST", "/auth/fsp/authorize")
    assert status == 200, started
    cookie = _SIGNIN_COOKIE
    assert cookie.startswith("fsp_signin="), cookie
    query = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(started["authorize_url"]).query).items()}
    assert query["redirect_uri"] == "/auth/fsp-callback", query
    status, login = call("POST", "/fsp-id-demo/login", {"fsp_id": fsp_id, "password": "test", **{
        k: query[k] for k in ("client_id", "redirect_uri", "state", "code_challenge", "code_challenge_method")}})
    assert status == 200, login
    back = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(login["redirect_to"]).query).items()}
    status, out = call("POST", "/auth/fsp/callback", {"code": back["code"], "state": back["state"]}, cookie=cookie)
    assert status == 200, out
    status, replay = call("POST", "/auth/fsp/callback", {"code": back["code"], "state": back["state"]}, cookie=cookie)
    assert status == 400 and replay["error"]["code"] == "fsp_invalid", replay
    return out


def check_fsp_signin(linked_id):
    """Q&A: FSP ID is the single entry point. A linked account signs in; a new person consents first."""
    out = _fsp_signin("FSP001")
    assert out["status"] == "signed_in", out
    status, me = call("GET", "/candidates/me", token=out["access_token"])
    assert status == 200 and me["id"] == linked_id, me
    # Not the time-based id: in the same second it was the one linked above, so sign-in landed in that
    # e-mail account and the check below failed (flaky CI). Prefer an id nobody has used yet.
    fallback = None
    for fresh in unclaimed_ids():
        out = _fsp_signin(fresh)
        if out["status"] == "needs_consent":
            break
        status, me = call("GET", "/candidates/me", token=out["access_token"])
        if status == 200 and me["email"] is None and fallback is None:
            fallback = (fresh, out)   # an FSP-only account from an earlier run: still a valid sign-in
    else:
        assert fallback is not None, "no unclaimed mock FSP id is usable"
        fresh, out = fallback
    if out["status"] == "needs_consent":   # the first run on this database
        status, refused = call("POST", "/auth/fsp/signup", {"ticket": out["ticket"], "consents": ["terms"]})
        assert status == 422 and refused["error"]["code"] == "consent_required", refused
        status, tokens = call("POST", "/auth/fsp/signup",
                              {"ticket": out["ticket"], "consents": REQUIRED_CANDIDATE_CONSENTS})
        assert status == 200, tokens
        status, again = call("POST", "/auth/fsp/signup",
                             {"ticket": out["ticket"], "consents": REQUIRED_CANDIDATE_CONSENTS})
        assert status == 400 and again["error"]["code"] == "fsp_ticket_invalid", again
        out = tokens
    status, me = call("GET", "/candidates/me", token=out["access_token"])
    assert status == 200 and me["fsp_id"] == fresh and me["email"] is None, me
    print("FSP ID SIGN-IN OK", fresh)


def _fsp_without_survey():
    """FSP2050 is the first choice. A later free id is used when that account already finished the survey."""
    for number in range(2050, 2100):
        out = _fsp_signin(f"FSP{number}")
        if out["status"] == "needs_consent":
            status, tokens = call("POST", "/auth/fsp/signup",
                                  {"ticket": out["ticket"], "consents": REQUIRED_CANDIDATE_CONSENTS})
            assert status == 200, tokens
            return tokens["access_token"]
        status, me = call("GET", "/candidates/me", token=out["access_token"])
        assert status == 200, me
        if not me.get("survey_done"):
            return out["access_token"]
    raise AssertionError("нет свободного номера ФСП без опроса")


def check_survey_gate(employer_token):
    """A new FSP ID login has protocols and still stays out of search until the survey."""
    token = _fsp_without_survey()
    status, me = call("GET", "/candidates/me", token=token)
    assert status == 200 and me["survey_done"] is False and me["primary_role"] == "не выбрана", me
    hidden = "/search/candidates?role=" + urllib.parse.quote("не выбрана") + "&grade=junior&limit=50"
    status, before = call("GET", hidden, token=employer_token)
    assert status == 200 and before["total"] == 0, before
    assert me["id"] not in [item["candidate_id"] for item in before["items"]]
    status, saved = call("PUT", "/candidates/me/survey",
                         {"specialization": "security", "declared_grade": "junior"}, token=token)
    assert status == 200, saved
    status, me = call("GET", "/candidates/me", token=token)
    assert me["grade_source"] == "declared" and me["primary_role"] == "security", me
    status, after = call("GET", "/search/candidates?role=security&grade=junior&limit=50", token=employer_token)
    assert status == 200, after
    card = next((item for item in after["items"] if item["candidate_id"] == me["id"]), None)
    assert card is not None and card["grade_source"] == "declared", after["total"]
    print("SURVEY GATE OK", me["fsp_id"])


def check_messages(offer_id, employer_token, participant_token):
    """After acceptance both sides write on the platform; the other side has an unread badge."""
    status, posted = call("POST", f"/offers/{offer_id}/messages", {"body": "Удобно созвониться в четверг?"},
                          token=employer_token)
    assert status == 201 and posted["mine"], posted
    status, seen = call("GET", "/candidates/me/offers", token=participant_token)
    assert next(o for o in seen if o["id"] == offer_id)["unread_messages"] == 1, seen
    status, thread = call("GET", f"/offers/{offer_id}/messages", token=participant_token)
    assert status == 200 and thread["can_post"] and thread["messages"][-1]["body"].startswith("Удобно"), thread
    status, reply = call("POST", f"/offers/{offer_id}/messages", {"body": "Да, после 15:00"}, token=participant_token)
    assert status == 201, reply
    status, alien = call("GET", f"/offers/{offer_id}/messages", token=_employer_login("hr@quantumlab.demo"))
    assert status == 404, alien


def check_revoke_contacts(offer_id, employer_token, participant_token):
    """Q&A: the candidate closes the contacts for one company; the global consent stays as it was."""
    status, closed = call("POST", f"/candidates/me/offers/{offer_id}/revoke-contacts", token=participant_token)
    assert status == 200 and closed["contacts_revoked_at"], closed
    status, denied = call("GET", f"/offers/{offer_id}/contacts", token=employer_token)
    assert status == 403 and denied["error"]["code"] == "contacts_revoked", denied
    status, listed = call("GET", "/offers/", token=employer_token)
    row = next(o for o in listed if o["id"] == offer_id)
    assert row["contacts_available"] is False and row["contacts_revoked_at"], row
    status, bell = call("GET", "/notifications", token=employer_token)
    assert any(n["kind"] == "offer_contacts_revoked" for n in bell["items"]), bell
    status, thread = call("POST", f"/offers/{offer_id}/messages", {"body": "Ещё вопрос"}, token=employer_token)
    assert status == 403, thread
    status, consents = call("GET", "/me/consents", token=participant_token)
    assert status == 200, consents
    print("REVOKE OK", offer_id)


def check_needs(token):
    """Employer need: version, explainable matches, recommended categories, shortlist, has_fsp filter."""
    body = {"title": "Python-бэкенд", "params": {"role": "backend", "grade": "middle",
                                                "skills": ["python", "PostgreSQL"], "nice_to_have": ["Docker"]}}
    status, need = call("POST", "/needs", body, token=token)
    assert status == 201 and need["version"] == 1 and need["params"]["skills"] == ["PostgreSQL", "Python"], need
    status, found = call("GET", f"/needs/{need['id']}/matches?limit=5", token=token)
    assert status == 200 and found["items"] and found["recommended_categories"], found
    top = found["items"][0]
    assert top["match"]["score"] >= found["items"][-1]["match"]["score"] and top["match"]["plus"], top
    assert {f["key"] for f in top["match"]["factors"]} >= {"skills", "grade", "role", "test", "fsp"}, top
    status, picked = call("PUT", f"/needs/{need['id']}/shortlist/{top['candidate_id']}", {"status": "shortlisted"},
                          token=token)
    assert status == 200 and picked["version"] == 1, picked
    body["params"]["grade"] = "senior"
    status, edited = call("PUT", f"/needs/{need['id']}", body, token=token)
    assert status == 200 and edited["version"] == 2, edited
    status, short = call("GET", f"/needs/{need['id']}/shortlist", token=token)
    assert short["items"][0]["picked_on_version"] == 1 and short["funnel"]["shortlisted"] == 1, short
    status, no_fsp = call("GET", "/search/candidates?skills=Python,Django&has_fsp=false", token=token)
    assert status == 200 and no_fsp["items"], no_fsp
    assert any("Нет истории ФСП" in line for line in no_fsp["items"][0]["match"]["info"]), no_fsp["items"][0]
    other = _employer_login("hr@quantumlab.demo")
    status, stolen = call("GET", f"/needs/{need['id']}", token=other)
    assert status == 404, stolen
    status, stolen_matches = call("GET", f"/needs/{need['id']}/matches", token=other)
    assert status == 404, stolen_matches


def _employer_login(email):
    status, login = call("POST", "/auth/employer/token", form={"username": email, "password": "demo12345"})
    assert status == 200, login
    return login["access_token"]


def _login(email):
    status, login = call("POST", "/auth/participant/token", form={"username": email, "password": "demo12345"})
    assert status == 200, login
    return login["access_token"]


def _run_test(token, target, choose, **extra):
    status, state = call("POST", "/assessment/start", {"target_grade": target, **extra}, token=token)
    assert status == 201 and state["item"], state
    first = state["item"]
    assert "correct_index" not in json.dumps(state) and "explanation" not in first, "answer leaked to the client"
    status, bad = call("POST", f"/assessment/{state['session_id']}/answer",
                       {"item_token": "0" * 32, "answer_index": 0}, token=token)
    assert status == 409 and bad["error"]["code"] == "item_token_invalid", bad
    seen = 0
    while state["item"]:
        item = state["item"]
        if item["answer_mode"] == "number":
            assert item["options"] == [], "a typed item must not show options"
        else:
            assert len(item["options"]) == 4
        status, state = call("POST", f"/assessment/{state['session_id']}/answer",
                             {"item_token": item["token"], **choose(state["session_id"], item)}, token=token)
        assert status == 200, state
        seen += 1
        assert seen <= 20, "session longer than the maximum"
    assert state["status"] == "completed" and state["result"], state
    return state


def _wrong_answer(session_id, item):
    """Plays a weak candidate: always the first option, or a number no item has as its answer."""
    return {"answer_text": "-987654"} if item["answer_mode"] == "number" else {"answer_index": 0}


def _right_answer(session_id, item):
    """Plays a strong candidate: reads the stored right answer straight from the database."""
    import asyncio
    import json as _json

    import asyncpg

    async def fetch():
        url = os.environ.get("DATABASE_URL", "postgresql://fsp:fsp@localhost:5432/fsp_talent")
        con = await asyncpg.connect(url.replace("+asyncpg", ""))
        try:
            return await con.fetchrow(
                "SELECT correct_index, options, typed FROM test_session_items WHERE session_id = $1 AND seq = $2",
                __import__("uuid").UUID(session_id), item["seq"])
        finally:
            await con.close()
    row = asyncio.run(fetch())
    if row["typed"]:
        options = row["options"] if isinstance(row["options"], list) else _json.loads(row["options"])
        return {"answer_text": options[row["correct_index"]]}
    return {"answer_index": row["correct_index"]}


def _ids(payload, key="id"):
    rows = payload.get("items", payload) if isinstance(payload, dict) else payload
    return [str(r[key]) for r in rows or [] if isinstance(r, dict) and r.get(key)]


# Public by design: a published card, a credential check, a vacancy page and applying to it.
IDOR_PUBLIC = ("/api/v1/public/", "/api/v1/vacancies/{vacancy_id}", "/api/v1/vacancies/{vacancy_id}/apply")


OTHER_EMPLOYER, OTHER_EMPLOYER_COMPANY = "hr@cloudwhale.demo", "Облачный кит"


def check_idor(owner_employer, owner_candidate):
    """Every route with an object id from app.routes: another employer and another candidate get no 2xx."""
    owned: dict[str, list[str]] = {}

    def collect(param, path, token, key="id"):
        status, body = call("GET", path, token=token)
        if status == 200:
            owned.setdefault(param, []).extend(_ids(body, key)[:2])

    collect("need_id", "/needs", owner_employer)
    collect("offer_id", "/offers/", owner_employer)
    collect("task_id", "/tasks/", owner_employer)
    collect("vacancy_id", "/vacancies/mine", owner_employer)
    collect("application_id", "/vacancies/applications", owner_employer)
    # Only invitations the "other" employer did not send: the seed gives FSP001 one from cloudwhale too
    # (DEMO_INVITES), and withdrawing your own invitation is not an IDOR.
    status, invites = call("GET", "/candidates/me/offers", token=owner_candidate)
    if status == 200:
        owned.setdefault("offer_id", []).extend(
            [o["id"] for o in invites if o["company"] != OTHER_EMPLOYER_COMPANY][:2])
    collect("session_id", "/assessment/history", owner_candidate, "session_id")
    collect("result_id", "/candidates/me/results", owner_candidate)
    collect("notification_id", "/notifications", owner_candidate)
    for task_id in owned.get("task_id", []):
        collect("submission_id", f"/tasks/{task_id}/submissions", owner_employer)
    other_employer = call("POST", "/auth/employer/token",
                          form={"username": OTHER_EMPLOYER, "password": "demo12345"})[1]["access_token"]
    other_candidate = _login("nofsp@demo.talent")
    root = BASE.rsplit("/api/v1", 1)[0]
    with urllib.request.urlopen(root + "/openapi.json") as response:
        spec = json.loads(response.read().decode())
    checked = 0
    leaks = []
    for path, methods in spec["paths"].items():
        params = re.findall(r"{([a-z_]+)}", path)
        if not params or path.startswith(IDOR_PUBLIC[0]) or path in IDOR_PUBLIC[1:]:
            continue
        target = next((p for p in params if p in owned), None)
        if target is None:
            continue
        for value in owned[target]:
            concrete = path
            for p in params:
                concrete = concrete.replace("{" + p + "}", value if p == target else
                                            ("1" if p == "version" else "00000000-0000-0000-0000-000000000001"))
            for method in methods:
                for token in (other_employer, other_candidate):
                    status, _ = call(method.upper(), concrete[len("/api/v1"):], {}, token=token)
                    checked += 1
                    if 200 <= status < 300:
                        leaks.append((method.upper(), concrete, status))
    assert not leaks, leaks
    assert checked >= 40, checked
    print("IDOR OK", checked, "requests with foreign ids, no 2xx:", ", ".join(sorted(owned)))


def check_minor():
    """Registration opens at 15; a 15–17-year-old enters search only after the guardian confirms by the link."""
    email = f"minor-{int(time.time() * 1000)}@example.com"
    body = {"email": email, "password": "smoke-pass-1", "display_name": "Юный Кандидат", "is_adult": False,
            "consents": REQUIRED_CANDIDATE_CONSENTS}
    status, young = call("POST", "/auth/participant/register", body)
    assert status == 422 and young["error"]["code"] == "too_young", young
    status, sent = call("POST", "/auth/participant/register", {**body, "age_15_17": True})
    assert status == 202, sent
    status, tokens = call("POST", "/auth/verify-email", {"email": email, "code": last_letter(email)["code"]})
    assert status == 200, tokens
    token = tokens["access_token"]
    status, me = call("GET", "/candidates/me", token=token)
    assert me["is_minor"] and not me["minor_consent_given"], me
    guardian = f"parent-{int(time.time() * 1000)}@example.com"
    status, asked = call("POST", "/candidates/me/guardian", {"guardian_email": guardian}, token=token)
    assert status == 200, asked
    if DEMO_MAIL:
        print("MINOR OK hidden until consent; guardian letter skipped: no mailbox on the stand")
        return
    letter = last_letter(guardian, "guardian")
    status, bad = call("POST", "/public/guardian-consent", {"token": letter["token"][:-4] + "0000"})
    assert status == 404, bad
    status, ok = call("POST", "/public/guardian-consent", {"token": letter["token"]})
    assert status == 200 and ok["ok"], ok
    status, me = call("GET", "/candidates/me", token=token)
    assert me["minor_consent_given"], me
    print("MINOR OK guardian consent by link")


def check_demo_guard():
    """Published demo accounts keep the printed password: a change is refused."""
    status, blueprint = call("GET", "/assessment/blueprint")
    if not (status == 200 and blueprint.get("express")):
        print("DEMO GUARD SKIPPED (DEMO_MODE off)")
        return
    token = _login("jury10@demo.talent")
    status, refused = call("POST", "/auth/password/change",
                           {"current_password": "demo12345", "new_password": "another-pass-1"}, token=token)
    assert status == 409 and refused["error"]["code"] == "demo_protected", refused
    print("DEMO GUARD OK")


def check_jury_accounts():
    """Demo stand: a jury account fills the survey and restarts the full test without pauses or limits."""
    status, blueprint = call("GET", "/assessment/blueprint")
    if not (status == 200 and blueprint.get("express")):
        print("JURY SKIPPED (DEMO_MODE off)")
        return
    token = _login("jury2@demo.talent")
    status, saved = call("PUT", "/candidates/me/survey", {"specialization": "backend", "declared_grade": "middle"},
                         token=token)
    assert status == 200, saved
    status, missing = call("PUT", "/candidates/me/survey", {"specialization": "backend"}, token=token)
    assert status == 422, missing
    for attempt in range(4):
        status, state = call("POST", "/assessment/start", {"target_grade": "middle"}, token=token)
        assert status == 201, (attempt, state)
        status, dropped = call("POST", f"/assessment/{state['session_id']}/abandon", token=token)
        assert status == 200, dropped
    print("JURY OK four full starts in a row")


def check_assessment():
    """Adaptive test through the real API: one item at a time, answers hidden, retakes wait, grade per spec."""
    status, blueprint = call("GET", "/assessment/blueprint")
    assert status == 200 and "security" in blueprint["specializations"], blueprint
    token = _login("fsp002@demo.talent")
    status, before = call("GET", "/candidates/me", token=token)
    assert status == 200 and before["specialization"] == "security" and before["grade_source"] != "assessed", before
    weak = _run_test(token, "junior", _wrong_answer)
    result = weak["result"]
    # The seed never tests the demo logins (seed._reserved), so a failed run leaves no grade at all.
    assert not result["passed"] and result["confirmed_grade"] is None and result["earned_grade"] is None, result
    status, again = call("POST", "/assessment/start", {"target_grade": "junior"}, token=token)
    assert status == 429 and again["error"]["code"] == "retake_cooldown", again
    # Stepping down after a failure does not wait for the retake interval.
    status, lower = call("POST", "/assessment/start", {"target_grade": "intern"}, token=token)
    assert status == 201 and lower["target_grade"] == "intern", lower
    status, dropped = call("POST", f"/assessment/{lower['session_id']}/abandon", token=token)
    assert status == 200 and dropped["status"] == "abandoned", dropped
    status, after = call("GET", "/candidates/me", token=token)
    assert after["grade"] == before["grade"] and after["assessed_grade"] is None, after

    token = _login("fsp001@demo.talent")
    strong = _run_test(token, "middle", _right_answer)
    result = strong["result"]
    # A test at middle confirms middle only. The next grade is suggested when P(θ ≥ its cut) reaches the rule.
    from app.services.cat import RECOMMEND_NEXT_P
    assert result["passed"] and result["confirmed_grade"] == "middle" and not result["upgraded"], result
    expect = "senior" if (result["p_upgrade"] or 0) >= RECOMMEND_NEXT_P else None
    assert result["recommended_grade"] == expect, result
    assert result["p_pass"] >= 0.75 and result["confirmed_skills"], result
    status, me = call("GET", "/candidates/me", token=token)
    assert me["grade_source"] == "assessed" and me["assessed_grade"] == result["confirmed_grade"], me
    assert any(s["trust_level"] == "test_confirmed" for s in me["skills"]), me["skills"]
    status, review = call("GET", f"/assessment/{strong['session_id']}/review", token=token)
    assert status == 200 and all(i["correct"] for i in review["items"]), review
    # A test built from a vacancy never changes the grade, even when every answer is right.
    # The task of the week comes from an open vacancy of the candidate's own specialization.
    status, weekly = call("GET", "/assessment/practice/weekly", token=token)
    assert status == 200 and weekly and weekly["vacancy_id"], weekly
    by_vacancy = _run_test(token, "senior", _right_answer, vacancy_id=weekly["vacancy_id"])
    vac = by_vacancy["result"]
    assert vac["vacancy_test"] and vac["outcome"] == "vacancy_test" and vac["confirmed_grade"] != "senior", vac
    assert vac["recommended_grade"] in ("senior", "lead") and vac["grade_locked_until"] is None, vac
    status, me = call("GET", "/candidates/me", token=token)
    assert me["assessed_grade"] == "middle", me
    status, health = call("GET", "/public/assessment/items")
    assert status == 200 and health and all("z" in row for row in health), health
    print("ASSESSMENT OK", result["confirmed_grade"], f"p_pass={result['p_pass']}", f"items={result['items_count']}")


if __name__ == "__main__":
    main()
