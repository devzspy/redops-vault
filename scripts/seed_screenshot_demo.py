"""Seeds a complete, realistic demo engagement owned entirely by dedicated
screenshot accounts, for use in README/marketing screenshots.

Unlike seed_demo.py (which reuses whichever admin/operator accounts already
exist on the instance), this script creates and uses two dedicated accounts
-- `__shot__` (admin) and `__shot_operator__` (operator) -- for every single
record, so no real operator's username ever appears in a screenshot.

Tells a single coherent story -- phishing -> credential theft -> lateral
movement -> domain compromise -> data exfiltration -- touching every major
feature: targets/victims vs. attacker infrastructure (with network pathing
for each), a threat model, encrypted loot, all three credential types plus
a live TOTP code, a kill chain timeline with ATT&CK mappings, correlated
findings, IOCs, and a shift-handoff todo checklist.

Only ever touches the single engagement it owns (matched by name) and the
two accounts it owns (matched by username) -- never touches other
engagements or user accounts.

Usage:
    python scripts/seed_screenshot_demo.py              # create (or recreate)
    python scripts/seed_screenshot_demo.py --teardown   # remove engagement + accounts
"""

import base64
import io
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

DEMO_ENGAGEMENT_NAME = "Solstice Health Partners \u2014 Red Team Assessment"
SHOT_ADMIN_USERNAME = "__shot__"
SHOT_OPERATOR_USERNAME = "__shot_operator__"
SHOT_PASSWORD = "ShotPass123!"


def _dt(days=0, hours=0, base=None):
    base = base or datetime.now(timezone.utc)
    return base + timedelta(days=days, hours=hours)


def main():
    teardown = "--teardown" in sys.argv
    app = create_app()
    with app.app_context():
        from app.models.engagement import Engagement
        from app.models.user import User

        existing = Engagement.query.filter_by(name=DEMO_ENGAGEMENT_NAME).first()
        if existing is not None:
            db.session.delete(existing)
            db.session.commit()
            print(f"Removed existing demo engagement (was id={existing.id}).")

        if teardown:
            for username in (SHOT_ADMIN_USERNAME, SHOT_OPERATOR_USERNAME):
                u = User.query.filter_by(username=username).first()
                if u is not None:
                    db.session.delete(u)
            db.session.commit()
            print("Teardown complete.")
            return

        seed(app)


def _get_or_create_user(username, role):
    from argon2 import PasswordHasher

    from app.models.user import User

    user = User.query.filter_by(username=username).first()
    if user is None:
        ph = PasswordHasher()
        user = User(username=username, password_hash=ph.hash(SHOT_PASSWORD), role=role)
        db.session.add(user)
        db.session.flush()
    return user


def seed(app):
    from app.models.attack import AttackTechnique
    from app.models.engagement import STATUS_ACTIVE, Engagement
    from app.models.finding import SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_INFORMATIONAL, SEVERITY_LOW, SEVERITY_MEDIUM, Finding
    from app.models.infrastructure import (
        ROLE_C2,
        ROLE_PROXY,
        ROLE_REDIRECTOR,
        ROLE_TARGET,
        ROLE_TEAM_SERVER,
        ROLE_VICTIM,
        STATUS_BURNED,
        STATUS_DEAD,
        STATUS_HEALTHY,
        STATUS_ISOLATED,
        InfrastructureEdge,
        InfrastructureNode,
        InfrastructureService,
    )
    from app.models.ioc import HASH_TYPE_MD5, HASH_TYPE_SHA256, IOC
    from app.models.killchain import (
        STAGE_ACTIONS_ON_OBJECTIVES,
        STAGE_COMMAND_AND_CONTROL,
        STAGE_DELIVERY,
        STAGE_EXPLOITATION,
        STAGE_INSTALLATION,
        STAGE_RECONNAISSANCE,
        STAGE_WEAPONIZATION,
        KillChainEntry,
        TechniqueMapping,
    )
    from app.models.loot import (
        CATEGORY_DOCUMENT,
        CATEGORY_NOTE,
        CATEGORY_PCAP,
        CATEGORY_SCREENSHOT,
        CRED_STATUS_NOT_WORKING,
        CRED_STATUS_UNTESTED,
        CRED_STATUS_WORKING,
        CRED_TYPE_API_KEY,
        CRED_TYPE_PASSWORD,
        CRED_TYPE_SSH_KEY,
        Credential,
        LootFile,
    )
    from app.models.threat_model import ThreatModel
    from app.models.todo import STATUS_DONE, STATUS_OPEN, Todo
    from app.models.user import ROLE_ADMIN, ROLE_OPERATOR
    from app.services import storage_service
    from app.services.sanitize_service import clean_html

    admin = _get_or_create_user(SHOT_ADMIN_USERNAME, ROLE_ADMIN)
    operator = _get_or_create_user(SHOT_OPERATOR_USERNAME, ROLE_OPERATOR)

    start = _dt(days=-6)

    engagement = Engagement(
        name=DEMO_ENGAGEMENT_NAME,
        client_name="Solstice Health Partners",
        description=(
            "External + internal red team assessment. Scope: external perimeter "
            "(*.solsticehealth.local, public patient portal), phishing against the "
            "Billing and Records departments, and internal Active Directory once a "
            "foothold is established. Objective: test detection/response and reach "
            "Domain Admin + exfiltrate a sample of patient records without being "
            "fully contained."
        ),
        start_date=start.date(),
        end_date=(start + timedelta(days=10)).date(),
        status=STATUS_ACTIVE,
        created_by_id=admin.id,
        created_at=start,
    )
    db.session.add(engagement)
    db.session.flush()
    eid = engagement.id

    def log(entity_type, action, summary, days=0, hours=0, actor=None):
        actor = actor or admin
        occurred = _dt(days=days, hours=hours, base=start)
        from app.models.activity import ActivityLogEntry

        db.session.add(
            ActivityLogEntry(
                engagement_id=eid,
                actor_id=actor.id,
                actor_label=actor.username,
                entity_type=entity_type,
                action=action,
                summary=summary,
                occurred_started_at=occurred,
                created_at=occurred,
            )
        )

    log("engagement", "created", f"Created engagement '{engagement.name}'", days=0)

    # ------------------------------------------------------------ Threat model
    db.session.add(
        ThreatModel(
            engagement_id=eid,
            threat_model=clean_html(
                "<p>Emulating a financially-motivated ransomware affiliate targeting "
                "healthcare providers for double-extortion: steal patient records and "
                "billing data before deploying ransomware, betting the client pays to "
                "avoid a HIPAA breach disclosure.</p>"
            ),
            attack_plan=clean_html(
                "<p>Phish the Billing department with an insurance-claim-update lure to "
                "get a foothold, dump credentials and pivot to the domain controller, "
                "then stage and exfiltrate patient records from the shared drive before "
                "the engagement window closes.</p>"
            ),
            objectives=clean_html(
                "<ul><li>Achieve Domain Admin on solsticehealth.local</li>"
                "<li>Exfiltrate a representative sample of patient records without full "
                "containment</li><li>Evaluate whether MFA-fatigue or credential replay "
                "would have worked against the VPN portal</li></ul>"
            ),
            updated_by_id=admin.id,
            updated_at=_dt(days=1, base=start),
        )
    )
    log("threat_model", "updated", "Saved threat model and attack plan", days=1)

    # ---------------------------------------------------------------- ATT&CK
    if AttackTechnique.query.count() == 0:
        try:
            from app.services import attack_sync

            summary = attack_sync.fetch_and_sync()
            db.session.commit()
            print(f"Synced live MITRE ATT&CK data: {summary}")
        except Exception as exc:  # noqa: BLE001 - best-effort, offline-safe fallback below
            print(f"Could not sync live ATT&CK data ({exc}); seeding a few stub techniques instead.")

    def technique(attack_id, name, description):
        t = AttackTechnique.query.filter_by(attack_id=attack_id).first()
        if t is None:
            t = AttackTechnique(attack_id=attack_id, name=name, description=description)
            db.session.add(t)
            db.session.flush()
        return t

    t_phishing = technique("T1566", "Phishing", "Sending malicious content to a victim to gain initial access.")
    t_userexec = technique("T1204", "User Execution", "A user executes malicious code, e.g. opening a macro attachment.")
    t_schedtask = technique("T1053", "Scheduled Task/Job", "Abusing task scheduling for execution and persistence.")
    t_creddump = technique("T1003", "OS Credential Dumping", "Dumping credentials from OS storage, e.g. LSASS memory.")
    t_remsvc = technique("T1021", "Remote Services", "Using valid credentials to log into a remote service for lateral movement.")
    t_localdata = technique("T1005", "Data from Local System", "Searching local system sources for data to exfiltrate.")
    t_exfil = technique("T1041", "Exfiltration Over C2 Channel", "Exfiltrating data over an existing C2 channel.")

    # ---------------------------------------------------- Attacker infrastructure
    def infra_node(name, node_type, role, status, provider=None, region=None, notes=None, days=0):
        n = InfrastructureNode(
            engagement_id=eid,
            node_type=node_type,
            name=name,
            role=role,
            status=status,
            provider=provider,
            region=region,
            notes=notes,
            added_by_id=admin.id,
            added_at=_dt(days=days, base=start),
        )
        db.session.add(n)
        db.session.flush()
        log("infrastructure_node", "created", f"Added infrastructure node '{name}'", days=days)
        return n

    redirector = infra_node(
        "portal.solstice-claims-update.com", "domain", ROLE_REDIRECTOR, STATUS_HEALTHY,
        provider="DigitalOcean", notes="Domain-fronted phishing + malleable C2 redirector.", days=0,
    )
    team_server = infra_node(
        "203.0.113.77", "ip_address", ROLE_TEAM_SERVER, STATUS_HEALTHY,
        provider="DigitalOcean", notes="Mythic team server.", days=0,
    )
    db.session.add(InfrastructureService(node_id=team_server.id, name="Mythic", port=7443))
    c2_domain = infra_node(
        "cdn-static.solstice-claims-update.com", "domain", ROLE_C2, STATUS_HEALTHY,
        provider="CloudFront", notes="Fronting domain for long-haul beacon traffic.", days=1,
    )
    proxy = infra_node(
        "198.51.100.64", "ip_address", ROLE_PROXY, STATUS_HEALTHY,
        provider="Vultr", notes="SOCKS5 pivot for internal scanning through the beacon.", days=2,
    )
    burned_redirector = infra_node(
        "claims-secure-update.com", "domain", ROLE_REDIRECTOR, STATUS_BURNED,
        provider="DigitalOcean", notes="Blocked by client's web proxy on day 2 — no longer usable.", days=0,
    )

    def infra_edge(src, dst, label, days=0):
        e = InfrastructureEdge(
            engagement_id=eid, source_node_id=src.id, target_node_id=dst.id,
            label=label, added_by_id=admin.id, added_at=_dt(days=days, base=start),
        )
        db.session.add(e)
        log("infrastructure_edge", "created", f"Added network path '{src.name}' \u2192 '{dst.name}'", days=days)

    infra_edge(redirector, team_server, "HTTPS/443 malleable C2 redirect", days=0)
    infra_edge(c2_domain, team_server, "HTTPS/443 long-haul beacon", days=1)
    infra_edge(team_server, proxy, "SOCKS5 pivot for internal scanning", days=2)
    infra_edge(burned_redirector, team_server, "HTTPS/443 (burned day 2)", days=0)

    # -------------------------------------------------------- Targets & victims
    def target_node(name, node_type, role, status, notes=None, days=0):
        n = InfrastructureNode(
            engagement_id=eid, node_type=node_type, name=name, role=role, status=status,
            notes=notes, added_by_id=admin.id, added_at=_dt(days=days, base=start),
        )
        db.session.add(n)
        db.session.flush()
        log("infrastructure_node", "created", f"Added target/victim '{name}'", days=days)
        return n

    dc01 = target_node("dc01.solsticehealth.local", "hostname", ROLE_TARGET, STATUS_HEALTHY, notes="Primary domain controller.", days=3)
    db.session.add(InfrastructureService(node_id=dc01.id, name="SMB", port=445))
    db.session.add(InfrastructureService(node_id=dc01.id, name="LDAP", port=389))
    jump_host = target_node("10.40.12.9", "ip_address", ROLE_TARGET, STATUS_HEALTHY, notes="Internal jump host, origin for post-foothold scanning.", days=2)
    portal_srv = target_node("portalsrv01.solsticehealth.local", "hostname", ROLE_TARGET, STATUS_ISOLATED, notes="Isolated by blue team after a WAF alert on day 4.", days=0)
    billing_ws = target_node("billing-ws04.solsticehealth.local", "hostname", ROLE_VICTIM, STATUS_HEALTHY, notes="Phished billing analyst workstation.", days=1)
    recordserver = target_node("recordserver01.solsticehealth.local", "file_share", ROLE_TARGET, STATUS_HEALTHY, notes="\\\\recordserver01\\PatientRecords$")
    db.session.add(InfrastructureService(node_id=recordserver.id, name="SMB", port=445))
    wiki = target_node("wiki.solsticehealth.local", "wiki", ROLE_TARGET, STATUS_HEALTHY, notes="Confluence — internal IT runbooks.")
    gitlab = target_node("gitlab.solsticehealth.local", "source_control", ROLE_TARGET, STATUS_HEALTHY, notes="Internal GitLab, hosts deployment repos.")
    servicenow = target_node("servicenow.solsticehealth.local", "ticketing", ROLE_TARGET, STATUS_HEALTHY, notes="ITSM portal.")
    s3_backups = target_node("s3://solstice-backups-prod", "cloud_storage", ROLE_TARGET, STATUS_HEALTHY, notes="Production backup bucket.")
    ehr_db = target_node("ehr-db01.solsticehealth.local", "database", ROLE_TARGET, STATUS_DEAD, notes="Decommissioned mid-engagement; no longer reachable.")
    slack = target_node("solsticehealth.slack.com", "collaboration", ROLE_VICTIM, STATUS_HEALTHY, notes="Accessed via a stolen browser session cookie.")
    backup01 = target_node("backup01.solsticehealth.local", "backup_system", ROLE_TARGET, STATUS_ISOLATED, notes="Network-isolated after IR started on day 5.")

    def target_edge(src, dst, label, days=0):
        e = InfrastructureEdge(
            engagement_id=eid, source_node_id=src.id, target_node_id=dst.id,
            label=label, added_by_id=admin.id, added_at=_dt(days=days, base=start),
        )
        db.session.add(e)
        log("infrastructure_edge", "created", f"Added network path '{src.name}' \u2192 '{dst.name}'", days=days)

    target_edge(billing_ws, dc01, "Same AD domain, cached DA token", days=3)
    target_edge(dc01, recordserver, "SMB share access as Domain Admin", days=3)
    target_edge(dc01, ehr_db, "SQL auth via service account", days=4)
    target_edge(gitlab, backup01, "CI/CD runner has backup service account creds", days=4)
    target_edge(billing_ws, slack, "Stolen browser session cookie", days=1)

    # ------------------------------------------------------------------- Loot
    def upload_loot(filename, content, category, description, tags, host, days=0):
        field_updates, size, sha256_hex = storage_service.save_upload(io.BytesIO(content))
        f = LootFile(
            engagement_id=eid, original_filename=filename, category=category,
            description=description, tags=tags, associated_host=host, file_size_bytes=size,
            content_type="text/plain", sha256_plaintext=sha256_hex, uploaded_by_id=admin.id,
            uploaded_at=_dt(days=days, base=start),
            **field_updates,
        )
        db.session.add(f)
        db.session.flush()
        log("loot_file", "created", f"Uploaded loot file '{filename}'", days=days)
        return f

    loot_phish_shot = upload_loot(
        "phishing_email_screenshot.txt",
        b"[Screenshot placeholder]\nSubject: Insurance Claim Update Required\nFrom: claims-support@solstice-claims-update.com\nTo: r.patel@solsticehealth.local\n\nPlease review and re-authorize the attached claim adjustment macro.",
        CATEGORY_SCREENSHOT, "Phishing email delivered to the billing team.", "phishing,initial-access",
        billing_ws.name, days=1,
    )
    loot_mimikatz = upload_loot(
        "mimikatz_output_dc01.txt",
        b"mimikatz # sekurlsa::logonpasswords\n\nAuthentication Id : 0 ; 771205\nUser Name : Administrator\nDomain : SOLSTICEHEALTH\nNTLM : 5f4dcc3b5aa765d61d8327deb882cf99\n",
        CATEGORY_DOCUMENT, "Mimikatz sekurlsa::logonpasswords output captured on dc01.", "credentials,mimikatz,privesc",
        dc01.name, days=4,
    )
    loot_nmap = upload_loot(
        "internal_nmap_scan.txt",
        b"Nmap scan report for 10.40.12.0/24\n22/tcp open ssh\n445/tcp open microsoft-ds\n3389/tcp open ms-wbt-server\n",
        CATEGORY_DOCUMENT, "Internal nmap sweep of 10.40.12.0/24 from the jump host.", "recon,nmap",
        jump_host.name, days=3,
    )
    loot_share_listing = upload_loot(
        "patient_records_share_listing.txt",
        b"\\\\recordserver01\\PatientRecords$\\Q3_Claims_Export.xlsx\n\\\\recordserver01\\PatientRecords$\\Intake_Forms_2026.pdf\n\\\\recordserver01\\PatientRecords$\\Provider_Billing_Codes.csv\n",
        CATEGORY_NOTE, "Directory listing of the patient records share showing sensitive PHI/billing files.", "fileshare,sensitive-data",
        recordserver.name, days=4,
    )
    loot_pcap = upload_loot(
        "llmnr_poisoning_capture.pcap",
        b"[pcap placeholder bytes]\nLLMNR/NBT-NS poisoning capture via Responder, 20 min window.",
        CATEGORY_PCAP, "Captured LLMNR/NBT-NS poisoning traffic while pivoting through the jump host.", "responder,pcap",
        jump_host.name, days=3,
    )

    # ------------------------------------------------------------- Credentials
    def credential(**kwargs):
        days = kwargs.pop("days", 0)
        c = Credential(engagement_id=eid, added_by_id=admin.id, added_at=_dt(days=days, base=start), **kwargs)
        db.session.add(c)
        db.session.flush()
        log("credential", "created", f"Added credential '{c.username or '(no username)'}'", days=days)
        return c

    from app.services import crypto_service

    totp_secret = base64.b32encode(os.urandom(10)).decode()

    cred_backup_svc = credential(
        credential_type=CRED_TYPE_PASSWORD, username="svc_backup", domain="SOLSTICEHEALTH",
        password_encrypted=crypto_service.encrypt_field("B4ckupSvc!2024"),
        source_host=dc01.name, status=CRED_STATUS_WORKING,
        access_description="Domain-joined service account; granted local admin on all workstations via GPO.",
        days=3,
    )
    cred_billing_user = credential(
        credential_type=CRED_TYPE_PASSWORD, username="r.patel@solsticehealth.local",
        password_encrypted=crypto_service.encrypt_field("Summer2024!"),
        totp_secret_encrypted=crypto_service.encrypt_field(totp_secret),
        source_host=billing_ws.name, status=CRED_STATUS_WORKING,
        access_description="O365 mailbox + VPN access. MFA is TOTP-based — captured via a real-time phishing proxy.",
        days=1,
    )
    cred_da_hash = credential(
        credential_type=CRED_TYPE_PASSWORD, username="Administrator", domain="SOLSTICEHEALTH",
        hash_encrypted=crypto_service.encrypt_field("aad3b435b51404eeaad3b435b51404ee:5f4dcc3b5aa765d61d8327deb882cf99"),
        source_host=dc01.name, status=CRED_STATUS_UNTESTED,
        access_description="Domain Administrator NTLM hash dumped via Mimikatz on dc01.",
        days=4,
    )
    cred_deploy_key = credential(
        credential_type=CRED_TYPE_API_KEY, username="prod-deploy-key",
        api_key_encrypted=crypto_service.encrypt_field("AKIAFAKESOLSTICE123456"),
        source_host=s3_backups.name, status=CRED_STATUS_WORKING,
        access_description="AWS IAM key with read/write on the solstice-backups-prod S3 bucket.",
        days=4,
    )
    cred_git_deploy = credential(
        credential_type=CRED_TYPE_SSH_KEY, username="git-ci",
        ssh_private_key_encrypted=crypto_service.encrypt_field(
            "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAA...\n-----END OPENSSH PRIVATE KEY-----"
        ),
        source_host=gitlab.name, status=CRED_STATUS_WORKING,
        access_description="GitLab deploy key with write access to all internal repositories.",
        days=4,
    )
    credential(
        credential_type=CRED_TYPE_PASSWORD, username="svc_sql",
        password_encrypted=crypto_service.encrypt_field("OldPassword1"),
        source_host=ehr_db.name, status=CRED_STATUS_NOT_WORKING,
        access_description="Attempted SQL service account access — password had already been rotated.",
        days=4,
    )

    # ------------------------------------------------------------- Kill chain
    def kc_entry(stage, title, description, host_node, days, hours=0, loot=None, techniques=None):
        e = KillChainEntry(
            engagement_id=eid, stage=stage, title=title, description=description,
            host=host_node.name if host_node else None,
            infra_node_id=host_node.id if host_node else None,
            occurred_at=_dt(days=days, hours=hours, base=start),
            created_by_id=admin.id, created_at=_dt(days=days, hours=hours, base=start),
        )
        db.session.add(e)
        if loot:
            e.loot_files = loot
        db.session.flush()
        log("killchain_entry", "created", f"Added kill chain entry '{title}' ({e.stage_label()})", days=days, hours=hours)
        for t in techniques or []:
            db.session.add(TechniqueMapping(engagement_id=eid, technique_id=t.id, killchain_entry_id=e.id, mapped_by_id=admin.id))
        return e

    kc_entry(
        STAGE_RECONNAISSANCE, "OSINT gathering on Solstice employees",
        "Enumerated billing/records staff via LinkedIn and breach-data lookups to build a phishing target list.",
        None, days=0, hours=9,
    )
    kc_entry(
        STAGE_WEAPONIZATION, "Crafted phishing payload with malicious macro",
        "Built a macro-enabled 'claim adjustment' document that drops a stager on execution.",
        None, days=0, hours=15,
    )
    kc_entry(
        STAGE_DELIVERY, "Sent phishing email to 35 billing employees",
        "Delivered via the domain-fronted redirector; 4 recipients opened the attachment.",
        redirector, days=1, hours=8, techniques=[t_phishing],
    )
    kc_exploit = kc_entry(
        STAGE_EXPLOITATION, "Macro executed, initial foothold on billing-ws04",
        "r.patel enabled macros; payload executed and called back to the C2 redirector.",
        billing_ws, days=1, hours=9, loot=[loot_phish_shot], techniques=[t_userexec],
    )
    kc_entry(
        STAGE_INSTALLATION, "Beacon implant installed, persistence via scheduled task",
        "Registered a scheduled task to relaunch the beacon on logon.",
        billing_ws, days=1, hours=10, techniques=[t_schedtask],
    )
    kc_entry(
        STAGE_COMMAND_AND_CONTROL, "C2 channel established over HTTPS",
        "Malleable HTTPS profile through the redirector to the Mythic team server.",
        team_server, days=1, hours=11,
    )
    kc_creddump = kc_entry(
        STAGE_ACTIONS_ON_OBJECTIVES, "Dumped credentials via Mimikatz on dc01",
        "Pivoted to dc01 using the cached DA token, then ran Mimikatz to harvest hashes.",
        dc01, days=4, hours=13, loot=[loot_mimikatz], techniques=[t_creddump, t_remsvc],
    )
    kc_exfil = kc_entry(
        STAGE_ACTIONS_ON_OBJECTIVES, "Exfiltrated patient records from the records share",
        "Pulled claims and intake documents from \\\\recordserver01\\PatientRecords$ over the C2 channel.",
        recordserver, days=4, hours=15, loot=[loot_share_listing], techniques=[t_localdata, t_exfil],
    )

    # --------------------------------------------------------------- Findings
    def finding(title, severity, details, remediation, infra_nodes=None, credentials=None, iocs=None, killchain_entries=None, loot_files=None, days=0):
        f = Finding(
            engagement_id=eid, title=title, severity=severity,
            details=clean_html(details), remediation=clean_html(remediation),
            created_by_id=admin.id, created_at=_dt(days=days, base=start),
        )
        db.session.add(f)
        f.infra_nodes = infra_nodes or []
        f.credentials = credentials or []
        f.iocs = iocs or []
        f.killchain_entries = killchain_entries or []
        f.loot_files = loot_files or []
        db.session.flush()
        log("finding", "created", f"Added finding '{f.title}' ({f.severity_label()})", days=days)
        return f

    finding(
        "Domain Admin compromise via phishing and credential theft", SEVERITY_CRITICAL,
        "<p>A single phishing email led to full Domain Admin compromise within 72 hours. The billing "
        "workstation's cached credentials, combined with a shared local-admin service account password, "
        "allowed unrestricted lateral movement to the domain controller.</p>",
        "<p>Enforce LAPS for local admin passwords, enable Credential Guard, and deploy phishing-resistant "
        "MFA (FIDO2) for privileged and billing-team accounts.</p>",
        infra_nodes=[dc01, billing_ws], credentials=[cred_backup_svc, cred_da_hash],
        killchain_entries=[kc_exploit, kc_creddump], loot_files=[loot_mimikatz, loot_phish_shot],
        days=4,
    )
    finding(
        "Sensitive patient data exposed via open file share", SEVERITY_HIGH,
        "<p>The PatientRecords$ share was readable by any domain-authenticated user, exposing claims and "
        "intake documents well beyond the billing/records team — a reportable HIPAA exposure.</p>",
        "<p>Restrict the share to an explicit records security group and enable file-access auditing.</p>",
        infra_nodes=[recordserver], loot_files=[loot_share_listing], killchain_entries=[kc_exfil],
        days=4,
    )
    finding(
        "Weak, reused service account password", SEVERITY_MEDIUM,
        "<p>The svc_backup account's password was guessable and reused across every workstation's local "
        "admin group via GPO, turning a single credential into domain-wide lateral movement.</p>",
        "<p>Rotate to a randomized, per-host LAPS-managed password and remove the account from the "
        "domain-wide local admin GPO.</p>",
        credentials=[cred_backup_svc],
        days=4,
    )
    finding(
        "Verbose internal scanning possible due to flat network segmentation", SEVERITY_LOW,
        "<p>Once on the internal network, nmap sweeps of the workstation subnet completed without any "
        "IDS/segmentation friction.</p>",
        "<p>Segment workstation, server, and management VLANs, and alert on internal port-scan patterns.</p>",
        infra_nodes=[jump_host], loot_files=[loot_nmap],
        days=3,
    )
    finding(
        "TOTP prompts did not throttle repeated MFA requests", SEVERITY_INFORMATIONAL,
        "<p>The VPN portal allowed unlimited TOTP attempts in quick succession, which would have enabled "
        "an MFA-fatigue attack had the code not been captured directly via the phishing proxy.</p>",
        "<p>Rate-limit and alert on repeated MFA challenges for the same account.</p>",
        credentials=[cred_billing_user],
        days=1,
    )

    # ------------------------------------------------------------------ IOCs
    def ioc(host, location, hash_type=None, hash_value=None, notes=None, days=0):
        i = IOC(
            engagement_id=eid, host=host, location=location, hash_type=hash_type, hash_value=hash_value,
            notes=notes, dropped_at=_dt(days=days, base=start), added_by_id=admin.id, added_at=_dt(days=days, base=start),
        )
        db.session.add(i)
        log("ioc", "created", f"Added IOC '{i.display_label()}'", days=days)
        return i

    ioc(
        billing_ws.name, r"C:\Users\rpatel\AppData\Local\Temp\claim_adjustment.docm",
        HASH_TYPE_SHA256, "3f786850e387550fdab836ed7e6dc881de23001b" + "a8b0ef2f6a5f1f3c9d0c8e1a2b3c4d5e",
        notes="Malicious macro dropper.", days=1,
    )
    ioc(
        dc01.name, r"C:\Windows\Temp\mimikatz.exe",
        HASH_TYPE_MD5, "5f4dcc3b5aa765d61d8327deb882cf99",
        notes="Staged for credential dumping.", days=4,
    )
    ioc(
        None, "hxxp://portal.solstice-claims-update[.]com/beacon",
        notes="C2 check-in URI observed in proxy logs.", days=1,
    )

    # ----------------------------------------------------------------- Todos
    def todo(title, status, assignee=None, notes=None, handoff_notes=None, completed=False, days=0):
        t = Todo(
            engagement_id=eid, title=title, status=status, notes=notes, handoff_notes=handoff_notes,
            assignee_id=assignee.id if assignee else None, created_by_id=admin.id, created_at=_dt(days=days, base=start),
        )
        if completed:
            t.completed_at = _dt(days=days, hours=4, base=start)
            t.completed_by_id = admin.id
        db.session.add(t)
        log("todo", "created", f"Added task '{title}'", days=days)
        return t

    todo("Confirm scope sign-off for internal segment with client POC", STATUS_OPEN, days=0)
    todo(
        "Continue lateral movement mapping from dc01", STATUS_OPEN, assignee=operator,
        notes="Focus on the Billing and Records OUs next.", days=4,
    )
    todo(
        "Draft phishing pretext and initial payload", STATUS_DONE, completed=True,
        notes="Used a 'claim adjustment' theme targeting Billing.", days=0,
    )
    todo(
        "Pick up overnight C2 monitoring", STATUS_OPEN,
        handoff_notes="Beacon on billing-ws04 checked in at 22:00, sleep is 60s. Watch for AV alerts — "
        "the isolated portalsrv01 host suggests blue team is actively hunting.",
        days=4,
    )

    db.session.commit()

    print(f"Seeded demo engagement '{DEMO_ENGAGEMENT_NAME}' (id={eid}).")
    print(f"Owner/actor: {admin.username}, secondary operator: {operator.username}")
    print(f"Log in as '{admin.username}' with password '{SHOT_PASSWORD}' to take screenshots.")
    print(f"View it at /engagements/{eid} once the app is running.")


if __name__ == "__main__":
    main()
