from tests.test_engagements import _create_engagement


def _seed_basic_data(app):
    """Creates one engagement with a finding and a todo, returns their ids."""
    with app.app_context():
        from app.extensions import db
        from app.models.engagement import Engagement
        from app.models.finding import SEVERITY_HIGH, Finding
        from app.models.todo import STATUS_OPEN, Todo
        from app.models.user import User

        user = User.query.first()
        engagement = Engagement(name="Restore Test Co", client_name="Restore Test Co", created_by_id=user.id)
        db.session.add(engagement)
        db.session.flush()
        finding = Finding(
            engagement_id=engagement.id, title="Test Finding", severity=SEVERITY_HIGH,
            details="<p>details</p>", created_by_id=user.id,
        )
        todo = Todo(engagement_id=engagement.id, title="Test Todo", status=STATUS_OPEN, created_by_id=user.id)
        db.session.add_all([finding, todo])
        db.session.commit()
        return engagement.id, finding.id, todo.id


def _build_archive(app, scope=None, engagement_id=None):
    with app.app_context():
        from app.models.backup import PROVIDER_OTHER, SCOPE_DATABASE_ONLY, SCOPE_ENGAGEMENT, SCOPE_FULL_VAULT, BackupDestination
        from app.models.user import User
        from app.services import backup_service

        user = User.query.first()
        destination = BackupDestination(
            name="test-dest", provider=PROVIDER_OTHER, scope=scope or SCOPE_FULL_VAULT,
            engagement_id=engagement_id, created_by_id=user.id,
        )
        return backup_service.build_archive(destination)


def test_inspect_full_vault_archive(app, admin_client):
    _seed_basic_data(app)
    path = _build_archive(app)
    with app.app_context():
        from app.services import restore_service

        info = restore_service.inspect_archive(path)
    assert info["has_database"] is True
    assert info["can_restore_full"] is True
    assert info["can_restore_loot_only"] is False
    assert info["table_counts"]["engagements"] >= 1
    assert info["table_counts"]["findings"] >= 1


def test_full_restore_round_trip_preserves_data(app, admin_client):
    engagement_id, finding_id, todo_id = _seed_basic_data(app)
    path = _build_archive(app)

    with app.app_context():
        from app.extensions import db
        from app.models.engagement import Engagement
        from app.models.finding import Finding
        from app.models.todo import Todo
        from app.services import restore_service

        summary = restore_service.restore_full_archive(path)
        assert summary["tables"]["engagements"] >= 1

        db.session.expire_all()
        engagement = Engagement.query.get(engagement_id)
        assert engagement is not None
        assert engagement.name == "Restore Test Co"
        assert Finding.query.get(finding_id) is not None
        assert Todo.query.get(todo_id) is not None


def test_full_restore_wipes_data_created_after_the_backup(app, admin_client):
    _seed_basic_data(app)
    path = _build_archive(app)

    with app.app_context():
        from app.extensions import db
        from app.models.engagement import Engagement
        from app.models.user import User

        user = User.query.first()
        later = Engagement(name="Created After Backup", client_name="Later Co", created_by_id=user.id)
        db.session.add(later)
        db.session.commit()
        later_id = later.id

        from app.services import restore_service

        restore_service.restore_full_archive(path)

        db.session.expire_all()
        assert Engagement.query.get(later_id) is None
        assert Engagement.query.filter_by(name="Restore Test Co").first() is not None


def test_self_referential_technique_survives_restore(app, admin_client):
    with app.app_context():
        from app.extensions import db
        from app.models.attack import AttackTechnique

        parent = AttackTechnique(attack_id="T9999", name="Parent Technique", description="d")
        db.session.add(parent)
        db.session.flush()
        child = AttackTechnique(
            attack_id="T9999.001", name="Sub Technique", description="d", parent_technique_id=parent.id
        )
        db.session.add(child)
        db.session.commit()
        child_id, parent_id = child.id, parent.id

    path = _build_archive(app)

    with app.app_context():
        from app.extensions import db
        from app.models.attack import AttackTechnique
        from app.services import restore_service

        restore_service.restore_full_archive(path)

        db.session.expire_all()
        restored_child = AttackTechnique.query.filter_by(attack_id="T9999.001").first()
        restored_parent = AttackTechnique.query.filter_by(attack_id="T9999").first()
        assert restored_child is not None
        assert restored_parent is not None
        assert restored_child.parent_technique_id == restored_parent.id


def test_restore_loot_only_reattaches_matching_files_and_skips_missing(app, admin_client):
    eng_id, _, _ = _seed_basic_data(app)

    with app.app_context():
        from app.extensions import db
        from app.models.loot import LootFile
        from app.models.user import User

        user = User.query.first()
        loot = LootFile(
            engagement_id=eng_id, original_filename="secret.txt", encrypted_content=b"original-ciphertext",
            file_size_bytes=10, uploaded_by_id=user.id,
        )
        db.session.add(loot)
        db.session.commit()
        loot_id = loot.id

    path = _build_archive(app)

    with app.app_context():
        from app.extensions import db
        from app.models.loot import LootFile

        loot = LootFile.query.get(loot_id)
        loot.encrypted_content = b"corrupted"
        db.session.commit()

        from app.services import restore_service

        summary = restore_service.restore_loot_only(path)
        assert summary["restored"] == 1
        assert summary["skipped"] == 0

        db.session.expire_all()
        restored = LootFile.query.get(loot_id)
        assert restored.encrypted_content == b"original-ciphertext"


def test_engagement_scoped_archive_is_not_auto_restorable(app, admin_client):
    eng_id, _, _ = _seed_basic_data(app)
    from app.models.backup import SCOPE_ENGAGEMENT

    path = _build_archive(app, scope=SCOPE_ENGAGEMENT, engagement_id=eng_id)

    with app.app_context():
        from app.services import restore_service

        info = restore_service.inspect_archive(path)
        assert info["has_engagement_manifest"] is True
        assert info["can_restore_full"] is False
        assert info["can_restore_loot_only"] is False


def test_restore_execute_requires_exact_confirm_phrase(app, admin_client):
    from tests.conftest import csrf_token

    _seed_basic_data(app)
    with app.app_context():
        from app.models.backup import PROVIDER_OTHER, SCOPE_FULL_VAULT, BackupDestination
        from app.extensions import db
        from app.models.user import User

        user = User.query.first()
        destination = BackupDestination(
            name="confirm-test", provider=PROVIDER_OTHER, scope=SCOPE_FULL_VAULT, created_by_id=user.id
        )
        db.session.add(destination)
        db.session.commit()
        backup_id = destination.id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/backups/{backup_id}/files/whatever.zip/restore",
        data={"csrf_token": csrf, "mode": "full", "confirm_phrase": "not-restore"},
    )
    assert resp.status_code == 302
    assert "/files/" in resp.headers["Location"]
