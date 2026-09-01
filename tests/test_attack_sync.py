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
            "name": "Deprecated Technique",
            "x_mitre_deprecated": True,
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T9999", "url": "https://attack.mitre.org/techniques/T9999"}
            ],
        },
    ]
}


def test_fetch_and_sync_upserts_tactics_and_techniques(app, monkeypatch):
    from app.services import attack_sync

    monkeypatch.setattr(attack_sync, "fetch_bundle", lambda: FAKE_BUNDLE)

    with app.app_context():
        summary = attack_sync.fetch_and_sync()
        assert summary == {"tactics": 1, "techniques": 2}

        from app.models.attack import AttackTactic, AttackTechnique

        assert AttackTactic.query.filter_by(attack_id="TA0001").count() == 1
        assert AttackTechnique.query.filter_by(attack_id="T9999").count() == 0

        parent = AttackTechnique.query.filter_by(attack_id="T1566").first()
        child = AttackTechnique.query.filter_by(attack_id="T1566.001").first()
        assert parent is not None
        assert child is not None
        assert child.is_subtechnique is True
        assert child.parent_technique_id == parent.id
        assert [t.attack_id for t in parent.tactics] == ["TA0001"]


def test_fetch_and_sync_is_idempotent(app, monkeypatch):
    from app.services import attack_sync

    monkeypatch.setattr(attack_sync, "fetch_bundle", lambda: FAKE_BUNDLE)

    with app.app_context():
        attack_sync.fetch_and_sync()
        summary = attack_sync.fetch_and_sync()
        assert summary == {"tactics": 1, "techniques": 2}

        from app.models.attack import AttackTechnique

        assert AttackTechnique.query.filter_by(attack_id="T1566").count() == 1


def test_refresh_route_is_admin_only(admin_client, second_client, monkeypatch):
    from app.services import attack_sync

    monkeypatch.setattr(attack_sync, "fetch_bundle", lambda: FAKE_BUNDLE)

    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op1", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "op1", "password": "operatorpass123"})
    op_csrf = csrf_token(second_client)
    resp = second_client.post("/attack/refresh", data={"csrf_token": op_csrf})
    assert resp.status_code == 403

    admin_resp = admin_client.post("/attack/refresh", data={"csrf_token": csrf})
    assert admin_resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.attack import AttackTactic

        assert AttackTactic.query.count() == 1
