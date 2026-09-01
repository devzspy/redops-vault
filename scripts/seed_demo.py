"""Seeds one complete, realistic demo engagement for live product demos.

Tells a single coherent story — phishing -> credential theft -> lateral
movement -> domain compromise -> data exfiltration — touching every major
feature: targets/victims vs. attacker infrastructure (with network pathing
for each), encrypted loot, all three credential types plus a live TOTP code,
a kill chain timeline with ATT&CK mappings, correlated findings, IOCs, and
a shift-handoff todo checklist.

Only ever touches the single engagement it owns (matched by name) — never
touches other engagements or user accounts, and reuses whichever admin/
operator accounts already exist rather than creating new ones.

Usage:
    python scripts/seed_demo.py              # create (or recreate) the demo
    python scripts/seed_demo.py --teardown   # remove it
"""

import base64
import io
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

DEMO_ENGAGEMENT_NAME = "Meridian Financial Group \u2014 Red Team Assessment"


def _dt(days=0, hours=0, base=None):
    base = base or datetime.now(timezone.utc)
    return base + timedelta(days=days, hours=hours)


def main():
    teardown = "--teardown" in sys.argv
    app = create_app()
    with app.app_context():
        from app.models.engagement import Engagement

        existing = Engagement.query.filter_by(name=DEMO_ENGAGEMENT_NAME).first()
        if existing is not None:
            db.session.delete(existing)
            db.session.commit()
            print(f"Removed existing demo engagement (was id={existing.id}).")

        if teardown:
            print("Teardown complete.")
            return

        seed(app)


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
    from app.models.todo import STATUS_DONE, STATUS_OPEN, Todo
    from app.models.user import ROLE_ADMIN, User
    from app.services import activity_service, storage_service
    from app.services.sanitize_service import clean_html

    admin = User.query.filter_by(role=ROLE_ADMIN).order_by(User.id.asc()).first()
    if admin is None:
        print("No admin user exists yet — complete the initial setup wizard first.")
        sys.exit(1)
    operator = User.query.filter(User.id != admin.id).order_by(User.id.asc()).first() or admin

    start = _dt(days=-6)
    now_ref = datetime.now(timezone.utc)

    engagement = Engagement(
        name=DEMO_ENGAGEMENT_NAME,
        client_name="Meridian Financial Group",
        description=(
            "External + internal red team assessment. Scope: external perimeter "
            "(*.meridianfg.local, public web apps), phishing against the Finance "
            "and HR departments, and internal Active Directory once a foothold is "
            "established. Objective: test detection/response and reach Domain "
            "Admin + exfiltrate a sample of sensitive finance data without being "
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
        entry_actor_id = actor.id
        entry_actor_label = actor.username
        from app.models.activity import ActivityLogEntry

        db.session.add(
            ActivityLogEntry(
                engagement_id=eid,
                actor_id=entry_actor_id,
                actor_label=entry_actor_label,
                entity_type=entity_type,
                action=action,
                summary=summary,
                occurred_started_at=occurred,
                created_at=occurred,
            )
        )

    log("engagement", "created", f"Created engagement '{engagement.name}'", days=0)

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
        "phish.merid-security-updates.com", "domain", ROLE_REDIRECTOR, STATUS_HEALTHY,
        provider="DigitalOcean", notes="Domain-fronted phishing + malleable C2 redirector.", days=0,
    )
    team_server = infra_node(
        "203.0.113.45", "ip_address", ROLE_TEAM_SERVER, STATUS_HEALTHY,
        provider="DigitalOcean", notes="Mythic team server.", days=0,
    )
    db.session.add(InfrastructureService(node_id=team_server.id, name="Mythic", port=7443))
    c2_domain = infra_node(
        "cdn-assets.merid-security-updates.com", "domain", ROLE_C2, STATUS_HEALTHY,
        provider="CloudFront", notes="Fronting domain for long-haul beacon traffic.", days=1,
    )
    proxy = infra_node(
        "198.51.100.22", "ip_address", ROLE_PROXY, STATUS_HEALTHY,
        provider="Vultr", notes="SOCKS5 pivot for internal scanning through the beacon.", days=2,
    )
    burned_redirector = infra_node(
        "updates-secure-portal.com", "domain", ROLE_REDIRECTOR, STATUS_BURNED,
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

    dc01 = target_node("dc01.meridianfg.local", "hostname", ROLE_TARGET, STATUS_HEALTHY, notes="Primary domain controller.", days=3)
    db.session.add(InfrastructureService(node_id=dc01.id, name="SMB", port=445))
    db.session.add(InfrastructureService(node_id=dc01.id, name="LDAP", port=389))
    jump_host = target_node("10.20.30.15", "ip_address", ROLE_TARGET, STATUS_HEALTHY, notes="Internal jump host, origin for post-foothold scanning.", days=2)
    websrv = target_node("websrv01.meridianfg.local", "hostname", ROLE_TARGET, STATUS_ISOLATED, notes="Isolated by blue team after a WAF alert on day 4.", days=0)
    finance_ws = target_node("finance-ws07.meridianfg.local", "hostname", ROLE_VICTIM, STATUS_HEALTHY, notes="Phished finance analyst workstation.", days=1)
    fileserver = target_node("fileserver01.meridianfg.local", "file_share", ROLE_TARGET, STATUS_HEALTHY, notes="\\\\fileserver01\\Finance$")
    db.session.add(InfrastructureService(node_id=fileserver.id, name="SMB", port=445))
    wiki = target_node("wiki.meridianfg.local", "wiki", ROLE_TARGET, STATUS_HEALTHY, notes="Confluence — internal IT runbooks.")
    gitlab = target_node("gitlab.meridianfg.local", "source_control", ROLE_TARGET, STATUS_HEALTHY, notes="Internal GitLab, hosts deployment repos.")
    servicenow = target_node("servicenow.meridianfg.local", "ticketing", ROLE_TARGET, STATUS_HEALTHY, notes="ITSM portal.")
    s3_backups = target_node("s3://meridian-backups-prod", "cloud_storage", ROLE_TARGET, STATUS_HEALTHY, notes="Production backup bucket.")
    hr_db = target_node("hr-db01.meridianfg.local", "database", ROLE_TARGET, STATUS_DEAD, notes="Decommissioned mid-engagement; no longer reachable.")
    slack = target_node("meridianfg.slack.com", "collaboration", ROLE_VICTIM, STATUS_HEALTHY, notes="Accessed via a stolen browser session cookie.")
    backup01 = target_node("backup01.meridianfg.local", "backup_system", ROLE_TARGET, STATUS_ISOLATED, notes="Network-isolated after IR started on day 5.")

    def target_edge(src, dst, label, days=0):
        e = InfrastructureEdge(
            engagement_id=eid, source_node_id=src.id, target_node_id=dst.id,
            label=label, added_by_id=admin.id, added_at=_dt(days=days, base=start),
        )
        db.session.add(e)
        log("infrastructure_edge", "created", f"Added network path '{src.name}' \u2192 '{dst.name}'", days=days)

    target_edge(finance_ws, dc01, "Same AD domain, cached DA token", days=3)
    target_edge(dc01, fileserver, "SMB share access as Domain Admin", days=3)
    target_edge(dc01, hr_db, "SQL auth via service account", days=4)
    target_edge(gitlab, backup01, "CI/CD runner has backup service account creds", days=4)
    target_edge(finance_ws, slack, "Stolen browser session cookie", days=1)

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
        b"[Screenshot placeholder]\nSubject: Q3 Invoice Update Required\nFrom: billing-support@merid-security-updates.com\nTo: j.doe@meridianfg.local\n\nPlease review and re-authorize the attached invoice update macro.",
        CATEGORY_SCREENSHOT, "Phishing email delivered to the finance team.", "phishing,initial-access",
        finance_ws.name, days=1,
    )
    loot_mimikatz = upload_loot(
        "mimikatz_output_dc01.txt",
        b"mimikatz # sekurlsa::logonpasswords\n\nAuthentication Id : 0 ; 892314\nUser Name : Administrator\nDomain : MERIDIANFG\nNTLM : 8846f7eaee8fb117ad06bdd830b7586c\n",
        CATEGORY_DOCUMENT, "Mimikatz sekurlsa::logonpasswords output captured on dc01.", "credentials,mimikatz,privesc",
        dc01.name, days=4,
    )
    loot_nmap = upload_loot(
        "internal_nmap_scan.txt",
        b"Nmap scan report for 10.20.30.0/24\n22/tcp open ssh\n445/tcp open microsoft-ds\n3389/tcp open ms-wbt-server\n",
        CATEGORY_DOCUMENT, "Internal nmap sweep of 10.20.30.0/24 from the jump host.", "recon,nmap",
        jump_host.name, days=3,
    )
    loot_share_listing = upload_loot(
        "finance_share_listing.txt",
        b"\\\\fileserver01\\Finance$\\Payroll_2026.xlsx\n\\\\fileserver01\\Finance$\\Wire_Transfer_Approvals.docx\n\\\\fileserver01\\Finance$\\Board_Comp_Plan.pdf\n",
        CATEGORY_NOTE, "Directory listing of the Finance share showing sensitive spreadsheets.", "fileshare,sensitive-data",
        fileserver.name, days=4,
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
        credential_type=CRED_TYPE_PASSWORD, username="svc_backup", domain="MERIDIANFG",
        password_encrypted=crypto_service.encrypt_field("B4ckupSvc!2024"),
        source_host=dc01.name, status=CRED_STATUS_WORKING,
        access_description="Domain-joined service account; granted local admin on all workstations via GPO.",
        days=3,
    )
    cred_finance_user = credential(
        credential_type=CRED_TYPE_PASSWORD, username="j.doe@meridianfg.local",
        password_encrypted=crypto_service.encrypt_field("Summer2024!"),
        totp_secret_encrypted=crypto_service.encrypt_field(totp_secret),
        source_host=finance_ws.name, status=CRED_STATUS_WORKING,
        access_description="O365 mailbox + VPN access. MFA is TOTP-based — captured via a real-time phishing proxy.",
        days=1,
    )
    cred_da_hash = credential(
        credential_type=CRED_TYPE_PASSWORD, username="Administrator", domain="MERIDIANFG",
        hash_encrypted=crypto_service.encrypt_field("aad3b435b51404eeaad3b435b51404ee:8846f7eaee8fb117ad06bdd830b7586c"),
        source_host=dc01.name, status=CRED_STATUS_UNTESTED,
        access_description="Domain Administrator NTLM hash dumped via Mimikatz on dc01.",
        days=4,
    )
    cred_deploy_key = credential(
        credential_type=CRED_TYPE_API_KEY, username="prod-deploy-key",
        api_key_encrypted=crypto_service.encrypt_field("AKIAFAKEMERIDIAN123456"),
        source_host=s3_backups.name, status=CRED_STATUS_WORKING,
        access_description="AWS IAM key with read/write on the meridian-backups-prod S3 bucket.",
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
        source_host=hr_db.name, status=CRED_STATUS_NOT_WORKING,
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

    kc_recon = kc_entry(
        STAGE_RECONNAISSANCE, "OSINT gathering on Meridian employees",
        "Enumerated finance/HR staff via LinkedIn and breach-data lookups to build a phishing target list.",
        None, days=0, hours=9,
    )
    kc_weapon = kc_entry(
        STAGE_WEAPONIZATION, "Crafted phishing payload with malicious macro",
        "Built a macro-enabled 'invoice update' document that drops a stager on execution.",
        None, days=0, hours=15,
    )
    kc_delivery = kc_entry(
        STAGE_DELIVERY, "Sent phishing email to 40 finance employees",
        "Delivered via the domain-fronted redirector; 3 recipients opened the attachment.",
        redirector, days=1, hours=8, techniques=[t_phishing],
    )
    kc_exploit = kc_entry(
        STAGE_EXPLOITATION, "Macro executed, initial foothold on finance-ws07",
        "j.doe enabled macros; payload executed and called back to the C2 redirector.",
        finance_ws, days=1, hours=9, loot=[loot_phish_shot], techniques=[t_userexec],
    )
    kc_install = kc_entry(
        STAGE_INSTALLATION, "Beacon implant installed, persistence via scheduled task",
        "Registered a scheduled task to relaunch the beacon on logon.",
        finance_ws, days=1, hours=10, techniques=[t_schedtask],
    )
    kc_c2 = kc_entry(
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
        STAGE_ACTIONS_ON_OBJECTIVES, "Exfiltrated sensitive files from the Finance share",
        "Pulled payroll and wire-transfer-approval documents from \\\\fileserver01\\Finance$ over the C2 channel.",
        fileserver, days=4, hours=15, loot=[loot_share_listing], techniques=[t_localdata, t_exfil],
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
        "<p>A single phishing email led to full Domain Admin compromise within 72 hours. The finance "
        "workstation's cached credentials, combined with a shared local-admin service account password, "
        "allowed unrestricted lateral movement to the domain controller.</p>",
        "<p>Enforce LAPS for local admin passwords, enable Credential Guard, and deploy phishing-resistant "
        "MFA (FIDO2) for privileged and finance-team accounts.</p>",
        infra_nodes=[dc01, finance_ws], credentials=[cred_backup_svc, cred_da_hash],
        killchain_entries=[kc_exploit, kc_creddump], loot_files=[loot_mimikatz, loot_phish_shot],
        days=4,
    )
    finding(
        "Sensitive financial data exposed via open file share", SEVERITY_HIGH,
        "<p>The Finance$ share was readable by any domain-authenticated user, exposing payroll and "
        "wire-transfer-approval documents well beyond the finance team.</p>",
        "<p>Restrict the share to an explicit finance security group and enable file-access auditing.</p>",
        infra_nodes=[fileserver], loot_files=[loot_share_listing], killchain_entries=[kc_exfil],
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
        credentials=[cred_finance_user],
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
        finance_ws.name, r"C:\Users\jdoe\AppData\Local\Temp\invoice_update.docm",
        HASH_TYPE_SHA256, "3f786850e387550fdab836ed7e6dc881de23001b" + "a8b0ef2f6a5f1f3c9d0c8e1a2b3c4d5e",
        notes="Malicious macro dropper.", days=1,
    )
    ioc(
        dc01.name, r"C:\Windows\Temp\mimikatz.exe",
        HASH_TYPE_MD5, "5f4dcc3b5aa765d61d8327deb882cf99",
        notes="Staged for credential dumping.", days=4,
    )
    ioc(
        None, "hxxp://phish.merid-security-updates[.]com/beacon",
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
        notes="Focus on the HR and Finance OUs next.", days=4,
    )
    todo(
        "Draft phishing pretext and initial payload", STATUS_DONE, completed=True,
        notes="Used an 'invoice update' theme targeting Finance.", days=0,
    )
    todo(
        "Pick up overnight C2 monitoring", STATUS_OPEN,
        handoff_notes="Beacon on finance-ws07 checked in at 22:00, sleep is 60s. Watch for AV alerts — "
        "the isolated websrv01 host suggests blue team is actively hunting.",
        days=4,
    )

    db.session.commit()

    print(f"Seeded demo engagement '{DEMO_ENGAGEMENT_NAME}' (id={eid}).")
    print(f"Owner/actor: {admin.username}" + (f", secondary operator: {operator.username}" if operator is not admin else ""))
    print(f"View it at /engagements/{eid} once the app is running.")


if __name__ == "__main__":
    main()
