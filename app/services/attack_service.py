from collections import defaultdict

from app.models.attack import AttackTactic
from app.models.engagement import Engagement
from app.models.killchain import TechniqueMapping


def build_matrix_tactics():
    """Loads the ATT&CK matrix and annotates each top-level technique with
    which engagements have used it (directly, or via one of its
    sub-techniques), for the browse page's orange highlighting + popover.
    """
    tactics = AttackTactic.query.order_by(AttackTactic.attack_id.asc()).all()

    mapping_rows = (
        TechniqueMapping.query.join(Engagement, TechniqueMapping.engagement_id == Engagement.id)
        .with_entities(TechniqueMapping.technique_id, Engagement.id, Engagement.name)
        .all()
    )
    engagements_by_technique = defaultdict(dict)
    for technique_id, engagement_id, engagement_name in mapping_rows:
        engagements_by_technique[technique_id][engagement_id] = engagement_name

    for tactic in tactics:
        for technique in tactic.techniques:
            if technique.is_subtechnique:
                continue

            usage_by_engagement = {}
            for eid, ename in engagements_by_technique.get(technique.id, {}).items():
                usage_by_engagement[eid] = {"name": ename, "direct": True, "via_subs": []}
            for sub in technique.sub_techniques:
                for eid, ename in engagements_by_technique.get(sub.id, {}).items():
                    usage_by_engagement.setdefault(eid, {"name": ename, "direct": False, "via_subs": []})
                    usage_by_engagement[eid]["via_subs"].append(sub)

            technique.matrix_usage = sorted(usage_by_engagement.items(), key=lambda kv: kv[1]["name"])
            technique.matrix_is_used = bool(technique.matrix_usage)

    return tactics
