"""Aggregates everything in the vault related to one target/victim
InfrastructureNode into a single chronological feed, for the "one stop
shop" target detail page.

KillChainEntry links to a node with a real foreign key (infra_node_id),
and Finding links via a many-to-many association (giving InfrastructureNode
its `findings` backref for free). Credential, LootFile, and IOC only carry
a free-text host field (source_host / associated_host / host) rather than
a foreign key, so those are matched case-insensitively against the node's
name -- the same convention app/services/loot_service.py already uses when
auto-creating a node from an uploaded file's associated_host. This means
the correlation is best-effort: a credential logged against "10.0.0.5"
won't surface here if the node is named "dc01.corp.local", even if they're
the same host.
"""

from datetime import datetime

from app.extensions import db
from app.models.ioc import IOC
from app.models.killchain import KillChainEntry
from app.models.loot import Credential, LootFile

_MIN_DATETIME = datetime.min


def _event(kind, timestamp, obj):
    return {"kind": kind, "timestamp": timestamp, "obj": obj}


def gather(node):
    """Returns a dict of the node's related records (each engagement-scoped
    and, for the free-text fields, name-matched to this node) plus a
    "timeline" list of the same records merged and sorted newest-first.
    """
    engagement_id = node.engagement_id
    name = (node.name or "").strip().lower()

    killchain_entries = (
        KillChainEntry.query.filter_by(engagement_id=engagement_id, infra_node_id=node.id)
        .order_by(KillChainEntry.occurred_at.asc())
        .all()
    )
    credentials = (
        Credential.query.filter(
            Credential.engagement_id == engagement_id, db.func.lower(Credential.source_host) == name
        )
        .order_by(Credential.added_at.asc())
        .all()
    )
    loot_files = (
        LootFile.query.filter(
            LootFile.engagement_id == engagement_id, db.func.lower(LootFile.associated_host) == name
        )
        .order_by(LootFile.uploaded_at.asc())
        .all()
    )
    iocs = (
        IOC.query.filter(IOC.engagement_id == engagement_id, db.func.lower(IOC.host) == name)
        .order_by(IOC.added_at.asc())
        .all()
    )
    findings = sorted(node.findings, key=lambda f: f.created_at)

    timeline = (
        [_event("killchain", entry.occurred_at or entry.created_at, entry) for entry in killchain_entries]
        + [_event("credential", cred.added_at, cred) for cred in credentials]
        + [_event("loot", loot.uploaded_at, loot) for loot in loot_files]
        + [_event("ioc", ioc.dropped_at or ioc.added_at, ioc) for ioc in iocs]
        + [_event("finding", finding.created_at, finding) for finding in findings]
    )
    timeline.sort(key=lambda e: e["timestamp"] or _MIN_DATETIME, reverse=True)

    return {
        "killchain_entries": killchain_entries,
        "credentials": credentials,
        "loot_files": loot_files,
        "iocs": iocs,
        "findings": findings,
        "timeline": timeline,
    }
