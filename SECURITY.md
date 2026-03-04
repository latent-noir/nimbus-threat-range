# 🔐 Security Policy

> *"Security is not a product, but a process."* — Bruce Schneier

## Supported Versions

| Version | Status |
|---------|--------|
| 2.0.x   | ✅ Actively maintained |
| < 2.0   | ❌ End of life |

## ⚠️ Important Disclaimer

This project is an **educational cyber simulation platform**. It simulates attacks in a **controlled, local environment** for learning purposes. It is **not** designed for production deployment, penetration testing against real systems, or any unauthorized activity.

**Never expose the API endpoints to the public internet.**

## Reporting a Vulnerability

If you discover a security vulnerability, **do not open a public issue**.

### How to Report

1. Send a detailed private report via [GitHub Security Advisories](../../security/advisories/new) or contact the maintainer directly
2. Include:
   - Clear description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested mitigation (if any)

### Response SLA

| Stage | Timeline |
|-------|----------|
| Acknowledgment | 48 hours |
| Initial triage | 5 business days |
| Patch (critical) | 30 days |

## Security Architecture

| Component | Implementation |
|-----------|---------------|
| **CORS** | Restricted to `localhost:3000` and `localhost:8501` |
| **WebSocket** | Input validation — severity `[1-100]`, duration `[100-60000ms]` |
| **Firewall** | Configurable stateless rules (ALLOW / DENY / LOG) |
| **IDS** | 7+ detection rules with behavioral anomaly analysis |
| **Audit Trail** | All security events logged with timestamps |
| **Authentication** | None (by design — educational sandbox) |

## Hardening for Production

If adapting this for a production environment:

1. Implement JWT or API key authentication
2. Replace CORS wildcard with specific origins
3. Add rate limiting middleware
4. Enable TLS / HTTPS
5. Add WebSocket token authentication
6. Deploy behind a reverse proxy (nginx / Caddy)
7. Route logs to a SIEM (Splunk, ELK, Wazuh)

---

<p align="center"><sub>🔒 Responsible disclosure keeps the ecosystem safe.</sub></p>
