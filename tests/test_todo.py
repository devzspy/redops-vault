from tests.conftest import csrf_token


def _create_engagement(client, name="Todo Co"):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": name, "client_name": name, "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_todo(client, engagement_id, title="Escalate privileges on DC01", notes=""):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/todos",
        data={"title": title, "notes": notes, "csrf_token": csrf},
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.todo import Todo

        return Todo.query.filter_by(engagement_id=engagement_id, title=title).first().id


def _add_operator(admin_client, second_client, username="bob", password="operatorpass123"):
    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": username, "password": password, "role": "operator", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": username, "password": password})


def test_create_todo_appears_in_open_section(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_todo(admin_client, engagement_id, title="Recon subnet", notes="Start with nmap")

    resp = admin_client.get(f"/engagements/{engagement_id}")
    assert resp.status_code == 200
    assert b"Todo Checklist" in resp.data
    assert b"Recon subnet" in resp.data
    assert b"Start with nmap" in resp.data

    with admin_client.application.app_context():
        from app.models.todo import STATUS_OPEN, Todo

        todo = Todo.query.filter_by(engagement_id=engagement_id).first()
        assert todo.status == STATUS_OPEN
        assert todo.assignee_id is None
        assert todo.is_available()
        assert not todo.is_in_progress()


def test_create_todo_requires_title(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/todos", data={"title": "", "csrf_token": csrf}
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.todo import Todo

        assert Todo.query.filter_by(engagement_id=engagement_id).count() == 0


def test_claim_todo_moves_to_in_progress(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/claim", data={"csrf_token": csrf}
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.todo import Todo

        todo = Todo.query.get(todo_id)
        assert todo.is_in_progress()
        assert todo.assignee.username == "admin"

    overview = admin_client.get(f"/engagements/{engagement_id}")
    assert b"Working: admin" in overview.data


def test_claim_completed_todo_rejected(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(f"/engagements/{engagement_id}/todos/{todo_id}/done", data={"csrf_token": csrf})

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/claim", data={"csrf_token": csrf}
    )
    assert resp.status_code == 400


def test_handoff_clears_assignee_and_sets_notes(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(f"/engagements/{engagement_id}/todos/{todo_id}/claim", data={"csrf_token": csrf})

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/handoff",
        data={"handoff_notes": "Got initial foothold, creds in loot #4", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.todo import Todo

        todo = Todo.query.get(todo_id)
        assert todo.assignee_id is None
        assert todo.is_available()
        assert todo.handoff_notes == "Got initial foothold, creds in loot #4"

    overview = admin_client.get(f"/engagements/{engagement_id}")
    assert b"Handoff notes: Got initial foothold" in overview.data


def test_handoff_completed_todo_rejected(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(f"/engagements/{engagement_id}/todos/{todo_id}/done", data={"csrf_token": csrf})

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/handoff", data={"csrf_token": csrf}
    )
    assert resp.status_code == 400


def test_mark_done_sets_completed_fields(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/done", data={"csrf_token": csrf}
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.todo import STATUS_DONE, Todo

        todo = Todo.query.get(todo_id)
        assert todo.status == STATUS_DONE
        assert todo.completed_at is not None
        assert todo.completed_by.username == "admin"
        assert not todo.is_in_progress()
        assert not todo.is_available()

    overview = admin_client.get(f"/engagements/{engagement_id}")
    assert b"Show completed" in overview.data


def test_reopen_clears_completed_fields(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(f"/engagements/{engagement_id}/todos/{todo_id}/done", data={"csrf_token": csrf})

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/reopen", data={"csrf_token": csrf}
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.todo import STATUS_OPEN, Todo

        todo = Todo.query.get(todo_id)
        assert todo.status == STATUS_OPEN
        assert todo.completed_at is None
        assert todo.completed_by_id is None


def test_delete_todo(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/delete", data={"csrf_token": csrf}
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.todo import Todo

        assert Todo.query.get(todo_id) is None


def test_shift_change_handoff_workflow(admin_client, second_client):
    engagement_id = _create_engagement(admin_client)
    _add_operator(admin_client, second_client, username="bob")

    todo_id = _create_todo(admin_client, engagement_id, title="Pivot to DC01")

    csrf = csrf_token(admin_client)
    admin_client.post(f"/engagements/{engagement_id}/todos/{todo_id}/claim", data={"csrf_token": csrf})

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/handoff",
        data={"handoff_notes": "Have local admin, need to dump lsass next.", "csrf_token": csrf},
    )

    with admin_client.application.app_context():
        from app.models.todo import Todo

        todo = Todo.query.get(todo_id)
        assert todo.assignee_id is None
        assert todo.is_available()

    bob_csrf = csrf_token(second_client)
    resp = second_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/claim", data={"csrf_token": bob_csrf}
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.todo import Todo

        todo = Todo.query.get(todo_id)
        assert todo.assignee.username == "bob"
        assert todo.is_in_progress()

    bob_csrf = csrf_token(second_client)
    second_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/done", data={"csrf_token": bob_csrf}
    )

    with admin_client.application.app_context():
        from app.models.todo import STATUS_DONE, Todo

        todo = Todo.query.get(todo_id)
        assert todo.status == STATUS_DONE
        assert todo.completed_by.username == "bob"


def test_todo_actions_are_logged_in_activity_feed(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id, title="Dump hashes")

    csrf = csrf_token(admin_client)
    admin_client.post(f"/engagements/{engagement_id}/todos/{todo_id}/claim", data={"csrf_token": csrf})
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/todos/{todo_id}/handoff", data={"csrf_token": csrf}
    )
    csrf = csrf_token(admin_client)
    admin_client.post(f"/engagements/{engagement_id}/todos/{todo_id}/claim", data={"csrf_token": csrf})
    csrf = csrf_token(admin_client)
    admin_client.post(f"/engagements/{engagement_id}/todos/{todo_id}/done", data={"csrf_token": csrf})

    with admin_client.application.app_context():
        from app.models.activity import ActivityLogEntry

        entries = (
            ActivityLogEntry.query.filter_by(engagement_id=engagement_id, entity_type="todo")
            .order_by(ActivityLogEntry.id.asc())
            .all()
        )
        actions = [e.action for e in entries]
        assert actions == ["created", "claimed", "handed_off", "claimed", "completed"]
        assert all("Dump hashes" in e.summary for e in entries)


def test_available_todos_are_scoped_per_engagement(admin_client):
    engagement_a = _create_engagement(admin_client, name="Engagement A")
    engagement_b = _create_engagement(admin_client, name="Engagement B")
    _create_todo(admin_client, engagement_a, title="Task in A")
    _create_todo(admin_client, engagement_b, title="Task in B")

    resp_a = admin_client.get(f"/engagements/{engagement_a}")
    assert b"Task in A" in resp_a.data
    assert b"Task in B" not in resp_a.data

    resp_b = admin_client.get(f"/engagements/{engagement_b}")
    assert b"Task in B" in resp_b.data
    assert b"Task in A" not in resp_b.data


def test_deleting_engagement_deletes_its_todos(admin_client):
    engagement_id = _create_engagement(admin_client)
    todo_id = _create_todo(admin_client, engagement_id)

    with admin_client.application.app_context():
        from app.extensions import db
        from app.models.engagement import Engagement
        from app.models.todo import Todo

        assert Todo.query.get(todo_id) is not None
        engagement = Engagement.query.get(engagement_id)
        db.session.delete(engagement)
        db.session.commit()
        assert Todo.query.get(todo_id) is None
