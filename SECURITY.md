# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability within GolfCal2, please follow these steps:

1. **Do Not** disclose the vulnerability publicly until it has been addressed.
2. Email the details to jarkkoa@iki.fi with:
   - Subject line: "GolfCal2 Security Vulnerability"
   - Description of the vulnerability
   - Steps to reproduce (if possible)
   - Potential impact
   - Any suggested fixes (if you have them)

You should receive a response within 48 hours. If not, please follow up.

## Security Measures

GolfCal2 implements several security measures:

1. **API Key Protection**
   - API keys are never stored in code
   - Keys are loaded from environment variables or secure configuration files
   - Configuration files with sensitive data are excluded from version control

2. **File Permissions**
   - Service runs with minimal required permissions
   - Configuration directories use restrictive permissions
   - ICS files are created with user-only access

3. **Authentication**
   - Secure storage of authentication tokens
   - Support for multiple authentication methods
   - Token refresh handling

4. **Data Protection**
   - Sensitive data masking in logs
   - No storage of plain-text credentials
   - Secure handling of session data

## Development Security Practices

1. **Dependency Management**
   - Regular dependency updates
   - Automated vulnerability scanning
   - Version pinning for stability

2. **Code Security**
   - Type checking with mypy
   - Automated testing
   - Code review requirements
   - Security-focused linting rules

3. **CI/CD Security**
   - Automated security scanning
   - Dependency vulnerability checks
   - Secure secret handling in CI/CD

## Security Update Process

1. Security issues are prioritized
2. Fixes are developed in private forks
3. Updates are released as soon as possible
4. Users are notified through:
   - GitHub Security Advisories
   - Release notes
   - Direct communication for critical issues 