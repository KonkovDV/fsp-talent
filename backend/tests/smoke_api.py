"""One-shot API smoke test against a running server. Not part of the unit suite."""
import glob
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8010/api/v1")
# The API must run with MAIL_MODE=file and the same MAIL_FILE_DIR: codes are read from the letters.
MAIL_DIR = os.environ.get("MAIL_FILE_DIR", "/tmp/fsp-talent-mail")
EMPLOYER = {"username": "hr@sibcode.demo", "password": "demo12345"}
CANDIDATE = {"username": "fsp001@demo.talent", "password": "demo12345"}
REQUIRED_CANDIDATE_CONSENTS = ["terms", "pd_candidate"]


def call(method, path, body=None, token=None, form=None):
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
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return error.code, payload


def last_letter(email, purpose="verify", timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for path in sorted(glob.glob(os.path.join(MAIL_DIR, "*.json")), reverse=True):
            with open(path, encoding="utf-8") as fh:
                letter = json.load(fh)
            if letter["to"] == email and letter.get("purpose") == purpose:
                return letter
        time.sleep(0.2)
    raise AssertionError(f"no {purpose} letter for {email} in {MAIL_DIR}")


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
    status, again = call("POST", "/auth/verify-email", {"token": letter["token"]})
    assert status == 400 and again["error"]["code"] == "verification_invalid", again
    status, taken = call("POST", "/auth/participant/register", {**body, "consents": REQUIRED_CANDIDATE_CONSENTS})
    assert status == 409 and taken["error"]["code"] == "email_taken", taken
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
    status, taken_fsp = call("POST", "/candidates/me/fsp", {"fsp_id": "FSP001", "fsp_secret": "test"}, token=token)
    assert status == 409 and taken_fsp["error"]["code"] == "fsp_taken", taken_fsp
    status, bad_fsp = call("POST", "/candidates/me/fsp", {"fsp_id": "FSP2001", "fsp_secret": "nope"}, token=token)
    assert status == 400 and bad_fsp["error"]["code"] == "fsp_invalid", bad_fsp
    fsp_id = f"FSP{2000 + int(time.time()) % 100}"
    status, linked = call("POST", "/candidates/me/fsp", {"fsp_id": fsp_id, "fsp_secret": "test"}, token=token)
    if status == 409:   # a previous smoke run on the same database already linked this id
        assert linked["error"]["code"] == "fsp_taken", linked
    else:
        assert status == 200 and linked["fsp_id"] == fsp_id and linked["results"] >= 1, linked
        status, me = call("GET", "/candidates/me", token=token)
        assert me["has_fsp"] and me["display_name"] == "Смоук Тест", me
    status, reset = call("POST", "/auth/password/forgot", {"email": email, "role": "participant"})
    assert status == 202, reset
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
    status, gone = call("DELETE", "/candidates/me", {"confirm": "удалить"}, token=token)
    assert status == 200 and gone["deleted"], gone
    status, login = call("POST", "/auth/participant/token", form={"username": email, "password": "smoke-pass-1"})
    assert status == 401, login
    status, me = call("GET", "/candidates/me", token=token)
    assert status == 404, me
    status, closed = call("GET", f"/offers/{offer['id']}/contacts", token=employer_token)
    assert status == 403, closed


def main():
    with urllib.request.urlopen(BASE.replace("/api/v1", "/health")) as response:
        print("health", json.loads(response.read().decode()))
    status, employer = call("POST", "/auth/employer/token", form=EMPLOYER)
    assert status == 200, employer
    employer_token = employer["access_token"]
    status, participant = call("POST", "/auth/participant/token", form=CANDIDATE)
    assert status == 200, participant
    participant_token = participant["access_token"]
    status, me = call("GET", "/candidates/me", token=participant_token)
    assert status == 200 and me["fsp_id"] == "FSP001" and me["grade"] == "middle", me
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
        "contact_method": "Telegram @sibcode_hr",
    }, token=employer_token)
    assert status == 201, offer
    status, seen = call("GET", "/candidates/me/offers", token=participant_token)
    mine = next(o for o in seen if o["id"] == offer["id"])
    assert status == 200 and mine["contact_method"] == "Telegram @sibcode_hr", mine
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
    status, bell = call("GET", "/notifications", token=employer_token)
    assert status == 200 and any(n["kind"] == "offer_accepted" for n in bell["items"]), bell
    status, public = call("GET", f"/public/candidates/{me['id']}")
    assert status == 200 and "fsp_id" not in public and public["display_name"], public
    status, board = call("GET", "/public/leaderboard?discipline=algorithmic")
    assert status == 200 and board and "fsp_id" not in board[0]
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
    check_erasure(employer_token)
    check_assessment()
    print("SMOKE OK", contacts["display_name"], "|", card["why"][0])


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


def _login(email):
    status, login = call("POST", "/auth/participant/token", form={"username": email, "password": "demo12345"})
    assert status == 200, login
    return login["access_token"]


def _run_test(token, target, choose):
    status, state = call("POST", "/assessment/start", {"target_grade": target}, token=token)
    assert status == 201 and state["item"], state
    first = state["item"]
    assert "correct_index" not in json.dumps(state) and "explanation" not in first, "answer leaked to the client"
    status, bad = call("POST", f"/assessment/{state['session_id']}/answer",
                       {"item_token": "0" * 32, "answer_index": 0}, token=token)
    assert status == 409 and bad["error"]["code"] == "item_token_invalid", bad
    seen = 0
    while state["item"]:
        item = state["item"]
        assert len(item["options"]) == 4
        status, state = call("POST", f"/assessment/{state['session_id']}/answer",
                             {"item_token": item["token"], "answer_index": choose(state["session_id"], item)},
                             token=token)
        assert status == 200, state
        seen += 1
        assert seen <= 20, "session longer than the maximum"
    assert state["status"] == "completed" and state["result"], state
    return state


def _right_answer(session_id, item):
    """Plays a strong candidate: reads the stored right answer straight from the database."""
    import asyncio

    import asyncpg

    async def fetch():
        url = os.environ.get("DATABASE_URL", "postgresql://fsp:fsp@localhost:5432/fsp_talent")
        con = await asyncpg.connect(url.replace("+asyncpg", ""))
        try:
            return await con.fetchval("SELECT correct_index FROM test_session_items WHERE session_id = $1 AND seq = $2",
                                      __import__("uuid").UUID(session_id), item["seq"])
        finally:
            await con.close()
    return asyncio.run(fetch())


def check_assessment():
    """Adaptive test through the real API: one item at a time, answers hidden, retakes wait, grade per spec."""
    status, blueprint = call("GET", "/assessment/blueprint")
    assert status == 200 and "security" in blueprint["specializations"], blueprint
    token = _login("fsp002@demo.talent")
    status, before = call("GET", "/candidates/me", token=token)
    assert status == 200 and before["specialization"] == "security" and before["grade_source"] != "assessed", before
    weak = _run_test(token, "junior", lambda sid, item: 0)
    result = weak["result"]
    assert not result["passed"] and result["confirmed_grade"] is None, result
    status, again = call("POST", "/assessment/start", {"target_grade": "junior"}, token=token)
    assert status == 429 and again["error"]["code"] == "retake_cooldown", again
    status, after = call("GET", "/candidates/me", token=token)
    assert after["grade"] == before["grade"] and after["assessed_grade"] is None, after

    token = _login("fsp001@demo.talent")
    strong = _run_test(token, "middle", _right_answer)
    result = strong["result"]
    assert result["passed"] and result["confirmed_grade"] in ("middle", "senior"), result
    assert result["p_pass"] >= 0.75 and result["confirmed_skills"], result
    status, me = call("GET", "/candidates/me", token=token)
    assert me["grade_source"] == "assessed" and me["assessed_grade"] == result["confirmed_grade"], me
    assert any(s["trust_level"] == "test_confirmed" for s in me["skills"]), me["skills"]
    status, review = call("GET", f"/assessment/{strong['session_id']}/review", token=token)
    assert status == 200 and all(i["correct"] for i in review["items"]), review
    status, health = call("GET", "/public/assessment/items")
    assert status == 200 and health and all("z" in row for row in health), health
    print("ASSESSMENT OK", result["confirmed_grade"], f"p_pass={result['p_pass']}", f"items={result['items_count']}")


if __name__ == "__main__":
    main()
