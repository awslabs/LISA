# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 5.x.x   | :white_check_mark: |
| 4.x.x   | :x:                |
| 3.x.x   | :x:                |
| < 3.0   | :x:                |

## Security Measures

### Static Analysis Security Testing (SAST)

The LISA project implements comprehensive SAST scanning across all code changes:

- **CodeQL Analysis**: Runs on all branches and PRs for JavaScript and Python
- **Bandit Security Scanner**: Python-specific security analysis
- **ESLint Security Rules**: JavaScript/TypeScript security scanning
- **CDK-NAG**: Infrastructure security validation
- **Dependency Scanning**: Automated vulnerability detection

### Vulnerability Management

The project implements proactive vulnerability management:

- **Automated Vulnerability Blocking**: PRs with critical/high vulnerabilities are automatically blocked
- **Dependency Update Automation**: Weekly automated checks for security updates
- **Security Patch Automation**: Automatic PR creation for security-critical updates
- **Vulnerability Reporting**: Comprehensive vulnerability reports on all PRs

### Security Gates

All pull requests must pass security gates before merging:

- No high/critical security vulnerabilities
- No moderate+ NPM package vulnerabilities
- No known Python package vulnerabilities
- All security scans must complete successfully

### Automated Security Workflows

- **Security Gate**: Blocks PRs with security issues
- **Vulnerability Blocking**: Prevents introduction of new vulnerabilities
- **Dependency Updates**: Automated security patch management
- **Comprehensive SAST**: Weekly security scanning
- **Vulnerability Scanning**: Trivy-based container and filesystem scanning
- **Dependency Review**: Automated dependency vulnerability checks

## Vulnerability Management Process

### Automated Vulnerability Detection

1. **Continuous Monitoring**: All PRs are scanned for vulnerabilities
2. **Severity-Based Blocking**: Critical and high vulnerabilities block merging
3. **Moderate Vulnerability Reporting**: Moderate issues are reported but don't block
4. **Automated Updates**: Security patches are automatically applied when possible

### Dependency Update Workflow

1. **Weekly Scans**: Automated dependency checks every Monday
2. **Security-First Updates**: Critical and high vulnerabilities trigger immediate updates
3. **Automated PR Creation**: Security updates are automatically proposed
4. **Review Process**: All updates require human review before merging

### Current Vulnerability Status

- **Critical Vulnerabilities**: 0
- **High Vulnerabilities**: 0  
- **Moderate Vulnerabilities**: 6 (in development dependencies)
- **Low Vulnerabilities**: 0

> **Note**: The 6 moderate vulnerabilities are in development dependencies (vitepress, react-syntax-highlighter) and are being actively monitored. They don't pose immediate security risks to production deployments.

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### GitHub Security Advisory

1. Go to the [Security tab](https://github.com/awslabs/LISA/security/advisories)
2. Click "Report a vulnerability"
3. Fill out the security advisory form
4. Submit for review

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Resolution**: Within 30 days for critical issues
- **Public Disclosure**: Coordinated release with fixes

## Security Best Practices

### For Contributors

1. **Code Review**: All changes require security-focused review
2. **Dependency Updates**: Keep dependencies updated and secure
3. **Input Validation**: Always validate and sanitize user inputs
4. **Secret Management**: Never commit secrets or sensitive data
5. **Security Testing**: Run security scans locally before submitting PRs

### For Users

1. **Keep Updated**: Always use the latest stable release
2. **Monitor Advisories**: Subscribe to security notifications
3. **Report Issues**: Report any security concerns immediately
4. **Follow Guidelines**: Implement security best practices in your deployments

## Token Permissions Strategy

The LISA project implements a comprehensive token permissions strategy based on the principle of least privilege:

### Permission Levels
- **Level 1 (Read-Only)**: Default for testing, linting, and security scanning
- **Level 2 (Security Operations)**: For uploading security scan results
- **Level 3 (Content Management)**: For git operations like merging and branching
- **Level 4 (Package Management)**: For publishing NPM packages
- **Level 5 (Pull Request Management)**: For creating PRs and commenting
- **Level 6 (Release Management)**: For release branches and hotfixes
- **Level 7 (Deployment Operations)**: For AWS deployments using OIDC
- **Level 8 (GitHub Pages)**: For documentation deployment
- **Level 9 (No Permissions)**: For external notifications only

### Security Benefits
- **Least Privilege**: All workflows start with minimal permissions
- **Explicit Scoping**: Every permission has a documented purpose
- **Regular Audits**: Quarterly permission reviews and updates
- **Compliance**: Follows OWASP and GitHub security best practices

For detailed information, see [`.github/TOKEN_PERMISSIONS.md`](.github/TOKEN_PERMISSIONS.md).

## Dangerous Workflow Mitigation

The LISA project implements comprehensive dangerous workflow mitigation strategies:

### Key Security Measures
- **Pull Request Security**: Uses `pull_request_target` instead of `pull_request` for security workflows
- **Base Branch Checkout**: Only checks out trusted base branch code, not PR code
- **Latest Action Versions**: All GitHub Actions use latest stable versions
- **Input Validation**: Comprehensive input validation and sanitization
- **Permission Scoping**: Minimal required permissions for all workflows

### Security Benefits
- **Prevents Code Injection**: Malicious PRs cannot execute code
- **Reduces Attack Surface**: Workflows only access what they need
- **Latest Security**: Up-to-date actions with security patches
- **Compliance**: Follows OWASP and GitHub security best practices

For detailed information, see [`.github/DANGEROUS_WORKFLOW_MITIGATION.md`](.github/DANGEROUS_WORKFLOW_MITIGATION.md).

## Security Tools and Configuration

### Local Development

```bash
# Run security scans locally
npm run lint                    # ESLint with security rules
pip install bandit && bandit -r .  # Python security scan
npm audit                      # NPM vulnerability check
pip install safety && safety check  # Python vulnerability check
```

### CI/CD Integration

Security scanning is automatically integrated into all CI/CD pipelines:

- **Pre-commit**: Local security checks
- **PR Checks**: Automated security gates
- **Vulnerability Blocking**: Prevents vulnerable code from merging
- **Branch Protection**: Security requirements enforced
- **Release Validation**: Final security verification

## Security Contacts

- **Security Team**: security@awslabs.com
- **Project Maintainers**: [GitHub Team](https://github.com/orgs/awslabs/teams/lisa-maintainers)
- **Emergency**: For critical vulnerabilities, email security@awslabs.com with `[URGENT]` in subject

## Security History

- **2024-09-02**: Implemented comprehensive SAST scanning
- **2024-09-02**: Added security gates and PR blocking
- **2024-09-02**: Enhanced dependency vulnerability scanning
- **2024-09-02**: Implemented vulnerability blocking and automated updates
- **2024-09-02**: Updated AWS CDK to fix brace-expansion vulnerability

## Compliance and Standards

The LISA project follows these security standards:

- **OWASP Top 10**: Addresses common web application vulnerabilities
- **CWE/SANS Top 25**: Prevents critical software weaknesses
- **NIST Cybersecurity Framework**: Comprehensive security approach
- **AWS Security Best Practices**: Cloud-native security patterns

## Security Metrics

- **SAST Coverage**: 100% of code changes
- **Vulnerability Response**: < 48 hours acknowledgment
- **Security Reviews**: Required for all PRs
- **Automated Scanning**: Continuous security monitoring
- **Vulnerability Blocking**: 100% of critical/high vulnerabilities blocked
- **Dependency Updates**: Weekly automated security checks

---

*This security policy is maintained by the LISA project maintainers and security team. For questions or concerns, please contact security@awslabs.com.*
