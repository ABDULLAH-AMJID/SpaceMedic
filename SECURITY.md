# Security Policy

## Supported versions

Security fixes are provided for the latest public release on Windows 10/11 x64.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could enable arbitrary command execution, privilege escalation, unsafe deletion, path traversal, or sensitive-data exposure. Contact the repository owner privately through the security advisory feature.

Include the SpaceMedic version, Windows version, reproduction steps, affected path/action, and whether Administrator mode was used. Do not include credentials or private file contents.

## Security boundaries

- Scanning is read-only by default.
- Protected Windows paths fail closed.
- Cleanup uses Recycle Bin where supported.
- Registry differences are report-only; there is no generic Registry cleaner.
- Community rules cannot use absolute paths or parent traversal, and SYSTEM rules cannot enable direct cleanup.
- External tools are never downloaded automatically.
- Code signing is optional and only valid when the release owner provides a trusted certificate.
