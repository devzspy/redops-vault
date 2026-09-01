from tests.conftest import csrf_token


def _create_engagement(client):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": "Infra Co", "client_name": "Infra Co", "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_node(
    client, engagement_id, node_type="hostname", name="www.evilcorp-redirect.com", role="redirector", status=None
):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes",
        data={
            "node_type": node_type,
            "name": name,
            "role": role,
            "status": status or "",
            "provider": "DigitalOcean",
            "region": "nyc3",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        return InfrastructureNode.query.filter_by(engagement_id=engagement_id, name=name).first().id


def _create_target_node(
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


def test_create_node_appears_in_list(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert resp.status_code == 200
    assert b"www.evilcorp-redirect.com" in resp.data


def test_create_node_rejects_invalid_type(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes",
        data={"node_type": "not-a-real-type", "name": "bad-node", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.filter_by(engagement_id=engagement_id).count() == 0


def test_edit_and_delete_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_node(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/edit",
        data={
            "node_type": "hostname",
            "name": "renamed.evilcorp.com",
            "role": "team_server",
            "provider": "",
            "region": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert b"renamed.evilcorp.com" in resp.data

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/delete",
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.get(node_id) is None


def test_create_and_delete_edge(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_node(admin_client, engagement_id, name="c2.evilcorp.com", role="team_server")
    node_b = _create_node(admin_client, engagement_id, name="redirect.evilcorp.com", role="redirector")

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges",
        data={
            "source_node_id": str(node_a),
            "target_node_id": str(node_b),
            "label": "HTTPS/443",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert b"HTTPS/443" in resp.data

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        edge_id = InfrastructureEdge.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges/{edge_id}/delete",
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        assert InfrastructureEdge.query.get(edge_id) is None


def test_add_and_remove_service_on_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_node(admin_client, engagement_id, name="c2.evilcorp.com", role="team_server")

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/services",
        data={"name": "goPhish", "port": "8082", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert b"goPhish:8082" in resp.data

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/edit")
    assert b"goPhish:8082" in resp.data

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureService

        service = InfrastructureService.query.filter_by(node_id=node_id).first()
        assert service.name == "goPhish"
        assert service.port == 8082
        service_id = service.id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/services/{service_id}/delete",
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureService

        assert InfrastructureService.query.get(service_id) is None


def test_service_without_port_displays_name_only(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_node(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/services",
        data={"name": "SSH", "port": "", "csrf_token": csrf},
    )

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureService

        service = InfrastructureService.query.filter_by(node_id=node_id).first()
        assert service.port is None
        assert service.display() == "SSH"


def test_deleting_node_deletes_its_services(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_node(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/services",
        data={"name": "goPhish", "port": "8082", "csrf_token": csrf},
    )

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/delete",
        data={"csrf_token": csrf},
    )

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureService

        assert InfrastructureService.query.filter_by(node_id=node_id).count() == 0


def test_edit_edge_changes_source_target_and_label(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_node(admin_client, engagement_id, name="proxy.evilcorp.com", role="proxy")
    node_b = _create_node(admin_client, engagement_id, name="redirect.evilcorp.com", role="redirector")
    node_c = _create_node(admin_client, engagement_id, name="c2.evilcorp.com", role="team_server")

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges",
        data={
            "source_node_id": str(node_a),
            "target_node_id": str(node_b),
            "label": "HTTPS/443",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        edge_id = InfrastructureEdge.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges/{edge_id}/edit",
        data={
            "source_node_id": str(node_b),
            "target_node_id": str(node_c),
            "label": "C2/443",
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
        assert edge.label == "C2/443"

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert b"C2/443" in resp.data


def test_edge_rejects_same_source_and_target(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_node(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges",
        data={
            "source_node_id": str(node_a),
            "target_node_id": str(node_a),
            "label": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureEdge

        assert InfrastructureEdge.query.filter_by(engagement_id=engagement_id).count() == 0


def test_infra_edge_rejects_target_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_node(admin_client, engagement_id, name="redirect.evilcorp.com", role="redirector")
    node_b = _create_target_node(admin_client, engagement_id, name="victim01.corp.local", role="victim")

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges",
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


def test_infrastructure_network_pathing_excludes_target_edges(admin_client):
    engagement_id = _create_engagement(admin_client)
    attacker_a = _create_node(admin_client, engagement_id, name="redirect.evilcorp.com", role="redirector")
    attacker_b = _create_node(admin_client, engagement_id, name="c2.evilcorp.com", role="team_server")
    target_a = _create_target_node(admin_client, engagement_id, name="victim01.corp.local", role="victim")

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges",
        data={
            "source_node_id": str(attacker_a),
            "target_node_id": str(attacker_b),
            "label": "attacker-only path",
            "notes": "",
            "csrf_token": csrf,
        },
    )

    with admin_client.application.app_context():
        from app.extensions import db as _db
        from app.models.infrastructure import InfrastructureEdge

        legacy_edge = InfrastructureEdge(
            engagement_id=engagement_id,
            source_node_id=attacker_a,
            target_node_id=target_a,
            label="legacy cross edge",
            added_by_id=1,
        )
        _db.session.add(legacy_edge)
        _db.session.commit()

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert b"attacker-only path" in resp.data
    assert b"legacy cross edge" not in resp.data


def test_graph_json_shape(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_a = _create_node(admin_client, engagement_id, name="c2.evilcorp.com", role="team_server")
    node_b = _create_node(admin_client, engagement_id, name="redirect.evilcorp.com", role="redirector")
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges",
        data={
            "source_node_id": str(node_a),
            "target_node_id": str(node_b),
            "label": "HTTPS/443",
            "notes": "",
            "csrf_token": csrf,
        },
    )

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure/graph.json")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload["nodes"]) == 2
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["source"] == node_a
    assert payload["edges"][0]["target"] == node_b
    assert payload["killchain"] == []


def test_graph_json_includes_category_per_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_target_node(admin_client, engagement_id, name="victim01.corp.local", role="victim")
    _create_node(admin_client, engagement_id, name="redirector01.evilcorp.test", role="redirector")

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure/graph.json")
    assert resp.status_code == 200
    payload = resp.get_json()
    categories = {n["name"]: n["category"] for n in payload["nodes"]}
    assert categories["victim01.corp.local"] == "target"
    assert categories["redirector01.evilcorp.test"] == "attacker"


def test_attack_map_page_renders(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/attack-map")
    assert resp.status_code == 200
    assert b"Attack Map" in resp.data


def test_attack_map_has_killchain_timeline(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/attack-map")
    assert resp.status_code == 200
    assert b'id="timeline-scrubber"' in resp.data
    assert b"Unmapped kill chain entries" in resp.data


def test_attack_map_legend_lists_target_node_types_only(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/attack-map")
    assert resp.status_code == 200
    assert b"Wiki / Documentation" in resp.data
    assert b"File Share (SMB/NFS)" in resp.data
    assert b"Attacker Infrastructure" not in resp.data


def test_network_map_has_no_killchain_timeline(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/network")
    assert resp.status_code == 200
    assert b'id="timeline-scrubber"' not in resp.data
    assert b"Unmapped kill chain entries" not in resp.data


def test_killchain_entry_can_link_to_infra_node_and_unlinks_on_delete(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_node(admin_client, engagement_id, name="c2.evilcorp.com", role="team_server")

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "installation",
            "title": "Beacon established",
            "description": "",
            "host": "c2.evilcorp.com",
            "infra_node_id": str(node_id),
            "occurred_at": "2026-01-16T10:00",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.killchain import KillChainEntry

        entry = KillChainEntry.query.filter_by(engagement_id=engagement_id).first()
        assert entry.infra_node_id == node_id
        entry_id = entry.id

    graph = admin_client.get(f"/engagements/{engagement_id}/infrastructure/graph.json").get_json()
    assert graph["killchain"][0]["infra_node_id"] == node_id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/delete",
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.killchain import KillChainEntry

        entry = KillChainEntry.query.get(entry_id)
        assert entry is not None
        assert entry.infra_node_id is None


def test_target_nodes_do_not_appear_on_infrastructure_page(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_target_node(admin_client, engagement_id, name="victim01.corp.local", role="target")
    _create_node(admin_client, engagement_id, name="redirector01.evilcorp.test", role="redirector")

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert resp.status_code == 200
    assert b"redirector01.evilcorp.test" in resp.data
    assert b"victim01.corp.local" not in resp.data


def test_node_with_no_role_appears_on_infrastructure_page(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="unassigned.corp.local", role="")

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert resp.status_code == 200
    assert b"unassigned.corp.local" in resp.data


def test_infrastructure_create_node_rejects_target_role(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes",
        data={
            "node_type": "hostname",
            "name": "victim01.corp.local",
            "role": "target",
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


def test_infrastructure_edit_node_form_redirects_target_node_to_targets_pane(admin_client):
    engagement_id = _create_engagement(admin_client)
    node_id = _create_target_node(admin_client, engagement_id, name="victim01.corp.local", role="target")

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/edit")
    assert resp.status_code == 302
    assert resp.headers["Location"].rstrip("/").endswith(f"/targets/{node_id}/edit")


def test_add_node_button_without_role_hint_shows_generic_form(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure/nodes/new")
    assert resp.status_code == 200
    assert b"Add Infrastructure Node" in resp.data


def test_invalid_role_query_param_is_ignored(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure/nodes/new?role=not-a-real-role")
    assert resp.status_code == 200
    assert b"Add Infrastructure Node" in resp.data


def test_infra_node_accepts_burned_status(admin_client):
    engagement_id = _create_engagement(admin_client)

    node_id = _create_node(admin_client, engagement_id, name="redirector01.evilcorp.test", role="redirector", status="burned")

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        assert InfrastructureNode.query.get(node_id).status == "burned"


def test_infra_node_rejects_isolated_status(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    resp = admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/nodes",
        data={
            "node_type": "hostname",
            "name": "redirector01.evilcorp.test",
            "role": "redirector",
            "status": "isolated",
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


def test_status_badge_appears_in_infrastructure_list(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="redirector01.evilcorp.test", role="redirector", status="burned")

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure")
    assert resp.status_code == 200
    assert b"Burned" in resp.data


def test_new_infra_form_only_offers_infra_statuses(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/infrastructure/nodes/new")
    assert resp.status_code == 200
    assert b"Burned" in resp.data
    assert b"Isolated" not in resp.data
    assert b"Dead" not in resp.data


