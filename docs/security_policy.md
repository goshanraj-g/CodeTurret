# CodeBouncer Security Policy

> Comprehensive security rules enforced during automated AI-powered scans.

---

## Vulnerability Detection Rules

### Injection Attacks

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-001 | CRITICAL | SQL Injection | String concatenation or f-strings in SQL queries |
| SP-002 | CRITICAL | Command Injection | Unsanitized input in `subprocess`, `os.system`, `eval` |
| SP-003 | CRITICAL | LDAP Injection | Unescaped input in LDAP queries |
| SP-004 | HIGH | NoSQL Injection | Unsanitized MongoDB/Redis query operators |
| SP-005 | HIGH | Template Injection | User input in Jinja2/Django template rendering |

### Authentication & Authorization

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-010 | CRITICAL | Broken Auth | Missing authentication on sensitive endpoints |
| SP-011 | CRITICAL | Privilege Escalation | Role checks bypassed via parameter manipulation |
| SP-012 | HIGH | Plaintext Passwords | Passwords stored without hashing |
| SP-013 | HIGH | Weak Hashing | MD5/SHA1 used for password storage |
| SP-014 | MEDIUM | Session Fixation | Session ID not regenerated after login |
| SP-015 | MEDIUM | Insufficient Expiry | JWT tokens with >24h expiry or no expiry |

### Secrets & Credentials

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-020 | CRITICAL | Hardcoded Secrets | API keys, tokens, passwords in source code |
| SP-021 | CRITICAL | Private Keys | RSA/EC private keys committed to repo |
| SP-022 | HIGH | Exposed .env | Environment files with secrets in public paths |
| SP-023 | MEDIUM | Secrets in Logs | Sensitive data written to log outputs |

### Cross-Site Scripting (XSS)

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-030 | HIGH | Reflected XSS | Unescaped query params rendered in HTML |
| SP-031 | HIGH | Stored XSS | Database content rendered without sanitization |
| SP-032 | MEDIUM | DOM XSS | `innerHTML`, `document.write` with user input |

### Insecure Deserialization

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-040 | CRITICAL | Pickle RCE | `pickle.loads` on untrusted data |
| SP-041 | CRITICAL | YAML RCE | `yaml.load` without `SafeLoader` |
| SP-042 | HIGH | JSON Prototype | Prototype pollution in JavaScript |

### File System & Path Traversal

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-050 | HIGH | Path Traversal | `../` sequences in file path construction |
| SP-051 | HIGH | Arbitrary File Read | User input in `open()`, `read_file()` |
| SP-052 | CRITICAL | Arbitrary File Write | User input controls file write destination |

### Cryptography

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-060 | CRITICAL | Weak Encryption | DES, RC4, or ECB mode usage |
| SP-061 | HIGH | Broken RNG | `random` module for security operations |
| SP-062 | MEDIUM | Insufficient Key Size | RSA < 2048 bits, AES < 128 bits |
| SP-063 | LOW | Missing Salt | Hashing without unique salt per entry |

### Configuration & Infrastructure

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-070 | HIGH | Debug Mode | `DEBUG=True` in production configs |
| SP-071 | MEDIUM | Permissive CORS | Wildcard `*` in CORS headers |
| SP-072 | MEDIUM | Missing CSP | No Content-Security-Policy header |
| SP-073 | LOW | Verbose Errors | Stack traces exposed to users |
| SP-074 | LOW | Missing Rate Limit | No rate limiting on auth endpoints |

### API Security

| ID | Severity | Rule | Detection Pattern |
|----|----------|------|-------------------|
| SP-080 | HIGH | Mass Assignment | Unfiltered request body bound to models |
| SP-081 | MEDIUM | BOLA/IDOR | Direct object references without ownership check |
| SP-082 | MEDIUM | Missing Input Validation | No schema validation on API inputs |
| SP-083 | LOW | Excessive Data Exposure | Sensitive fields in API responses |

---

## Severity Classification

| Level | Definition | Example |
|-------|------------|---------|
| **CRITICAL** | Remotely exploitable, no auth required | RCE, SQLi with data exfil, auth bypass |
| **HIGH** | Exploitable with low privilege or user interaction | Stored XSS, privilege escalation |
| **MEDIUM** | Requires specific conditions or higher privilege | CSRF, info disclosure, IDOR |
| **LOW** | Best-practice violations, unlikely to be directly exploitable | Debug mode, verbose errors |

---

## Compliance Mappings

| Framework | Covered Rules |
|-----------|---------------|
| **OWASP Top 10 2021** | A01-A10 fully covered |
| **CWE Top 25** | 23 of 25 most dangerous weaknesses |
| **SANS Top 25** | Complete coverage |
| **PCI DSS 4.0** | Req 6.2 (Secure development) |
| **SOC 2 Type II** | CC6.1, CC6.6, CC6.7 |

---

## Scan Behavior

- **Triage Pass**: Gemini Flash scans all files, flags potential issues
- **Deep Analysis**: Gemini Pro analyzes HIGH/CRITICAL findings for confirmation
- **False Positive Reduction**: AI validates context before reporting
- **Fix Suggestions**: Auto-generated remediation code when applicable

---

*Last updated: February 2026*
