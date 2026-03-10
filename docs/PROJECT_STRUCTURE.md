# SNS Monitoring System - Project Structure

**Version**: 1.0.0
**Last Updated**: 2025-11-21

## 📁 Directory Structure

```
sns-monitoring-system/
├── 📄 README.md                          # Project overview and quick start
├── 📄 ARCHITECTURE.md                    # System architecture and cost analysis
├── 📄 DEPLOYMENT.md                      # Complete deployment guide
├── 📄 SUMMARY.md                         # Port configuration summary
├── 📄 KUBECTL_OKTA_PORTS.md              # kubectl + Okta OIDC analysis
├── 📄 docker-compose.yml                 # Docker Compose configuration
├── 📄 .env.example                       # Environment variables template
│
├── 📂 lambda/                            # AWS Lambda functions (also run in Docker)
│   ├── api-backend/                      # REST API backend (Port 8090)
│   │   └── lambda_function.py
│   ├── auth-service/                     # Authentication service (Port 8081)
│   │   └── lambda_function.py
│   ├── youtube-crawler/                  # YouTube data collector
│   │   ├── lambda_function.py
│   │   ├── optimized_youtube_api.py      # YouTube API with caching
│   │   └── run_crawler.py
│   ├── llm-analyzer/                     # AI analysis service (Port 5000)
│   │   └── lambda_function.py
│   ├── vuddy-crawler/                    # Vuddy platform crawler
│   │   └── lambda_function.py
│   ├── rss-crawler/                      # RSS feed crawler
│   ├── telegram-crawler/                 # Telegram bot crawler
│   ├── twitter-crawler/                  # Twitter/X crawler
│   ├── instagram-crawler/                # Instagram crawler
│   ├── facebook-crawler/                 # Facebook crawler
│   ├── threads-crawler/                  # Threads crawler
│   └── common/                           # Shared utilities
│       └── local_storage.py              # Local file storage helper
│
├── 📂 frontend/                          # React frontend application
│   ├── public/                           # Static assets
│   ├── src/
│   │   ├── App.js                        # Main app component
│   │   ├── index.js                      # Entry point
│   │   ├── components/
│   │   │   ├── Dashboard.jsx             # Main dashboard
│   │   │   ├── ArchiveStudioDetail.jsx   # AkaiV Studio detail page
│   │   │   └── AuthLogin.jsx             # Login component
│   │   └── setupProxy.js                 # Dev proxy configuration
│   ├── package.json
│   └── Dockerfile
│
├── 📂 k8s/                               # Kubernetes manifests
│   ├── namespace.yaml                    # Namespace definition
│   ├── config/
│   │   ├── configmap.yaml                # Configuration
│   │   └── secrets.yaml                  # Secrets (API keys)
│   ├── deployments/
│   │   ├── api-backend.yaml              # API Backend deployment
│   │   ├── frontend.yaml                 # Frontend deployment
│   │   ├── auth-service.yaml             # Auth service deployment
│   │   ├── redis.yaml                    # Redis cache
│   │   ├── dynamodb.yaml                 # DynamoDB Local
│   │   ├── youtube-crawler.yaml          # YouTube crawler
│   │   └── oauth2-proxy.yaml             # Okta OAuth2 Proxy
│   └── ingress/
│       └── ingress.yaml                  # Ingress with Okta OIDC
│
├── 📂 helm/                              # Helm chart
│   └── sns-monitor/
│       ├── Chart.yaml                    # Chart metadata
│       ├── values.yaml                   # Default values
│       ├── README.md                     # Helm usage guide
│       └── templates/
│           ├── _helpers.tpl              # Template helpers
│           ├── namespace.yaml
│           ├── config/
│           │   ├── configmap.yaml
│           │   └── secrets.yaml
│           ├── deployments/
│           │   ├── api-backend.yaml
│           │   └── frontend.yaml
│           └── ingress/
│               └── ingress.yaml
│
├── 📂 docker/                            # Docker configuration files
│   ├── Dockerfile.api                    # API services Dockerfile
│   ├── Dockerfile.crawler                # Crawler services Dockerfile
│   ├── Dockerfile.analyzer               # Analyzer Dockerfile
│   ├── Dockerfile.frontend               # Frontend Dockerfile
│   ├── Dockerfile.scheduler              # Scheduler Dockerfile
│   ├── init-dynamodb.py                  # DynamoDB initialization
│   └── init-localstack.py                # LocalStack initialization
│
├── 📂 local-data/                        # Local data storage
│   └── vuddy/comprehensive_analysis/
│       ├── vuddy-creators.json           # All creators data (9 creators)
│       └── akaiv-studio-members.json     # AkaiV Studio members (5 members)
│
├── 📂 chrome-extension/                  # Chrome Extension for data collection
│   ├── manifest.json                     # Extension manifest
│   ├── popup.html                        # Extension popup UI
│   ├── popup.js                          # Popup logic
│   ├── content-youtube.js                # YouTube content script
│   └── content-twitter.js                # Twitter content script
│
├── 📂 scripts/                           # Utility scripts
│   ├── README.md                         # Scripts documentation
│   ├── start_local_api.py                # Start local API server
│   ├── test_local.py                     # Test local setup
│   └── archive/                          # Archived one-time scripts
│       ├── collect_*.py                  # Data collection scripts
│       ├── update_*.py                   # Data migration scripts
│       └── add_*.py                      # Data addition scripts
│
├── 📂 docs/                              # Documentation
│   ├── README.md                         # Documentation index
│   └── archive/                          # Archived documentation
│       ├── README.old.md
│       ├── DOCKER_SETUP.md
│       ├── LOCAL_DEVELOPMENT.md
│       ├── LOCAL_TESTING.md
│       └── QUICKSTART.md
│
└── 📂 docker-data/                       # Docker persistent data
    ├── dynamodb/                         # DynamoDB data
    ├── redis/                            # Redis data
    └── localstack/                       # LocalStack data
```

## 🚀 Key Components

### Core Services

| Service | Port | Purpose | Technology |
|---------|------|---------|------------|
| **Frontend** | 3000 | React Dashboard | React 18 |
| **API Backend** | 8090 | REST API | Python 3.11, Flask-like |
| **Auth Service** | 8081 | Authentication | Python 3.11, OAuth2 |
| **LLM Analyzer** | 5000 | AI Analysis | Python 3.11, Claude/OpenAI |
| **DynamoDB** | 8002 | Database | DynamoDB Local |
| **Redis** | 6379 | Cache | Redis 7 |

### Data Collection

- **YouTube Crawler**: Collects channel statistics, videos, comments
- **Vuddy Crawler**: Scrapes Vuddy platform data
- **RSS Crawler**: Aggregates RSS feed content
- **Social Media Crawlers**: Twitter, Instagram, Facebook, Telegram, Threads

### Infrastructure

- **Docker Compose**: Local development and testing
- **Kubernetes**: Production deployment
- **Helm**: Kubernetes package management
- **Okta OAuth2 Proxy**: Authentication for Kubernetes

## 📊 Data Flow

```
1. Data Collection
   Chrome Extension / Crawlers → Lambda Functions → S3 / Local Storage

2. Data Processing
   Raw Data → LLM Analyzer → Sentiment/Trend Analysis → DynamoDB

3. API Layer
   Frontend → API Backend → DynamoDB / Local Storage → Response

4. Caching
   API Backend → Redis Cache (15min TTL) → Reduced API calls
```

## 🔧 Configuration Files

### Environment Variables

```bash
# .env (create from .env.example)
YOUTUBE_API_KEY=your_key_here
SEARCH_KEYWORDS=Levvels,Vuddy,굿즈
CRAWL_SCHEDULE=*/30 * * * *
LOCAL_MODE=true
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  - api-backend (port 8090)
  - frontend (port 3000)
  - auth-service (port 8081)
  - dynamodb-local (port 8002)
  - redis (port 6379)
  - llm-analyzer (port 5000)
  - crawlers (youtube, rss, etc.)
```

### Kubernetes

```yaml
# k8s/ directory
- Namespace: sns-monitor
- ConfigMaps: Configuration
- Secrets: API keys, credentials
- Deployments: All services
- Services: ClusterIP (internal)
- Ingress: NGINX + Okta OIDC
```

## 📝 Important Files

### Documentation
- **README.md** - Project overview
- **ARCHITECTURE.md** - System design and costs
- **DEPLOYMENT.md** - Deployment instructions
- **SUMMARY.md** - Configuration summary
- **KUBECTL_OKTA_PORTS.md** - kubectl + Okta setup

### Configuration
- **docker-compose.yml** - Docker services
- **.env.example** - Environment template
- **k8s/config/** - Kubernetes configuration
- **helm/sns-monitor/values.yaml** - Helm values

### Data
- **local-data/vuddy/comprehensive_analysis/** - Creator data
  - vuddy-creators.json (9 creators, 243K subscribers)
  - akaiv-studio-members.json (5 members)

## 🗑️ Cleaned Up

### Removed
- ❌ `lambda/naver-cafe-crawler/` - Empty folder
- ❌ `lambda/multi-llm-analyzer/` - Duplicate of llm-analyzer

### Archived
- 📦 `docs/archive/` - Old documentation (6 files)
- 📦 `scripts/archive/` - One-time scripts (30+ files)
  - collect_*.py, update_*.py, add_*.py, etc.

## 🎯 Usage Patterns

### Local Development

```bash
# Start all services
docker-compose up -d

# Access services
Frontend: http://localhost:3000
API: http://localhost:8090
DynamoDB: http://localhost:8002
```

### Kubernetes Deployment

```bash
# Deploy with kubectl
kubectl apply -f k8s/

# Or use Helm
helm install sns-monitor ./helm/sns-monitor
```

### Data Collection

```bash
# Manual collection
docker exec sns-monitor-youtube-crawler python3 /app/run_crawler.py

# Or use Chrome Extension
# Install extension → Visit YouTube → Click extension → Collect
```

## 📈 Metrics

- **Total Files**: ~100+ source files
- **Docker Services**: 14 containers
- **Kubernetes Resources**: 20+ manifests
- **Lambda Functions**: 10 active functions
- **Documentation**: 5 main docs
- **Creators Tracked**: 9 creators
- **Total Subscribers**: 243,330+

## 🔐 Security

- OAuth2 authentication (Okta)
- Secrets management (K8s Secrets, env vars)
- API key protection
- HTTPS/TLS support
- CORS configuration
- Rate limiting

## 🚀 Next Steps

1. Add monitoring (Prometheus, Grafana)
2. Implement CI/CD pipeline
3. Add more social media platforms
4. Enhance AI analysis features
5. Implement real-time notifications

---

**Maintained By**: SNS Monitor Team
**License**: MIT
**Last Cleanup**: 2025-11-21
