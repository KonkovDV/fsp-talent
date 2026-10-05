"""One-shot API smoke test against a running server. Not part of the unit suite."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8010/api/v1")


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


def main():
    with urllib.request.urlopen(BASE.replace("/api/v1", "/health")) as response:
        print("health", json.loads(response.read().decode()))
    status, employer = call("POST", "/auth/employer/token", form={"username": "hr@yandex.demo", "password": "demo12345"})
    assert status == 200, employer
    employer_token = employer["access_token"]
    status, participant = call("POST", "/auth/participant/token", form={"username": "FSP001", "password": "test"})
    assert status == 200, participant
    participant_token = participant["access_token"]
    status, me = call("GET", "/candidates/me", token=participant_token)
    assert status == 200 and me["fsp_id"] == "FSP001" and me["grade"] == "middle", me
    status, duplicate = call("POST", "/auth/participant/register", {"fsp_id": "FSP001", "fsp_secret": "test"})
    assert status == 409, duplicate
    status, bad_salary = call("POST", "/offers/", {
        "candidate_id": me["id"], "salary_from_gross": 200, "salary_to_gross": 100,
        "role": "Backend", "work_format": "remote", "contact_method": "hr@yandex.demo",
    }, token=employer_token)
    assert status == 422, bad_salary
    status, found = call("GET", "/search/candidates?q=Python%20backend&skills=Go,FastAPI&limit=10", token=employer_token)
    assert status == 200 and found["total"] > 0, found
    card = next(item for item in found["items"] if item["candidate_id"] == me["id"])
    assert "display_name" not in card and "Go" in card["matched_skills"] and card["why"], card
    status, offer = call("POST", "/offers/", {
        "candidate_id": me["id"], "salary_from_gross": 180000, "salary_to_gross": 260000,
        "role": "Backend-разработчик", "work_format": "remote", "message": "Ждём в команде",
        "contact_method": "Telegram @yandex_hr",
    }, token=employer_token)
    assert status == 201, offer
    status, seen = call("GET", "/candidates/me/offers", token=participant_token)
    mine = next(o for o in seen if o["id"] == offer["id"])
    assert status == 200 and mine["contact_method"] == "Telegram @yandex_hr", mine
    status, listed = call("GET", "/offers/", token=employer_token)
    assert next(o for o in listed if o["id"] == offer["id"])["candidate_viewed_at"], "viewed status not recorded"
    status, no_salary = call("POST", "/vacancies/", {"title": "Без вилки", "skills": ["Python"]}, token=employer_token)
    assert status == 422, no_salary
    status, denied = call("GET", f"/offers/{offer['id']}/contacts", token=employer_token)
    assert status == 403, denied
    status, accepted = call("POST", f"/candidates/me/offers/{offer['id']}/respond",
                            {"action": "accept"}, token=participant_token)
    assert status == 200 and accepted["status"] == "accepted", accepted
    status, again = call("POST", f"/candidates/me/offers/{offer['id']}/respond",
                         {"action": "reject"}, token=participant_token)
    assert status == 409, again
    status, contacts = call("GET", f"/offers/{offer['id']}/contacts", token=employer_token)
    assert status == 200 and contacts["display_name"] and contacts["email"], contacts
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
    assert status == 200 and query["role"] == "backend" and query["grade"] == "senior" and "Python" in query["skills"], query
    check_assessment()
    print("SMOKE OK", contacts["display_name"], "|", card["why"][0])


def check_assessment():
    """Test mechanic through the real API: answers stay hidden, skipping earns nothing, retakes wait."""
    status, login = call("POST", "/auth/participant/token", form={"username": "FSP002", "password": "test"})
    assert status == 200, login
    token = login["access_token"]
    status, before = call("GET", "/candidates/me", token=token)
    assert status == 200 and before["grade_source"] != "assessed", before
    status, session = call("POST", "/assessment/start",
                           {"target_grade": "junior", "discipline": "security"}, token=token)
    assert status == 201 and len(session["questions"]) >= 5, session
    assert all("correct_option" not in q for q in session["questions"]), "right answers leaked to the client"
    # Old bug: an empty submission scored theta=0 -> "middle". Every served question now counts.
    status, result = call("POST", f"/assessment/{session['session_id']}/submit",
                          {"answers": [{"question_id": "not-served", "answer": "a"}]}, token=token)
    assert status == 200 and result["outcome"] == "not_passed" and result["confirmed_grade"] is None, result
    status, again = call("POST", "/assessment/start", {"target_grade": "junior"}, token=token)
    assert status == 429, again
    status, after = call("GET", "/candidates/me", token=token)
    assert status == 200 and after["grade"] == before["grade"] and after["assessed_grade"] is None, after


if __name__ == "__main__":
    main()
