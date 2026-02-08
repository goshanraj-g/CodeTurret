# Security Policy

Rules enforced by CodeBouncer during automated scans.

## Blocked Patterns

| ID | Category | Rule |
|----|----------|------|
| SP-001 | Injection | No string concatenation or f-strings in SQL queries. Use parameterized queries. |
| SP-002 | Injection | No unsanitized user input passed to `subprocess`, `os.system`, or `eval`. |
| SP-003 | Secrets | No hardcoded API keys, tokens, passwords, or private keys in source code. |
| SP-004 | Auth | No plaintext password storage. Passwords must be hashed (bcrypt, argon2). |
| SP-005 | XSS | No unescaped user input rendered in HTML templates. |
| SP-006 | Path Traversal | No user-controlled values used directly in file system paths without validation. |
| SP-007 | Deserialization | No `pickle.loads`, `yaml.load` (without SafeLoader), or `eval` on untrusted data. |
| SP-008 | Config | No debug mode enabled in production configurations. |
| SP-009 | Config | No wildcard CORS (`*`) in production. |
| SP-010 | Crypto | No use of MD5 or SHA1 for password hashing or security-critical operations. |

## Severity Classification

- **CRITICAL**: Exploitable remotely with no authentication (RCE, SQLi with data exfil).
- **HIGH**: Exploitable with low-privilege access or requires minimal user interaction (stored XSS, auth bypass).
- **MEDIUM**: Requires specific conditions or higher-privilege access (CSRF, information disclosure).
- **LOW**: Best-practice violations unlikely to be directly exploitable (debug mode, verbose errors).
