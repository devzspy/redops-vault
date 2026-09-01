"""One `*_dict()` function per model exposed over /api/v1. Each pulls the
same fields/labels the Jinja templates already render (reusing the
`*_label()` helpers already defined on the models) so API output and HTML
output can't drift apart.
"""

from app.models.engagement import STATUS_LABELS
from app.models.killchain import KILL_CHAIN_MODEL_LABELS
from app.models.loot import Credential, LootFile
from app.services import credential_service


def _iso(value):
    return value.isoformat() if value is not None else None


def user_ref(user):
    if user is None:
        return None
    return {"id": user.id, "username": user.username}


def engagement_link_dict(link):
    return {
        "id": link.id,
        "engagement_id": link.engagement_id,
        "link_type": link.link_type,
        "link_type_label": link.link_type_label(),
        "url": link.url,
        "label": link.label,
        "notes": link.notes,
        "added_by": user_ref(link.added_by),
        "added_at": _iso(link.added_at),
    }


def engagement_assignment_dict(assignment):
    return {
        "id": assignment.id,
        "engagement_id": assignment.engagement_id,
        "user": user_ref(assignment.user),
        "assigned_by": user_ref(assignment.assigned_by),
        "assigned_at": _iso(assignment.assigned_at),
    }


def threat_model_dict(plan):
    if plan is None:
        return None
    return {
        "engagement_id": plan.engagement_id,
        "threat_model": plan.threat_model,
        "attack_plan": plan.attack_plan,
        "objectives": plan.objectives,
        "is_empty": plan.is_empty(),
        "updated_at": _iso(plan.updated_at),
        "updated_by": user_ref(plan.updated_by),
    }


def engagement_summary_dict(engagement):
    return {
        "id": engagement.id,
        "name": engagement.name,
        "client_name": engagement.client_name,
        "description": engagement.description,
        "start_date": _iso(engagement.start_date),
        "end_date": _iso(engagement.end_date),
        "status": engagement.status,
        "status_label": STATUS_LABELS.get(engagement.status, engagement.status),
        "kill_chain_model": engagement.kill_chain_model,
        "kill_chain_model_label": KILL_CHAIN_MODEL_LABELS.get(engagement.kill_chain_model, engagement.kill_chain_model),
        "is_archived": engagement.is_archived,
        "created_by": user_ref(engagement.created_by),
        "created_at": _iso(engagement.created_at),
    }


def engagement_detail_dict(engagement):
    from app.models.finding import Finding
    from app.models.infrastructure import InfrastructureEdge, InfrastructureNode
    from app.models.ioc import IOC
    from app.models.killchain import KillChainEntry
    from app.models.todo import Todo

    data = engagement_summary_dict(engagement)
    eid = engagement.id
    data.update(
        {
            "threat_model": threat_model_dict(engagement.threat_model),
            "links": [engagement_link_dict(link) for link in engagement.links],
            "assignments": [engagement_assignment_dict(a) for a in engagement.assignments],
            "loot_files_count": LootFile.query.filter_by(engagement_id=eid).count(),
            "credentials_count": Credential.query.filter_by(engagement_id=eid).count(),
            "findings_count": Finding.query.filter_by(engagement_id=eid).count(),
            "killchain_entries_count": KillChainEntry.query.filter_by(engagement_id=eid).count(),
            "infrastructure_nodes_count": InfrastructureNode.query.filter_by(engagement_id=eid).count(),
            "infrastructure_edges_count": InfrastructureEdge.query.filter_by(engagement_id=eid).count(),
            "iocs_count": IOC.query.filter_by(engagement_id=eid).count(),
            "todos_count": Todo.query.filter_by(engagement_id=eid).count(),
        }
    )
    return data


def finding_dict(finding):
    return {
        "id": finding.id,
        "engagement_id": finding.engagement_id,
        "title": finding.title,
        "severity": finding.severity,
        "severity_label": finding.severity_label(),
        "details": finding.details,
        "remediation": finding.remediation,
        "created_by": user_ref(finding.created_by),
        "created_at": _iso(finding.created_at),
        "loot_files": [{"id": f.id, "filename": f.original_filename} for f in finding.loot_files],
        "infra_nodes": [{"id": n.id, "name": n.name} for n in finding.infra_nodes],
        "credentials": [{"id": c.id, "label": c.display_label()} for c in finding.credentials],
        "iocs": [{"id": i.id, "label": i.display_label()} for i in finding.iocs],
        "killchain_entries": [
            {"id": e.id, "title": e.title, "stage": e.stage} for e in finding.killchain_entries
        ],
    }


def loot_file_dict(loot_file):
    return {
        "id": loot_file.id,
        "engagement_id": loot_file.engagement_id,
        "original_filename": loot_file.original_filename,
        "category": loot_file.category,
        "description": loot_file.description,
        "tags": loot_file.tag_list(),
        "associated_host": loot_file.associated_host,
        "file_size_bytes": loot_file.file_size_bytes,
        "content_type": loot_file.content_type,
        "sha256_plaintext": loot_file.sha256_plaintext,
        "uploaded_by": user_ref(loot_file.uploaded_by),
        "uploaded_at": _iso(loot_file.uploaded_at),
    }


def credential_dict(credential, reveal=False):
    data = {
        "id": credential.id,
        "engagement_id": credential.engagement_id,
        "credential_type": credential.credential_type,
        "credential_type_label": credential.credential_type_label(),
        "username": credential.username,
        "domain": credential.domain,
        "source_host": credential.source_host,
        "access_description": credential.access_description,
        "status": credential.status,
        "status_label": credential.status_label(),
        "notes": credential.notes,
        "display_label": credential.display_label(),
        "has_password": credential.password_encrypted is not None,
        "has_hash": credential.hash_encrypted is not None,
        "has_api_key": credential.api_key_encrypted is not None,
        "has_ssh_private_key": credential.ssh_private_key_encrypted is not None,
        "has_ssh_passphrase": credential.ssh_passphrase_encrypted is not None,
        "has_totp": credential.totp_secret_encrypted is not None,
        "added_by": user_ref(credential.added_by),
        "added_at": _iso(credential.added_at),
    }
    if reveal:
        data["secrets"] = credential_service.decrypt(credential)
    return data


def killchain_entry_dict(entry):
    return {
        "id": entry.id,
        "engagement_id": entry.engagement_id,
        "stage": entry.stage,
        "stage_label": entry.stage_label(),
        "title": entry.title,
        "description": entry.description,
        "host": entry.host,
        "infra_node": {"id": entry.infra_node.id, "name": entry.infra_node.name} if entry.infra_node else None,
        "occurred_at": _iso(entry.occurred_at),
        "occurred_ended_at": _iso(entry.occurred_ended_at),
        "occurred_range_label": entry.occurred_range_label(),
        "loot_files": [{"id": f.id, "filename": f.original_filename} for f in entry.loot_files],
        "created_by": user_ref(entry.created_by),
        "created_at": _iso(entry.created_at),
    }


def infra_node_dict(node):
    return {
        "id": node.id,
        "engagement_id": node.engagement_id,
        "node_type": node.node_type,
        "name": node.name,
        "role": node.role,
        "status": node.status,
        "provider": node.provider,
        "region": node.region,
        "notes": node.notes,
        "services": [{"id": s.id, "name": s.name, "port": s.port, "display": s.display()} for s in node.services],
        "added_by": user_ref(node.added_by),
        "added_at": _iso(node.added_at),
    }


def infra_edge_dict(edge):
    return {
        "id": edge.id,
        "engagement_id": edge.engagement_id,
        "source_node": {"id": edge.source_node.id, "name": edge.source_node.name},
        "target_node": {"id": edge.target_node.id, "name": edge.target_node.name},
        "label": edge.label,
        "notes": edge.notes,
        "added_by": user_ref(edge.added_by),
        "added_at": _iso(edge.added_at),
    }


def ioc_dict(ioc):
    return {
        "id": ioc.id,
        "engagement_id": ioc.engagement_id,
        "host": ioc.host,
        "location": ioc.location,
        "hash_type": ioc.hash_type,
        "hash_type_label": ioc.hash_type_label(),
        "hash_value": ioc.hash_value,
        "dropped_at": _iso(ioc.dropped_at),
        "notes": ioc.notes,
        "display_label": ioc.display_label(),
        "added_by": user_ref(ioc.added_by),
        "added_at": _iso(ioc.added_at),
    }


def todo_dict(todo):
    return {
        "id": todo.id,
        "engagement_id": todo.engagement_id,
        "title": todo.title,
        "notes": todo.notes,
        "status": todo.status,
        "status_label": todo.status_label(),
        "is_in_progress": todo.is_in_progress(),
        "is_available": todo.is_available(),
        "assignee": user_ref(todo.assignee),
        "handoff_notes": todo.handoff_notes,
        "created_by": user_ref(todo.created_by),
        "created_at": _iso(todo.created_at),
        "updated_at": _iso(todo.updated_at),
        "completed_at": _iso(todo.completed_at),
        "completed_by": user_ref(todo.completed_by),
    }


def attack_technique_summary_dict(technique):
    return {
        "id": technique.id,
        "attack_id": technique.attack_id,
        "name": technique.name,
        "is_subtechnique": technique.is_subtechnique,
    }


def attack_technique_dict(technique):
    return {
        "id": technique.id,
        "attack_id": technique.attack_id,
        "name": technique.name,
        "description": technique.description,
        "is_subtechnique": technique.is_subtechnique,
        "parent_technique_id": technique.parent_technique_id,
        "url": technique.url,
        "last_synced_at": _iso(technique.last_synced_at),
        "tactics": [{"attack_id": t.attack_id, "name": t.name} for t in technique.tactics],
        "sub_techniques": [attack_technique_summary_dict(s) for s in technique.sub_techniques],
    }


def attack_tactic_dict(tactic):
    return {
        "id": tactic.id,
        "attack_id": tactic.attack_id,
        "name": tactic.name,
        "short_name": tactic.short_name,
        "description": tactic.description,
        "url": tactic.url,
        "techniques": [
            attack_technique_summary_dict(t) for t in tactic.techniques if not t.is_subtechnique
        ],
    }


def technique_mapping_dict(mapping):
    return {
        "id": mapping.id,
        "engagement_id": mapping.engagement_id,
        "technique": {"attack_id": mapping.technique.attack_id, "name": mapping.technique.name},
        "loot_file_id": mapping.loot_file_id,
        "killchain_entry_id": mapping.killchain_entry_id,
        "notes": mapping.notes,
        "mapped_by": user_ref(mapping.mapped_by),
        "mapped_at": _iso(mapping.mapped_at),
    }


def activity_entry_dict(entry):
    return {
        "id": entry.id,
        "engagement_id": entry.engagement_id,
        "actor": user_ref(entry.actor) if entry.actor_id else None,
        "actor_label": entry.actor_label,
        "entity_type": entry.entity_type,
        "action": entry.action,
        "summary": entry.summary,
        "occurred_started_at": _iso(entry.occurred_started_at),
        "occurred_ended_at": _iso(entry.occurred_ended_at),
        "occurred_range_label": entry.occurred_range_label(),
        "created_at": _iso(entry.created_at),
    }
