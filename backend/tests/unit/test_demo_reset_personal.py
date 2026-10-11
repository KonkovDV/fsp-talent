"""PR295-01: «Начать заново» left the previous expert's name, phone, Telegram and GitHub on the jury login."""
from app.models import Participant
from app.services.demo_reset import clear_personal, juror_name


def test_start_over_clears_what_the_previous_expert_typed():
    person = Participant(email="jury3@demo.talent", display_name="Иван Петров", phone="+79990001122",
                         telegram="@ivan_p", github="ivanp", region="Казань", soft_skills=["Лидерство"],
                         work_formats=["remote"], excluded_industries=["gambling"], public_profile=True,
                         show_city=False, job_search="not_looking", certificate_grade="middle")
    clear_personal(person)
    assert person.display_name == "Член жюри 3"
    for field in ("phone", "telegram", "github", "region", "certificate_grade"):
        assert getattr(person, field) is None, field
    assert person.soft_skills == [] and person.work_formats == [] and person.excluded_industries == []
    assert person.public_profile is False and person.show_city is True and person.job_search == "open"


def test_juror_name_matches_the_seed():
    assert juror_name("jury10@demo.talent") == "Член жюри 10"
    assert juror_name("someone@demo.talent") == "Член жюри"
