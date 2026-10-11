"""AUD-02: a text file is refused; a PDF certificate leaves skills self-declared."""
import io

import pytest
from fastapi import UploadFile
from sqlalchemy import select

from app.api.errors import ApiError
from app.api.v1 import candidates as api
from app.models import Participant, Skill
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_text_file_is_refused_and_pdf_skills_stay_unconfirmed(db, monkeypatch):
    async def never(*a, **k):
        return False
    monkeypatch.setattr(api, "too_many", never)
    person = Participant(email=f"dbtest-cert-{stamp()}@example.com", display_name="Серт", password_hash=PASSWORD_HASH,
                         email_verified_at=now(), is_minor=False, is_visible=True, public_profile=False)
    db.add(person)
    await db.commit()
    me = {"sub": str(person.id)}
    try:
        txt = UploadFile(io.BytesIO("Я освоил компетенции: Python, Docker".encode()), filename="c.txt")
        with pytest.raises(ApiError) as caught:
            await api.import_certificate(txt, me, db)
        assert caught.value.status_code == 422
        fake_pdf = UploadFile(io.BytesIO(b"not a pdf"), filename="c.pdf")
        with pytest.raises(ApiError):
            await api.import_certificate(fake_pdf, me, db)
        import app.services.protocol_file as pf
        monkeypatch.setattr(pf, "text_of_pdf", lambda raw: "Сертификат КИТ. Компетенции: Python, Docker")
        pdf = UploadFile(io.BytesIO(b"%PDF-1.7 fake"), filename="c.pdf")
        result = await api.import_certificate(pdf, me, db)
        assert result["skills"]
        rows = list(await db.scalars(select(Skill).where(Skill.participant_id == person.id)))
        assert rows and all(not r.confirmed and r.trust_level == "self_reported" and r.source_quote for r in rows)
    finally:
        await wipe_people([person.id])
