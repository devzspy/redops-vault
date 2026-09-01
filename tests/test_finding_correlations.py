from tests.conftest import csrf_token


def _create_engagement(client, name="Correlate Co"):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": name, "client_name": name, "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_target_node(client, engagement_id, name="dc01.corp.local", role="target"):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/targets",
        data={
            "node_type": "hostname",
            "name": name,
            "role": role,
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


def _create_infra_node(client, engagement_id, name="redirect.evilcorp.com", role="redirector"):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes",
        data={
            "node_type": "hostname",
            "name": name,
            "role": role,
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


def _create_credential(client, engagement_id, username="svc_backup"):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/credentials",
        data={
            "username": username,
            "password": "hunter2hunter2",
            "hash": "",
            "domain": "CORP",
            "source_host": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.loot import Credential

        return Credential.query.filter_by(engagement_id=engagement_id, username=username).first().id


def _create_ioc(client, engagement_id, location=r"C:\Temp\evil.exe"):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/iocs",
        data={"location": location, "csrf_token": csrf},
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.ioc import IOC

        return IOC.query.filter_by(engagement_id=engagement_id, location=location).first().id


def _create_killchain_entry(client, engagement_id, title="Beacon established"):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "installation",
            "title": title,
            "description": "",
            "host": "",
            "occurred_at": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.killchain import KillChainEntry

        return KillChainEntry.query.filter_by(engagement_id=engagement_id, title=title).first().id


def _create_finding_with_links(client, engagement_id, title, **link_ids):
    csrf = csrf_token(client)
    data = {
        "title": title,
        "severity": "high",
        "details": "",
        "remediation": "",
        "csrf_token": csrf,
    }
    for field, ids in link_ids.items():
        data[field] = [str(i) for i in ids]
    resp = client.post(f"/engagements/{engagement_id}/findings", data=data)
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.finding import Finding

        return Finding.query.filter_by(engagement_id=engagement_id, title=title).first().id


def test_finding_can_link_infra_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target_node(admin_client, engagement_id)
    finding_id = _create_finding_with_links(
        admin_client, engagement_id, "Host finding", infra_node_ids=[node_id]
    )

    with admin_client.application.app_context():
        from app.models.finding import Finding
        from app.models.infrastructure import InfrastructureNode

        finding = Finding.query.get(finding_id)
        assert len(finding.infra_nodes) == 1
        assert finding.infra_nodes[0].name == "dc01.corp.local"

        node = InfrastructureNode.query.get(node_id)
        assert len(node.findings) == 1
        assert node.findings[0].title == "Host finding"

    resp = admin_client.get(f"/engagements/{engagement_id}/targets/{node_id}/edit")
    assert b"Host finding" in resp.data


def test_finding_can_link_credential(admin_client):
    engagement_id = _create_engagement(admin_client)
    cred_id = _create_credential(admin_client, engagement_id)
    finding_id = _create_finding_with_links(
        admin_client, engagement_id, "Cred finding", credential_ids=[cred_id]
    )

    with admin_client.application.app_context():
        from app.models.finding import Finding
        from app.models.loot import Credential

        finding = Finding.query.get(finding_id)
        assert len(finding.credentials) == 1
        assert finding.credentials[0].username == "svc_backup"

        cred = Credential.query.get(cred_id)
        assert len(cred.findings) == 1

    resp = admin_client.get(f"/engagements/{engagement_id}/credentials")
    assert b"Cred finding" in resp.data


def test_finding_can_link_ioc(admin_client):
    engagement_id = _create_engagement(admin_client)
    ioc_id = _create_ioc(admin_client, engagement_id)
    finding_id = _create_finding_with_links(admin_client, engagement_id, "IOC finding", ioc_ids=[ioc_id])

    with admin_client.application.app_context():
        from app.models.finding import Finding
        from app.models.ioc import IOC

        finding = Finding.query.get(finding_id)
        assert len(finding.iocs) == 1

        ioc = IOC.query.get(ioc_id)
        assert len(ioc.findings) == 1

    resp = admin_client.get(f"/engagements/{engagement_id}/iocs")
    assert b"IOC finding" in resp.data


def test_finding_can_link_killchain_entry(admin_client):
    engagement_id = _create_engagement(admin_client)
    entry_id = _create_killchain_entry(admin_client, engagement_id)
    finding_id = _create_finding_with_links(
        admin_client, engagement_id, "Killchain finding", killchain_entry_ids=[entry_id]
    )

    with admin_client.application.app_context():
        from app.models.finding import Finding
        from app.models.killchain import KillChainEntry

        finding = Finding.query.get(finding_id)
        assert len(finding.killchain_entries) == 1

        entry = KillChainEntry.query.get(entry_id)
        assert len(entry.findings) == 1

    resp = admin_client.get(f"/engagements/{engagement_id}/killchain")
    assert b"Killchain finding" in resp.data


def test_edit_finding_replaces_correlations(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_target_node(admin_client, engagement_id, name="node-a.corp.local")
    node_b = _create_target_node(admin_client, engagement_id, name="node-b.corp.local")
    finding_id = _create_finding_with_links(
        admin_client, engagement_id, "Swap finding", infra_node_ids=[node_a]
    )

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/findings/{finding_id}/edit",
        data={
            "title": "Swap finding",
            "severity": "high",
            "details": "",
            "remediation": "",
            "infra_node_ids": [str(node_b)],
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.finding import Finding

        finding = Finding.query.get(finding_id)
        names = {n.name for n in finding.infra_nodes}
        assert names == {"node-b.corp.local"}


def test_finding_form_lists_correlation_candidates(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_target_node(admin_client, engagement_id, name="dc01.corp.local")
    _create_credential(admin_client, engagement_id, username="svc_backup")
    _create_ioc(admin_client, engagement_id, location=r"C:\Temp\evil.exe")
    _create_killchain_entry(admin_client, engagement_id, title="Beacon established")

    resp = admin_client.get(f"/engagements/{engagement_id}/findings/new")
    assert resp.status_code == 200
    assert b"dc01.corp.local" in resp.data
    assert b"svc_backup" in resp.data
    assert rb"evil.exe" in resp.data
    assert b"Beacon established" in resp.data


def test_finding_correlations_appear_in_markdown_report(admin_client):
    engagement_id = _create_engagement(admin_client, name="Report Co")
    node_id = _create_target_node(admin_client, engagement_id, name="dc01.corp.local")
    cred_id = _create_credential(admin_client, engagement_id, username="svc_backup")
    ioc_id = _create_ioc(admin_client, engagement_id, location=r"C:\Temp\evil.exe")
    entry_id = _create_killchain_entry(admin_client, engagement_id, title="Beacon established")

    _create_finding_with_links(
        admin_client,
        engagement_id,
        "Fully linked finding",
        infra_node_ids=[node_id],
        credential_ids=[cred_id],
        ioc_ids=[ioc_id],
        killchain_entry_ids=[entry_id],
    )

    resp = admin_client.get(f"/engagements/{engagement_id}/findings/report.md")
    md = resp.data.decode()
    assert "**Affected hosts:** dc01.corp.local" in md
    assert "**Related credentials:**" in md and "svc_backup" in md
    assert "**Related IOCs:**" in md and "evil.exe" in md
    assert "**Related kill chain entries:**" in md and "Beacon established" in md


def test_deleting_finding_does_not_delete_linked_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target_node(admin_client, engagement_id)
    finding_id = _create_finding_with_links(
        admin_client, engagement_id, "Temp finding", infra_node_ids=[node_id]
    )

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/findings/{finding_id}/delete",
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        node = InfrastructureNode.query.get(node_id)
        assert node is not None
        assert node.findings == []
