# Security Policy

## Supported versions

RedOps Vault doesn't cut versioned releases — only the code on `master`
is supported. Security fixes land there.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Use GitHub's private vulnerability reporting instead:
[github.com/devzspy/redops-vault/security/advisories/new](https://github.com/devzspy/redops-vault/security/advisories/new)
(also reachable from this repo's **Security** tab → **Report a
vulnerability**). This opens a private conversation with the maintainer
that isn't visible to the public until a fix is out.

Include what you'd include in any report: the affected version/commit,
steps to reproduce, and the impact as you understand it. There's no
bounty program — this is a small, largely solo-maintained project — but
reports are taken seriously and credited in the advisory unless you'd
rather stay anonymous.

## Scope notes

RedOps Vault is a self-hosted tool for tracking authorized red-team
engagements, built for a small trusted operator team, not a
multi-tenant SaaS. See the [Security notes](README.md#security-notes)
section of the README for known, intentional scope limitations (e.g. no
per-engagement access control between operators/admins) — those are
design tradeoffs, not vulnerabilities, but are worth reading before filing
a report about them.
