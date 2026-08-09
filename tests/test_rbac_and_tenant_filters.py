from rag.hybrid_retriever import metadata_allowed
from services.platform_service import can_access_agent_run


def test_candidate_can_only_access_own_run():
    own = {"user_id": 7, "organization_id": None}
    assert can_access_agent_run({"id": 7, "role": "candidate"}, own)
    assert not can_access_agent_run({"id": 8, "role": "candidate"}, own)


def test_interviewer_is_limited_to_organization_and_admin_is_global():
    run = {"user_id": 7, "organization_id": 12}
    assert can_access_agent_run({"id": 2, "role": "interviewer", "organization_id": 12}, run)
    assert not can_access_agent_run({"id": 3, "role": "interviewer", "organization_id": 13}, run)
    assert not can_access_agent_run({"id": 3, "role": "interviewer", "organization_id": None}, run)
    assert can_access_agent_run({"id": 1, "role": "admin"}, run)


def test_document_visibility_rules():
    actor = {"user_id": "candidate@example.com", "organization_id": 9}
    assert metadata_allowed({"visibility": "public"}, actor)
    assert metadata_allowed(
        {"visibility": "private", "user_id": "candidate@example.com", "organization_id": 9}, actor
    )
    assert not metadata_allowed(
        {"visibility": "private", "user_id": "other@example.com", "organization_id": 9}, actor
    )
    assert metadata_allowed({"visibility": "organization", "organization_id": 9}, actor)
    assert not metadata_allowed({"visibility": "organization", "organization_id": 10}, actor)
