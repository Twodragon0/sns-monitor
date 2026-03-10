# Documentation Index

This directory contains all documentation for the SNS Monitoring System.

## 📚 Main Documentation

### Core Documents

- **[README.md](../README.md)** - Project overview and quick start guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture (EKS, Pod Identity, S3)
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide (Docker, Kubernetes, EKS, Helm, Terraform)
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Detailed project structure and organization
- **[SUMMARY.md](SUMMARY.md)** - Port configuration summary and changes
- **[CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md)** - Project cleanup history
- **[KUBECTL_OKTA_PORTS.md](KUBECTL_OKTA_PORTS.md)** - kubectl + Okta OIDC port analysis

### Specialized Guides

- **[cost-optimization.md](cost-optimization.md)** - Cost optimization strategies
- **[dcinside-monitoring-guide.md](dcinside-monitoring-guide.md)** - DCInside crawler guide
- **[monitoring-guide.md](monitoring-guide.md)** - Monitoring and observability
- **[oauth-setup.md](oauth-setup.md)** - OAuth2/OIDC setup guide
- **[pod-identity-migration-summary.md](pod-identity-migration-summary.md)** - Pod Identity migration from IRSA
- **[terraform-s3-security-improvements.md](terraform-s3-security-improvements.md)** - S3 security enhancements
- **[rss-feeds.md](rss-feeds.md)** - RSS feed configuration

### UI/UX Documentation

- **[ui-ux-improvements.md](ui-ux-improvements.md)** - UI/UX improvement plans
- **[ui-ux-summary.md](ui-ux-summary.md)** - UI/UX changes summary

### Data Analysis

- **[vuddy-comprehensive-analysis.md](vuddy-comprehensive-analysis.md)** - Vuddy platform analysis
- **[vuddy-creators.md](vuddy-creators.md)** - Creator data documentation

### Architecture Diagrams

- **[architecture.drawio](architecture.drawio)** - System architecture diagram (Draw.io format)
- **[architecture.drawio.png](architecture.drawio.png)** - Architecture diagram (PNG)

## 📦 Archived Documentation

The `archive/` subdirectory contains older documentation versions:

- `ARCHITECTURE-old.md` - Previous architecture documentation
- `deployment-guide.md` - Terraform deployment guide (merged into DEPLOYMENT.md)
- `DOCKER_SETUP.md` - Old Docker setup guide
- `LOCAL_DEVELOPMENT.md` - Old local development guide
- `LOCAL_TESTING.md` - Old testing guide
- `QUICKSTART.md` - Old quickstart guide
- `README_LOCAL.md` - Old local setup guide
- `README.old.md` - Previous README version

## 🗂️ Documentation Structure

```
docs/
├── README.md                          # This file
├── ARCHITECTURE.md                    # Main architecture doc
├── DEPLOYMENT.md                      # Main deployment guide
├── PROJECT_STRUCTURE.md               # Project structure
├── SUMMARY.md                         # Port configuration
├── CLEANUP_SUMMARY.md                 # Cleanup history
├── KUBECTL_OKTA_PORTS.md              # kubectl/Okta ports
│
├── cost-optimization.md               # Cost guides
├── dcinside-monitoring-guide.md       # DCInside guide
├── monitoring-guide.md                # Monitoring guide
├── oauth-setup.md                     # OAuth setup
├── pod-identity-migration-summary.md  # Pod Identity migration
├── terraform-s3-security-improvements.md  # S3 security
├── rss-feeds.md                       # RSS configuration
│
├── ui-ux-improvements.md              # UI/UX plans
├── ui-ux-summary.md                   # UI/UX summary
│
├── vuddy-comprehensive-analysis.md    # Vuddy analysis
├── vuddy-creators.md                  # Creator docs
│
├── architecture.drawio                # Architecture diagram
├── architecture.drawio.png            # Architecture image
│
└── archive/                           # Archived docs
    ├── ARCHITECTURE-old.md
    ├── deployment-guide.md
    ├── DOCKER_SETUP.md
    ├── LOCAL_DEVELOPMENT.md
    ├── LOCAL_TESTING.md
    ├── QUICKSTART.md
    ├── README_LOCAL.md
    └── README.old.md
```

## 🚀 Quick Links

- **Getting Started**: [README.md](../README.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Project Structure**: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

## 📝 Documentation Standards

- All documentation is written in Markdown
- Use clear headings and structure
- Include code examples where applicable
- Keep documentation up-to-date with code changes
- Archive old versions instead of deleting

---

**Last Updated**: 2025-12-29
