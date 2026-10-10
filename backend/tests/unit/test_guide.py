from app.services.guide import guide


def test_a_candidate_is_sent_to_the_grade_test():
    answer = guide("куда нажать, чтобы подтвердить грейд", "participant")
    assert answer["links"] == [{"label": "Тест на грейд", "to": "/candidate/assessment"}]
    assert all(link["to"].startswith("/candidate") for link in answer["links"])


def test_an_employer_does_not_receive_a_candidate_page():
    answer = guide("где потребности и черновик", "employer")
    assert answer["links"][0]["to"] == "/employer/needs"
    assert all(not link["to"].startswith("/candidate") for link in answer["links"])


def test_a_public_question_stays_on_public_pages():
    answer = guide("где проверить подпись удостоверения", "public")
    assert answer["links"] == [{"label": "Проверка удостоверения", "to": "/badge"}]
    assert all(link["to"] in {"/method", "/badge", "/jury"} for link in answer["links"])


def test_an_unknown_question_stays_inside_the_role_menu():
    answer = guide("покажите зарплату директора", "participant")
    assert answer["links"]
    assert all(link["to"].startswith("/candidate") for link in answer["links"])
    assert "директор" not in answer["answer"]
