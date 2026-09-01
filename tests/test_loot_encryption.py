import io

from tests.conftest import csrf_token


def _create_engagement(client):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": "Loot Co", "client_name": "Loot Co", "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def test_uploaded_file_is_encrypted_in_db_and_downloads_intact(admin_client):
    engagement_id = _create_engagement(admin_client)
    plaintext = b"top secret loot: admin:P@ssw0rd123\n" * 100

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(plaintext), "notes.txt"),
            "category": "note",
            "description": "test note",
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    file_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    with admin_client.application.app_context():
        from app.models.loot import LootFile

        loot_file = LootFile.query.get(file_id)
        assert loot_file.file_size_bytes == len(plaintext)

        raw_bytes = loot_file.encrypted_content
        assert plaintext not in raw_bytes
        assert b"P@ssw0rd123" not in raw_bytes

    download = admin_client.get(f"/engagements/{engagement_id}/loot/{file_id}/download")
    assert download.status_code == 200
    assert download.data == plaintext


def _create_node(client, engagement_id, name="dc01.corp.local", role="target"):
    endpoint = "targets" if role in ("target", "victim") else "infrastructure/nodes"
    csrf = csrf_token(client)
    client.post(
        f"/engagements/{engagement_id}/{endpoint}",
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


def test_associated_host_dropdown_populated_from_infrastructure(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="dc01.corp.local")

    form_page = admin_client.get(f"/engagements/{engagement_id}/loot/upload")
    assert form_page.status_code == 200
    assert b"dc01.corp.local" in form_page.data
    assert b"Other" in form_page.data
    assert b"N/A" not in form_page.data

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(b"loot"), "creds.txt"),
            "category": "note",
            "associated_host": "dc01.corp.local",
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    file_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    with admin_client.application.app_context():
        from app.models.loot import LootFile

        loot_file = LootFile.query.get(file_id)
        assert loot_file.associated_host == "dc01.corp.local"


def test_associated_host_dropdown_excludes_attacker_infrastructure(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="dc01.corp.local", role="target")
    _create_node(admin_client, engagement_id, name="redirector01.evilcorp.test", role="redirector")

    upload_page = admin_client.get(f"/engagements/{engagement_id}/loot/upload")
    assert upload_page.status_code == 200
    assert b"dc01.corp.local" in upload_page.data
    assert b"redirector01.evilcorp.test" not in upload_page.data

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(b"loot"), "creds.txt"),
            "category": "note",
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    file_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    edit_page = admin_client.get(f"/engagements/{engagement_id}/loot/{file_id}")
    assert edit_page.status_code == 200
    assert b"dc01.corp.local" in edit_page.data
    assert b"redirector01.evilcorp.test" not in edit_page.data


def test_victim_role_also_appears_in_associated_host_dropdown(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="finance-pc.corp.local", role="victim")

    upload_page = admin_client.get(f"/engagements/{engagement_id}/loot/upload")
    assert upload_page.status_code == 200
    assert b"finance-pc.corp.local" in upload_page.data


def test_associated_host_other_blank_stores_null_and_edit_form_has_no_none_text(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="dc01.corp.local")

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(b"loot"), "creds.txt"),
            "category": "note",
            "associated_host": "__other__",
            "associated_host_other": "",
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    file_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    with admin_client.application.app_context():
        from app.models.loot import LootFile

        assert LootFile.query.get(file_id).associated_host is None

    edit_page = admin_client.get(f"/engagements/{engagement_id}/loot/{file_id}")
    assert edit_page.status_code == 200
    assert b"value=\"None\"" not in edit_page.data
    assert b"dc01.corp.local" in edit_page.data


def test_associated_host_other_creates_target_infrastructure_node(admin_client):
    engagement_id = _create_engagement(admin_client)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(b"loot"), "creds.txt"),
            "category": "note",
            "associated_host": "__other__",
            "associated_host_other": "new-host.local",
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    file_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    with admin_client.application.app_context():
        from app.models.infrastructure import ROLE_TARGET, InfrastructureNode
        from app.models.loot import LootFile

        assert LootFile.query.get(file_id).associated_host == "new-host.local"
        node = InfrastructureNode.query.filter_by(
            engagement_id=engagement_id, name="new-host.local"
        ).first()
        assert node is not None
        assert node.role == ROLE_TARGET

    edit_page = admin_client.get(f"/engagements/{engagement_id}/loot/{file_id}")
    assert edit_page.status_code == 200
    assert b"new-host.local" in edit_page.data


def test_associated_host_other_does_not_duplicate_existing_node(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="dc01.corp.local")

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(b"loot"), "creds.txt"),
            "category": "note",
            "associated_host": "__other__",
            "associated_host_other": "dc01.corp.local",
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        matches = InfrastructureNode.query.filter_by(
            engagement_id=engagement_id, name="dc01.corp.local"
        ).all()
        assert len(matches) == 1


def test_credential_fields_are_encrypted_in_db(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/credentials",
        data={
            "username": "svc_backup",
            "password": "hunter2hunter2",
            "hash": "aad3b435b51404eeaad3b435b51404ee",
            "domain": "CORP",
            "source_host": "dc01.corp.local",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential
        from app.services import crypto_service

        cred = Credential.query.filter_by(engagement_id=engagement_id).first()
        assert cred is not None
        assert b"hunter2hunter2" not in cred.password_encrypted
        assert crypto_service.decrypt_field(cred.password_encrypted) == "hunter2hunter2"
        assert crypto_service.decrypt_field(cred.hash_encrypted) == "aad3b435b51404eeaad3b435b51404ee"

    resp = admin_client.get(f"/engagements/{engagement_id}/credentials")
    assert resp.status_code == 200
    assert b"hunter2hunter2" in resp.data


def test_edit_credential_updates_and_reencrypts_fields(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/credentials",
        data={
            "username": "svc_backup",
            "password": "hunter2hunter2",
            "hash": "",
            "domain": "CORP",
            "source_host": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential

        cred_id = Credential.query.filter_by(engagement_id=engagement_id).first().id

    edit_page = admin_client.get(f"/engagements/{engagement_id}/credentials/{cred_id}/edit")
    assert edit_page.status_code == 200
    assert b"hunter2hunter2" in edit_page.data
    assert b"value=\"None\"" not in edit_page.data

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/credentials/{cred_id}/edit",
        data={
            "username": "svc_backup2",
            "password": "newpassword123",
            "hash": "",
            "domain": "CORP",
            "source_host": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential
        from app.services import crypto_service

        cred = Credential.query.get(cred_id)
        assert cred.username == "svc_backup2"
        assert crypto_service.decrypt_field(cred.password_encrypted) == "newpassword123"


def test_source_host_dropdown_populated_from_infrastructure(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/targets",
        data={
            "node_type": "hostname",
            "name": "dc01.corp.local",
            "role": "target",
            "provider": "",
            "region": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )

    form_page = admin_client.get(f"/engagements/{engagement_id}/credentials/new")
    assert form_page.status_code == 200
    assert b"dc01.corp.local" in form_page.data
    assert b"N/A" in form_page.data

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/credentials",
        data={
            "username": "svc_backup",
            "password": "",
            "hash": "",
            "domain": "",
            "source_host": "dc01.corp.local",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential

        cred = Credential.query.filter_by(engagement_id=engagement_id).first()
        assert cred.source_host == "dc01.corp.local"


def test_source_host_dropdown_excludes_attacker_infrastructure(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="dc01.corp.local", role="target")
    _create_node(admin_client, engagement_id, name="c2.evilcorp.test", role="C2")

    new_form = admin_client.get(f"/engagements/{engagement_id}/credentials/new")
    assert new_form.status_code == 200
    assert b"dc01.corp.local" in new_form.data
    assert b"c2.evilcorp.test" not in new_form.data

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/credentials",
        data={
            "username": "svc_backup",
            "password": "",
            "hash": "",
            "domain": "",
            "source_host": "dc01.corp.local",
            "csrf_token": csrf,
        },
    )

    with admin_client.application.app_context():
        from app.models.loot import Credential

        cred_id = Credential.query.filter_by(engagement_id=engagement_id).first().id

    edit_form = admin_client.get(f"/engagements/{engagement_id}/credentials/{cred_id}/edit")
    assert edit_form.status_code == 200
    assert b"dc01.corp.local" in edit_form.data
    assert b"c2.evilcorp.test" not in edit_form.data


def test_source_host_na_option_stores_null(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/credentials",
        data={
            "username": "svc_backup",
            "password": "",
            "hash": "",
            "domain": "",
            "source_host": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential

        cred = Credential.query.filter_by(engagement_id=engagement_id).first()
        assert cred.source_host is None


def _create_credential(client, engagement_id, **overrides):
    csrf = csrf_token(client)
    data = {
        "username": "svc_backup",
        "credential_type": "password",
        "status": "untested",
        "password": "",
        "hash": "",
        "api_key": "",
        "ssh_private_key": "",
        "ssh_passphrase": "",
        "totp_secret": "",
        "domain": "",
        "source_host": "",
        "access_description": "",
        "notes": "",
        "csrf_token": csrf,
    }
    data.update(overrides)
    return client.post(f"/engagements/{engagement_id}/credentials", data=data)


def test_credential_defaults_to_password_type_and_untested_status(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _create_credential(admin_client, engagement_id)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential

        cred = Credential.query.filter_by(engagement_id=engagement_id).first()
        assert cred.credential_type == "password"
        assert cred.status == "untested"


def test_credential_access_description_and_status_are_saved(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _create_credential(
        admin_client,
        engagement_id,
        access_description="Domain Admin on CORP",
        status="working",
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential

        cred = Credential.query.filter_by(engagement_id=engagement_id).first()
        assert cred.access_description == "Domain Admin on CORP"
        assert cred.status == "working"

    resp = admin_client.get(f"/engagements/{engagement_id}/credentials")
    assert b"Domain Admin on CORP" in resp.data
    assert b"Working" in resp.data


def test_credential_rejects_invalid_status(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _create_credential(admin_client, engagement_id, status="on-fire")
    assert resp.status_code == 400

    with admin_client.application.app_context():
        from app.models.loot import Credential

        assert Credential.query.filter_by(engagement_id=engagement_id).count() == 0


def test_create_api_key_credential_is_encrypted(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _create_credential(
        admin_client,
        engagement_id,
        username="prod-deploy-key",
        credential_type="api_key",
        api_key="AKIAFAKEFAKEFAKEFAKE",
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential
        from app.services import crypto_service

        cred = Credential.query.filter_by(engagement_id=engagement_id).first()
        assert cred.credential_type == "api_key"
        assert b"AKIAFAKEFAKEFAKEFAKE" not in cred.api_key_encrypted
        assert crypto_service.decrypt_field(cred.api_key_encrypted) == "AKIAFAKEFAKEFAKEFAKE"

    resp = admin_client.get(f"/engagements/{engagement_id}/credentials")
    assert b"AKIAFAKEFAKEFAKEFAKE" in resp.data


def test_create_ssh_key_credential_is_encrypted(admin_client):
    engagement_id = _create_engagement(admin_client)
    key_material = "-----BEGIN OPENSSH PRIVATE KEY-----\nfakekeydata\n-----END OPENSSH PRIVATE KEY-----"
    resp = _create_credential(
        admin_client,
        engagement_id,
        username="ubuntu",
        credential_type="ssh_key",
        ssh_private_key=key_material,
        ssh_passphrase="hunter2",
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential
        from app.services import crypto_service

        cred = Credential.query.filter_by(engagement_id=engagement_id).first()
        assert cred.credential_type == "ssh_key"
        assert b"fakekeydata" not in cred.ssh_private_key_encrypted
        assert crypto_service.decrypt_field(cred.ssh_private_key_encrypted) == key_material
        assert crypto_service.decrypt_field(cred.ssh_passphrase_encrypted) == "hunter2"

    resp = admin_client.get(f"/engagements/{engagement_id}/credentials")
    assert b"Show private key" in resp.data


def test_credential_rejects_invalid_credential_type(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _create_credential(admin_client, engagement_id, credential_type="bitcoin_wallet")
    assert resp.status_code == 400

    with admin_client.application.app_context():
        from app.models.loot import Credential

        assert Credential.query.filter_by(engagement_id=engagement_id).count() == 0


def test_credential_totp_secret_is_encrypted_and_code_endpoint_works(admin_client):
    import base64

    engagement_id = _create_engagement(admin_client)
    secret = base64.b32encode(b"12345678901234567890").decode()
    resp = _create_credential(admin_client, engagement_id, totp_secret=secret)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential
        from app.services import crypto_service

        cred = Credential.query.filter_by(engagement_id=engagement_id).first()
        assert crypto_service.decrypt_field(cred.totp_secret_encrypted) == secret
        cred_id = cred.id

    resp = admin_client.get(f"/engagements/{engagement_id}/credentials/{cred_id}/totp")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload["code"]) == 6
    assert payload["code"].isdigit()
    assert 0 <= payload["seconds_remaining"] <= 30

    list_resp = admin_client.get(f"/engagements/{engagement_id}/credentials")
    assert b"data-totp-url" in list_resp.data
    assert payload["code"].encode() in list_resp.data


def test_credential_rejects_invalid_totp_secret(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _create_credential(admin_client, engagement_id, totp_secret="not-valid-base32!!")
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.loot import Credential

        assert Credential.query.filter_by(engagement_id=engagement_id).count() == 0

    follow = admin_client.get(resp.headers["Location"])
    assert b"must be a valid base32" in follow.data


def test_credential_totp_endpoint_404s_without_totp_secret(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_credential(admin_client, engagement_id)

    with admin_client.application.app_context():
        from app.models.loot import Credential

        cred_id = Credential.query.filter_by(engagement_id=engagement_id).first().id

    resp = admin_client.get(f"/engagements/{engagement_id}/credentials/{cred_id}/totp")
    assert resp.status_code == 404


def test_credential_list_hides_totp_chip_without_secret(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_credential(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/credentials")
    assert b"data-totp-url" not in resp.data
