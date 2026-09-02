import io

from tests.conftest import csrf_token


def _create_engagement(client):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": "Targets Co", "client_name": "Targets Co", "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_target(
    client, engagement_id, node_type="hostname", name="victim01.corp.local", role="target", status=None
):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/targets",
        data={
            "node_type": node_type,
            "name": name,
            "role": role,
            "status": status or "",
            "provider": "",
            "region": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        return InfrastructureNode.query.filter_by(engagement_id=engagement_id, name=name).first().id


def test_create_target_appears_in_list(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_target(admin_client, engagement_id, name="victim01.corp.local")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets")
    assert resp.status_code == 200
    assert b"victim01.corp.local" in resp.data


def test_victim_role_also_appears_in_targets_list(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_target(admin_client, engagement_id, name="finance-pc.corp.local", role="victim")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets")
    assert resp.status_code == 200
    assert b"finance-pc.corp.local" in resp.data


def test_create_target_rejects_invalid_type(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets",
        data={"node_type": "not-a-real-type", "name": "bad-node", "role": "target", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.filter_by(engagement_id=engagement_id).count() == 0


def test_create_target_accepts_data_platform_types(admin_client):
    engagement_id = _create_engagement(admin_client)

    wiki_id = _create_target(admin_client, engagement_id, node_type="wiki", name="wiki.corp.local")
    share_id = _create_target(admin_client, engagement_id, node_type="file_share", name="\\\\fileserver\\shares")

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.get(wiki_id).node_type == "wiki"
        assert InfrastructureNode.query.get(share_id).node_type == "file_share"


def test_new_target_form_lists_data_platform_types(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/new")
    assert resp.status_code == 200
    assert b"Wiki / Documentation" in resp.data
    assert b"File Share (SMB/NFS)" in resp.data
    assert b"Cloud Storage (S3/Blob/GCS)" in resp.data
    assert b"Source Control (Git)" in resp.data
    assert b"Ticketing / ITSM" in resp.data
    assert b"Collaboration (Email/Chat)" in resp.data
    assert b"Backup System" in resp.data
    assert b"Database" in resp.data


def test_infrastructure_pane_rejects_target_specific_node_type(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes",
        data={"node_type": "wiki", "name": "wiki.evilcorp.test", "role": "redirector", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.filter_by(engagement_id=engagement_id).count() == 0


def test_create_target_rejects_attacker_role(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets",
        data={
            "node_type": "hostname",
            "name": "redirector01.evilcorp.test",
            "role": "redirector",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 400

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.filter_by(engagement_id=engagement_id).count() == 0


def test_edit_and_delete_target(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets/{node_id}/edit",
        data={
            "node_type": "hostname",
            "name": "renamed-victim.corp.local",
            "role": "victim",
            "provider": "",
            "region": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    resp = admin_client.get(f"/engagements/{engagement_id}/targets")
    assert b"renamed-victim.corp.local" in resp.data

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets/{node_id}/delete",
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.get(node_id) is None


def test_add_and_remove_service_on_target(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/services",
        data={"name": "SMB", "port": "445", "csrf_token": csrf},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].rstrip("/").endswith(f"/targets/{node_id}/edit")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets")
    assert b"SMB:445" in resp.data


def test_target_accepts_isolated_and_dead_status(admin_client):
    engagement_id = _create_engagement(admin_client)

    isolated_id = _create_target(admin_client, engagement_id, name="victim01.corp.local", role="target", status="isolated")
    dead_id = _create_target(admin_client, engagement_id, name="victim02.corp.local", role="victim", status="dead")

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.get(isolated_id).status == "isolated"
        assert InfrastructureNode.query.get(dead_id).status == "dead"


def test_target_rejects_burned_status(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets",
        data={
            "node_type": "hostname",
            "name": "victim01.corp.local",
            "role": "target",
            "status": "burned",
            "provider": "",
            "region": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 400

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.filter_by(engagement_id=engagement_id).count() == 0


def test_edit_target_can_change_status(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="victim01.corp.local", role="target", status="healthy")

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets/{node_id}/edit",
        data={
            "node_type": "hostname",
            "name": "victim01.corp.local",
            "role": "target",
            "status": "dead",
            "provider": "",
            "region": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.get(node_id).status == "dead"


def test_status_badge_appears_in_targets_list(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_target(admin_client, engagement_id, name="victim01.corp.local", role="target", status="isolated")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets")
    assert resp.status_code == 200
    assert b"Isolated" in resp.data


def test_new_target_form_only_offers_target_statuses(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/new")
    assert resp.status_code == 200
    assert b"Isolated" in resp.data
    assert b"Dead" in resp.data
    assert b"Burned" not in resp.data


def test_new_target_form_defaults_role_to_target(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/new")
    assert resp.status_code == 200
    assert b'<option value="target" selected' in resp.data


def test_new_target_form_role_query_param_preselects_victim(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/new?role=victim")
    assert resp.status_code == 200
    assert b'<option value="victim" selected' in resp.data


def test_new_target_form_invalid_role_query_param_falls_back_to_target(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/new?role=not-a-real-role")
    assert resp.status_code == 200
    assert b'<option value="target" selected' in resp.data


def test_edit_target_form_404s_for_attacker_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes",
        data={
            "node_type": "hostname",
            "name": "redirector01.evilcorp.test",
            "role": "redirector",
            "csrf_token": csrf,
        },
    )
    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        node_id = InfrastructureNode.query.filter_by(engagement_id=engagement_id).first().id

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}/edit")
    assert resp.status_code == 404


def _create_infra_node(client, engagement_id, name="redirector01.evilcorp.test", role="redirector"):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes",
        data={"node_type": "hostname", "name": name, "role": role, "csrf_token": csrf},
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        return InfrastructureNode.query.filter_by(engagement_id=engagement_id, name=name).first().id


def test_create_and_delete_target_edge(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_target(admin_client, engagement_id, name="dc01.corp.local", role="target")
    node_b = _create_target(admin_client, engagement_id, name="finance-pc.corp.local", role="victim")

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets/edges",
        data={
            "source_node_id": str(node_a),
            "target_node_id": str(node_b),
            "label": "SMB lateral move",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    resp = admin_client.get(f"/engagements/{engagement_id}/targets")
    assert b"SMB lateral move" in resp.data

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert b"SMB lateral move" not in resp.data

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        edge_id = InfrastructureEdge.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets/edges/{edge_id}/delete",
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        assert InfrastructureEdge.query.get(edge_id) is None


def test_target_edge_rejects_attacker_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_target(admin_client, engagement_id, name="dc01.corp.local")
    node_b = _create_infra_node(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets/edges",
        data={
            "source_node_id": str(node_a),
            "target_node_id": str(node_b),
            "label": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 400

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        assert InfrastructureEdge.query.filter_by(engagement_id=engagement_id).count() == 0


def test_edit_target_edge_changes_source_target_and_label(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_target(admin_client, engagement_id, name="dc01.corp.local")
    node_b = _create_target(admin_client, engagement_id, name="finance-pc.corp.local", role="victim")
    node_c = _create_target(admin_client, engagement_id, name="fileserver.corp.local", role="target")

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/targets/edges",
        data={
            "source_node_id": str(node_a),
            "target_node_id": str(node_b),
            "label": "SMB",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        edge_id = InfrastructureEdge.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/targets/edges/{edge_id}/edit",
        data={
            "source_node_id": str(node_b),
            "target_node_id": str(node_c),
            "label": "RDP",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        edge = InfrastructureEdge.query.get(edge_id)
        assert edge.source_node_id == node_b
        assert edge.target_node_id == node_c
        assert edge.label == "RDP"


def test_edit_target_edge_form_redirects_for_attacker_edge(admin_client):
    engagement_id = _create_engagement(admin_client)
    attacker_a = _create_infra_node(admin_client, engagement_id, name="redirect.evilcorp.com", role="redirector")
    attacker_b = _create_infra_node(admin_client, engagement_id, name="c2.evilcorp.com", role="team_server")

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges",
        data={
            "source_node_id": str(attacker_a),
            "target_node_id": str(attacker_b),
            "label": "HTTPS",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        edge_id = InfrastructureEdge.query.filter_by(engagement_id=engagement_id).first().id

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/edges/{edge_id}/edit")
    assert resp.status_code == 302
    assert resp.headers["Location"].rstrip("/").endswith(f"/infrastructure/edges/{edge_id}/edit")


# ---------------------------------------------------------------- Detail page

def _create_credential(client, engagement_id, username="svc_backup", source_host=""):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/credentials",
        data={
            "username": username,
            "password": "hunter2hunter2",
            "hash": "",
            "domain": "CORP",
            "source_host": source_host,
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.loot import Credential

        return Credential.query.filter_by(engagement_id=engagement_id, username=username).first().id


def _create_ioc(client, engagement_id, location=r"C:\Temp\evil.exe", host=""):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/iocs",
        data={"location": location, "host": host, "csrf_token": csrf},
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.ioc import IOC

        return IOC.query.filter_by(engagement_id=engagement_id, location=location).first().id


def _upload_loot(client, engagement_id, filename="screenshot.png", associated_host=""):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(b"evidence"), filename),
            "category": "screenshot",
            "associated_host": associated_host,
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_killchain_entry(client, engagement_id, title="Beacon established", infra_node_id=None):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "installation",
            "title": title,
            "description": "",
            "host": "",
            "infra_node_id": str(infra_node_id) if infra_node_id else "",
            "occurred_at": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.killchain import KillChainEntry

        return KillChainEntry.query.filter_by(engagement_id=engagement_id, title=title).first().id


def _create_finding_with_infra_node(client, engagement_id, title, infra_node_id):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/findings",
        data={
            "title": title,
            "severity": "high",
            "details": "",
            "remediation": "",
            "infra_node_ids": [str(infra_node_id)],
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302


def test_target_list_links_to_detail_page(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets")
    assert resp.status_code == 200
    assert f"/engagements/{engagement_id}/targets/{node_id}".encode() in resp.data


def test_target_detail_renders_node_info(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local", role="target")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 200
    assert b"dc01.corp.local" in resp.data
    assert b"Nothing recorded for this host yet." in resp.data


def test_target_detail_404s_for_attacker_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_infra_node(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 404


def test_target_detail_404s_for_wrong_engagement(admin_client):
    engagement_id = _create_engagement(admin_client)
    other_engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local")

    resp = admin_client.get(f"/engagements/{other_engagement_id}/targets/{node_id}")
    assert resp.status_code == 404


def test_target_detail_shows_killchain_entry_linked_by_infra_node_id(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local")
    _create_killchain_entry(admin_client, engagement_id, title="Dumped hashes via Mimikatz", infra_node_id=node_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 200
    assert b"Dumped hashes via Mimikatz" in resp.data


def test_target_detail_excludes_killchain_entry_for_other_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local")
    other_node_id = _create_target(admin_client, engagement_id, name="finance-pc.corp.local", role="victim")
    _create_killchain_entry(admin_client, engagement_id, title="Unrelated activity", infra_node_id=other_node_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 200
    assert b"Unrelated activity" not in resp.data


def test_target_detail_shows_credential_matched_by_host_name(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local")
    _create_credential(admin_client, engagement_id, username="Administrator", source_host="dc01.corp.local")
    _create_credential(admin_client, engagement_id, username="unrelated_svc", source_host="other-host.corp.local")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 200
    assert b"Administrator" in resp.data
    assert b"unrelated_svc" not in resp.data


def test_target_detail_credential_match_is_case_insensitive(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="DC01.corp.local")
    _create_credential(admin_client, engagement_id, username="Administrator", source_host="dc01.CORP.LOCAL")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 200
    assert b"Administrator" in resp.data


def test_target_detail_shows_ioc_matched_by_host(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local")
    _create_ioc(admin_client, engagement_id, location=r"C:\Windows\Temp\mimikatz.exe", host="dc01.corp.local")
    _create_ioc(admin_client, engagement_id, location=r"C:\Temp\unrelated.exe", host="other-host.corp.local")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 200
    assert rb"mimikatz.exe" in resp.data
    assert rb"unrelated.exe" not in resp.data


def test_target_detail_shows_loot_matched_by_associated_host(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local")
    _upload_loot(admin_client, engagement_id, filename="lsass_dump.dmp", associated_host="dc01.corp.local")
    _upload_loot(admin_client, engagement_id, filename="unrelated.png", associated_host="other-host.corp.local")

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 200
    assert b"lsass_dump.dmp" in resp.data
    assert b"unrelated.png" not in resp.data


def test_target_detail_shows_finding_linked_via_infra_node_ids(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_id, name="dc01.corp.local")
    _create_finding_with_infra_node(admin_client, engagement_id, "Domain Admin compromise", node_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}")
    assert resp.status_code == 200
    assert b"Domain Admin compromise" in resp.data


def test_target_detail_shows_network_pathing_edge(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_target(admin_client, engagement_id, name="dc01.corp.local", role="target")
    node_b = _create_target(admin_client, engagement_id, name="finance-pc.corp.local", role="victim")
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/targets/edges",
        data={
            "source_node_id": str(node_a),
            "target_node_id": str(node_b),
            "label": "SMB lateral move",
            "notes": "",
            "csrf_token": csrf,
        },
    )

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_a}")
    assert resp.status_code == 200
    assert b"SMB lateral move" in resp.data

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_b}")
    assert resp.status_code == 200
    assert b"SMB lateral move" in resp.data


def test_target_detail_does_not_leak_across_engagements(admin_client):
    engagement_a = _create_engagement(admin_client)
    engagement_b = _create_engagement(admin_client)
    node_id = _create_target(admin_client, engagement_a, name="dc01.corp.local")
    _create_credential(admin_client, engagement_b, username="other_engagement_admin", source_host="dc01.corp.local")

    resp = admin_client.get(f"/engagements/{engagement_a}/targets/{node_id}")
    assert resp.status_code == 200
    assert b"other_engagement_admin" not in resp.data
