from tests.conftest import csrf_token

FAKE_BUNDLE = {
    "objects": [
        {
            "type": "x-mitre-tactic",
            "name": "Initial Access",
            "x_mitre_shortname": "initial-access",
            "description": "The adversary is trying to get into your network.",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "TA0001", "url": "https://attack.mitre.org/tactics/TA0001"}
            ],
        },
        {
            "type": "attack-pattern",
            "name": "Phishing",
            "description": "Adversaries may send phishing messages.",
            "x_mitre_is_subtechnique": False,
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1566", "url": "https://attack.mitre.org/techniques/T1566"}
            ],
            "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}],
        },
        {
            "type": "attack-pattern",
            "name": "Spearphishing Attachment",
            "description": "Adversaries may send spearphishing emails with an attachment.",
            "x_mitre_is_subtechnique": True,
            "external_references": [
                {
                    "source_name": "mitre-attack",
                    "external_id": "T1566.001",
                    "url": "https://attack.mitre.org/techniques/T1566/001",
                }
            ],
            "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}],
        },
        {
            "type": "attack-pattern",
            "name": "Phishing for Information",
            "description": "Adversaries may phish for information.",
            "x_mitre_is_subtechnique": False,
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1598", "url": "https://attack.mitre.org/techniques/T1598"}
            ],
            "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}],
        },
    ]
}


def _create_engagement(client, name):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": name, "client_name": name, "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_entry(client, engagement_id, title):
    csrf = csrf_token(client)
    client.post(
        f"/engagements/{engagement_id}/killchain",
        data={"stage": "delivery", "title": title, "csrf_token": csrf},
    )
    with client.application.app_context():
        from app.models.killchain import KillChainEntry

        return KillChainEntry.query.filter_by(engagement_id=engagement_id, title=title).first().id


def test_matrix_highlights_directly_used_technique(admin_client, monkeypatch):
    from app.services import attack_sync

    monkeypatch.setattr(attack_sync, "fetch_bundle", lambda: FAKE_BUNDLE)
    with admin_client.application.app_context():
        attack_sync.fetch_and_sync()

    engagement_id = _create_engagement(admin_client, "Matrix Co")
    entry_id = _create_entry(admin_client, engagement_id, "Phish sent")

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/killchain/{entry_id}/map-technique",
        data={"attack_id": "T1566", "csrf_token": csrf},
    )

    resp = admin_client.get("/attack")
    assert resp.status_code == 200
    html = resp.data.decode()

    assert "attack-cell-used" in html
    assert "Matrix Co" in html
    assert "popover-T1566" in html

    with admin_client.application.app_context():
        from app.services.attack_service import build_matrix_tactics

        tactics = build_matrix_tactics()
        used = next(t for tac in tactics for t in tac.techniques if t.attack_id == "T1566")
        unused = next(t for tac in tactics for t in tac.techniques if t.attack_id == "T1598")

        assert used.matrix_is_used is True
        assert used.matrix_usage[0][1]["direct"] is True
        assert unused.matrix_is_used is False


def test_matrix_highlights_parent_when_subtechnique_used(admin_client, monkeypatch):
    from app.services import attack_sync

    monkeypatch.setattr(attack_sync, "fetch_bundle", lambda: FAKE_BUNDLE)
    with admin_client.application.app_context():
        attack_sync.fetch_and_sync()

    engagement_id = _create_engagement(admin_client, "Subtech Co")
    entry_id = _create_entry(admin_client, engagement_id, "Sent attachment")

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/killchain/{entry_id}/map-technique",
        data={"attack_id": "T1566.001", "csrf_token": csrf},
    )

    resp = admin_client.get("/attack")
    html = resp.data.decode()

    assert "Subtech Co" in html
    assert "T1566.001" in html

    with admin_client.application.app_context():
        from app.services.attack_service import build_matrix_tactics

        tactics = build_matrix_tactics()
        parent = next(t for tac in tactics for t in tac.techniques if t.attack_id == "T1566")
        unused = next(t for tac in tactics for t in tac.techniques if t.attack_id == "T1598")

        assert parent.matrix_is_used is True
        assert parent.matrix_usage[0][1]["direct"] is False
        assert parent.matrix_usage[0][1]["via_subs"][0].attack_id == "T1566.001"
        assert unused.matrix_is_used is False
        assert unused.matrix_usage == []


def test_unused_technique_not_highlighted(admin_client, monkeypatch):
    from app.services import attack_sync

    monkeypatch.setattr(attack_sync, "fetch_bundle", lambda: FAKE_BUNDLE)
    with admin_client.application.app_context():
        attack_sync.fetch_and_sync()

    resp = admin_client.get("/attack")
    assert resp.status_code == 200
    assert "attack-cell-used" not in resp.data.decode()
