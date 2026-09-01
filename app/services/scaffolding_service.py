from datetime import datetime, timezone

from app.models.engagement_link import EngagementLink
from app.models.finding import Finding
from app.models.infrastructure import TARGET_ROLES, InfrastructureNode
from app.models.ioc import IOC
from app.models.killchain import KillChainEntry
from app.models.loot import Credential, LootFile
from app.models.todo import STATUS_DONE, Todo
from app.services.sanitize_service import html_to_markdown

TOOL_DOMAINS = [
    ("Engagement", "engagement_get, engagement_update, engagement_set_status, engagement_link_create"),
    ("Threat model", "threat_model_get, threat_model_save"),
    ("Todos", "todo_list, todo_create, todo_claim, todo_handoff, todo_complete, todo_reopen"),
    ("Kill chain", "killchain_list, killchain_create, killchain_update"),
    ("Findings", "finding_list, finding_create, finding_update, finding_report_markdown"),
    ("Loot", "loot_list, loot_upload, loot_download, loot_update"),
    ("Credentials", "credential_list, credential_create, credential_get (reveal=true), credential_totp"),
    ("Infrastructure", "infra_node_create, infra_service_create, infra_edge_create, infra_graph"),
    ("Targets & victims", "target_create, target_edge_create"),
    ("IOCs", "ioc_create, ioc_list"),
    ("ATT&CK", "attack_tactics, attack_technique_get, attack_map_technique_to_killchain"),
    ("Activity log", "activity_list"),
]


def _section(title, body):
    return f"## {title}\n\n{body.strip()}\n" if body and body.strip() else f"## {title}\n\n_Not documented yet._\n"


def _todo_lines(todos, empty_label):
    if not todos:
        return f"_{empty_label}_"
    lines = []
    for todo in todos:
        suffix = f" — assigned to {todo.assignee.username}" if todo.assignee_id and todo.assignee else ""
        lines.append(f"- [ ] (#{todo.id}) {todo.title}{suffix}")
    return "\n".join(lines)


def build_scaffolding(engagement):
    eid = engagement.id
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    plan = engagement.threat_model
    all_todos = Todo.query.filter_by(engagement_id=eid).order_by(Todo.created_at.asc()).all()
    in_progress = [t for t in all_todos if t.is_in_progress()]
    available = [t for t in all_todos if t.is_available()]
    done_count = sum(1 for t in all_todos if t.status == STATUS_DONE)

    links = (
        EngagementLink.query.filter_by(engagement_id=eid).order_by(EngagementLink.added_at.desc()).all()
    )

    counts = {
        "Findings": Finding.query.filter_by(engagement_id=eid).count(),
        "Loot files": LootFile.query.filter_by(engagement_id=eid).count(),
        "Credentials": Credential.query.filter_by(engagement_id=eid).count(),
        "Kill chain entries": KillChainEntry.query.filter_by(engagement_id=eid).count(),
        "Attacker infrastructure nodes": InfrastructureNode.query.filter_by(engagement_id=eid)
        .filter(InfrastructureNode.role.notin_(TARGET_ROLES))
        .count(),
        "Target/victim nodes": InfrastructureNode.query.filter_by(engagement_id=eid)
        .filter(InfrastructureNode.role.in_(TARGET_ROLES))
        .count(),
        "IOCs": IOC.query.filter_by(engagement_id=eid).count(),
    }

    lines = []
    lines.append(f"# RedOps Vault Agent Scaffolding — {engagement.name}")
    lines.append("")
    lines.append(
        f"Generated {generated} for engagement **#{eid}** (`{engagement.client_name}`). "
        "Paste this whole document into your agent's system prompt, project instructions "
        "(e.g. `CLAUDE.md` / `AGENTS.md`), or first message — it's everything it needs to "
        "start working this engagement through the RedOps Vault MCP server without being "
        "walked through each step."
    )
    lines.append("")

    lines.append("## Who you are")
    lines.append("")
    lines.append(
        f"You are an autonomous red-team operator agent working engagement **{engagement.name}** "
        f"(id `{eid}`) for client **{engagement.client_name}** via the `redops-vault` MCP server. "
        f"Current engagement status: **{engagement.status}**."
    )
    lines.append("")

    lines.append("## Operating principles")
    lines.append("")
    lines.append(
        "- **Work autonomously.** Don't stop and wait to be prompted for every step. When one "
        "action finishes, decide the next one from the objectives and checklist below and take "
        "it — only pause for the operator when you're genuinely blocked (missing scope/access, "
        "a legal/rules-of-engagement question, or nothing left to do).\n"
        f"- **Sync before you act.** Call `engagement_get(engagement_id={eid})` and "
        f"`todo_list(engagement_id={eid})` at the start of a session, and again after a break, "
        "since other operators (human or agent) may have made progress.\n"
        "- **Record as you go, not after.** Every meaningful action gets logged immediately: "
        "`killchain_create` for what you did, `finding_create` for weaknesses found, "
        "`credential_create`/`loot_upload` for anything captured, `ioc_create` for infrastructure "
        "or artifacts observed. If it's not in the vault, it didn't happen.\n"
        "- **Work the checklist.** Prefer claiming an existing todo (`todo_claim`) over freelancing; "
        "if the plan calls for work that isn't tracked yet, add it (`todo_create`) before starting "
        "so progress stays visible. `todo_complete` when done, `todo_handoff` if you have to stop "
        "mid-task.\n"
        f"- **Stay in scope.** Only act within engagement `{eid}`. If the threat model or objectives "
        "below are missing or thin, treat that as something to flag to the operator, not license to "
        "improvise scope."
    )
    lines.append("")

    lines.append("## Engagement context")
    lines.append("")
    lines.append(f"- **Client:** {engagement.client_name}")
    lines.append(f"- **Status:** {engagement.status}")
    if engagement.start_date or engagement.end_date:
        lines.append(
            f"- **Dates:** {engagement.start_date or '?'} → {engagement.end_date or 'open-ended'}"
        )
    if engagement.description:
        lines.append(f"- **Description:** {engagement.description}")
    lines.append("")

    if plan and not plan.is_empty():
        lines.append(_section("Adversary being emulated", html_to_markdown(plan.threat_model)))
        lines.append(_section("Planned attack path", html_to_markdown(plan.attack_plan)))
        lines.append(_section("Objectives (definition of success)", html_to_markdown(plan.objectives)))
    else:
        lines.append("## Threat model")
        lines.append("")
        lines.append(
            "_No threat model recorded yet._ Ask the operator for the adversary profile, planned "
            f"attack path, and objectives, or draft one yourself with `threat_model_save(engagement_id={eid}, ...)` "
            "once scope is clear — don't start acting against the target without one."
        )
        lines.append("")

    lines.append("## Checklist state")
    lines.append("")
    lines.append(f"**In progress ({len(in_progress)}):**")
    lines.append(_todo_lines(in_progress, "Nothing currently claimed."))
    lines.append("")
    lines.append(f"**Available ({len(available)}):**")
    lines.append(_todo_lines(available, "Nothing open and unclaimed."))
    lines.append("")
    lines.append(f"**Done:** {done_count} task(s) completed so far.")
    lines.append("")

    lines.append("## Current vault contents")
    lines.append("")
    lines.append("Quick snapshot so you don't duplicate work already logged:")
    lines.append("")
    for label, count in counts.items():
        lines.append(f"- {label}: {count}")
    lines.append("")

    if links:
        lines.append("## Reference links")
        lines.append("")
        for link in links:
            lines.append(f"- [{link.display_label()}]({link.url}) ({link.link_type_label()})")
        lines.append("")

    lines.append("## Suggested operating loop")
    lines.append("")
    lines.append(
        f"1. `engagement_get(engagement_id={eid})` and `todo_list(engagement_id={eid})` to refresh state.\n"
        "2. Claim an available todo that matches the objectives above (`todo_claim`), or create one "
        "for plan work that isn't tracked yet (`todo_create`).\n"
        "3. Execute it with the appropriate tool domain (see below).\n"
        "4. Log the outcome as it happens: kill chain entry for the action, finding for anything "
        "discovered, credential/loot for anything captured, IOC for infrastructure/artifacts observed.\n"
        "5. `todo_complete` the task (or `todo_handoff` with notes if you can't finish it now).\n"
        "6. Repeat until the checklist and objectives are satisfied, or you're blocked — then summarize "
        "status for the operator instead of going quiet."
    )
    lines.append("")

    lines.append("## MCP tool domains")
    lines.append("")
    lines.append("Full reference with every tool and its description is on the Help page in the app.")
    lines.append("")
    for domain, tools in TOOL_DOMAINS:
        lines.append(f"- **{domain}:** {tools}")
    lines.append("")

    lines.append("## One-time setup (skip if already done)")
    lines.append("")
    lines.append(
        "1. Get a `redops-vault` API key for the account this agent should act as (Admin → Users → "
        "create an `agent`-role user, or reuse an existing operator/admin account) from the API Keys page.\n"
        "2. Point your MCP client at `mcp_server/server.py` with `REDOPS_API_KEY` set — see the Help → "
        "MCP Server page for the exact `.mcp.json` snippet and run instructions.\n"
        "3. Paste this whole document into that agent's system prompt / project instructions file."
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"
