"""Decay is recomputed nightly; registry corrections are applied."""
import inspect

from app.core import rescore_stale
from app.services.fsp import sync
from app.services.profile import reconcile_results
from app.workers.celery_app import beat_schedule


def test_fsp_scores_are_recomputed_every_night():
    entry = beat_schedule()["rescore-fsp-nightly"]
    assert entry["task"] == "app.workers.tasks.rescore_fsp_nightly"
    source = inspect.getsource(rescore_stale.stale_participant_ids)
    assert "computed_at < cutoff" in source and "!= VERSION" in source


def test_registry_sync_reconciles_instead_of_appending():
    source = inspect.getsource(sync.pull_registry_changes)
    assert "reconcile_results" in source and "append_new_results" not in source


def test_reconcile_touches_only_registry_rows_and_survives_an_outage():
    source = inspect.getsource(reconcile_results)
    assert 'Result.trust_level == "verified_fsp"' in source
    assert "if incoming:" in source          # an empty answer removes nothing
    assert "revoked_at" in source            # the credential of a removed line is revoked
    assert "MAX_REMOVED_SHARE * len(rows)" in source   # a partial answer is not a mass annulment
