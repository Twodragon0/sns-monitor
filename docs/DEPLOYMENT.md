# SNS Monitoring System - Deployment Guide

Complete deployment guide for Docker, Kubernetes, and EKS with Okta OIDC authentication.

## 📋 Table of Contents

- [Port Configuration](#port-configuration)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [EKS Deployment](#eks-deployment)
- [Helm Chart Usage](#helm-chart-usage)
- [Okta OIDC Setup](#okta-oidc-setup)
- [Monitoring with k9s](#monitoring-with-k9s)

---

## 🔌 Port Configuration

### Updated Port Mapping (Docker)

| Service | Host Port | Container Port | Purpose | Status |
|---------|-----------|----------------|---------|--------|
| **Frontend** | 3000 | 3000 | React Dashboard | ✅ |
| **API Backend** | **8090** ✅ | 8080 | REST API | Changed from 8080 |
| **Auth Service** | 8081 | 8080 | Authentication | ✅ |
| **DynamoDB** | **8002** ✅ | 8000 | Database | Changed from 8000 |
| **LLM Analyzer** | 5000 | 5000 | AI Analysis | ✅ |
| **Redis** | 6379 | 6379 | Cache | ✅ |
| **LocalStack** | 4566, 4571 | 4566, 4571 | AWS Services | ✅ |

> **✅ Ports 8000 and 8080 are now free** for k9s and Okta OIDC!

### Why Port Changes?

**Port 8000 and 8080 were conflicting with:**
- **k9s**: Kubernetes CLI tool for cluster management
- **kubectl**: Kubernetes command-line tool with Okta OIDC authentication
- **Okta OIDC**: Local authentication server (http://localhost:8000/, http://localhost:8080/)

**Solutions:**
1. **DynamoDB**: 8000 → 8002 (host port only, container still uses 8000)
2. **API Backend**: 8080 → 8090 (host port only, container still uses 8080)

### Kubernetes vs Docker Ports

**Important:** Kubernetes does NOT have port conflicts because:
- Kubernetes uses **ClusterIP** services (internal cluster networking)
- No host port binding (services communicate via DNS within cluster)
- External access via **Ingress** (ports 80/443)
- k9s and kubectl connect to Kubernetes API server, not application ports

Therefore:
- **Docker**: Changed ports to avoid conflicts
- **Kubernetes**: No changes needed (ClusterIP isolates services)

---

## 🐳 Docker Deployment

### Prerequisites

- Docker Desktop 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum
- YouTube API Key

### Quick Start

```bash
# 1. Clone repository
git clone <repository-url>
cd sns-monitoring-system

# 2. Configure environment (optional)
cp .env.example .env
# Edit .env with your API keys

# 3. Start all services
docker-compose up -d

# 4. Verify services
docker-compose ps

# 5. Check health
curl http://localhost:8090/api/health

# 6. Access dashboard
open http://localhost:3000
```

### Service URLs (Docker)

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:3000 | React Dashboard |
| **API Backend** | **http://localhost:8090** ✅ | API Endpoints (Changed from 8080) |
| Auth Service | http://localhost:8081 | Authentication |
| DynamoDB Local | http://localhost:8002 | Database Admin (Changed from 8000) |
| LLM Analyzer | http://localhost:5000 | AI Analysis |

### Docker Commands

```bash
# Stop all services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f api-backend
docker-compose logs -f frontend

# Execute commands in containers
docker exec -it sns-monitor-api-backend bash
docker exec -it sns-monitor-youtube-crawler python3 collect_all_creators_stats.py

# Clean up (remove volumes)
docker-compose down -v
```

---

## ☸️ Kubernetes Deployment

### Prerequisites

- Kubernetes cluster 1.20+
- kubectl configured
- 16GB RAM minimum for cluster nodes
- Persistent Volume provisioner (e.g., EBS, GCE PD)

### Directory Structure

```
k8s/
├── namespace.yaml                  # Namespace definition
├── config/
│   ├── configmap.yaml             # Configuration
│   └── secrets.yaml               # Secrets (API keys, tokens)
├── deployments/
│   ├── redis.yaml                 # Redis cache
│   ├── dynamodb.yaml              # DynamoDB Local
│   ├── api-backend.yaml           # API Backend
│   ├── frontend.yaml              # React Frontend
│   ├── auth-service.yaml          # Auth Service
│   ├── youtube-crawler.yaml       # YouTube Crawler
│   └── oauth2-proxy.yaml          # Okta OAuth2 Proxy
└── ingress/
    └── ingress.yaml               # Ingress + Okta OIDC
```

### Deployment Steps

#### 1. Update Secrets

```bash
# Edit secrets with your actual values
nano k8s/config/secrets.yaml

# Update:
# - YOUTUBE_API_KEY
# - OKTA_CLIENT_SECRET
# - Other API keys
```

#### 2. Update ConfigMap

```bash
# Edit configuration
nano k8s/config/configmap.yaml

# Update:
# - OKTA_ISSUER: https://your-okta-domain.okta.com
# - OKTA_CLIENT_ID: your-client-id
# - REDIRECT_URI: https://your-domain.com/oauth2/callback
```

#### 3. Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Deploy configuration
kubectl apply -f k8s/config/

# Deploy infrastructure (Redis, DynamoDB, LocalStack)
kubectl apply -f k8s/deployments/redis.yaml
kubectl apply -f k8s/deployments/dynamodb.yaml

# Deploy services
kubectl apply -f k8s/deployments/api-backend.yaml
kubectl apply -f k8s/deployments/frontend.yaml
kubectl apply -f k8s/deployments/auth-service.yaml
kubectl apply -f k8s/deployments/youtube-crawler.yaml

# Deploy OAuth2 Proxy (for Okta)
kubectl apply -f k8s/deployments/oauth2-proxy.yaml

# Deploy Ingress
kubectl apply -f k8s/ingress/ingress.yaml
```

#### 4. Verify Deployment

```bash
# Check all pods
kubectl get pods -n sns-monitor

# Check services
kubectl get svc -n sns-monitor

# Check ingress
kubectl get ingress -n sns-monitor

# Check logs
kubectl logs -f deployment/api-backend -n sns-monitor
```

#### 5. Port Forward (for testing without Ingress)

```bash
# Frontend
kubectl port-forward svc/frontend 3000:3000 -n sns-monitor

# API Backend
kubectl port-forward svc/api-backend 8080:8080 -n sns-monitor

# Access locally
open http://localhost:3000
```

---

## 🚀 EKS Deployment

### Prerequisites

- AWS Account with EKS permissions
- eksctl or Terraform
- kubectl and aws-cli configured
- Domain name for Ingress

### EKS Cluster Setup

```bash
# Create EKS cluster with eksctl
eksctl create cluster \
  --name sns-monitor-cluster \
  --region ap-northeast-2 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 5 \
  --managed

# Configure kubectl
aws eks update-kubeconfig \
  --region ap-northeast-2 \
  --name sns-monitor-cluster

# Verify connection
kubectl get nodes
```

### Install Required Add-ons

#### 1. AWS Load Balancer Controller

```bash
# Install AWS Load Balancer Controller
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=sns-monitor-cluster \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller
```

#### 2. NGINX Ingress Controller

```bash
# Install NGINX Ingress
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer
```

#### 3. Cert-Manager (for TLS)

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create Let's Encrypt ClusterIssuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

#### 4. EBS CSI Driver (for persistent volumes)

```bash
# Install EBS CSI Driver
kubectl apply -k "github.com/kubernetes-sigs/aws-ebs-csi-driver/deploy/kubernetes/overlays/stable/?ref=release-1.24"
```

### Deploy Application to EKS

```bash
# Use Helm (recommended)
cd helm/sns-monitor

# Edit values-prod.yaml
cp values.yaml values-prod.yaml
nano values-prod.yaml

# Deploy with Helm
helm install sns-monitor . \
  --namespace sns-monitor \
  --create-namespace \
  --values values-prod.yaml

# Or use kubectl
kubectl apply -f k8s/
```

### Configure DNS

```bash
# Get Ingress Load Balancer URL
kubectl get ingress -n sns-monitor

# Create DNS A record pointing to the Load Balancer
# Example: sns-monitor.your-domain.com -> a1b2c3d4.elb.ap-northeast-2.amazonaws.com
```

---

## 📦 Helm Chart Usage

### Install Helm Chart

```bash
cd helm/sns-monitor

# Install with default values
helm install sns-monitor . \
  --namespace sns-monitor \
  --create-namespace

# Install with custom values
helm install sns-monitor . \
  --namespace sns-monitor \
  --create-namespace \
  --values my-values.yaml

# Install with Okta OIDC
helm install sns-monitor . \
  --namespace sns-monitor \
  --create-namespace \
  --set okta.enabled=true \
  --set okta.issuer="https://your-okta.okta.com" \
  --set okta.clientId="your-client-id" \
  --set okta.clientSecret="your-client-secret" \
  --set ingress.host="sns-monitor.your-domain.com"
```

### Helm Commands

```bash
# List releases
helm list -n sns-monitor

# Upgrade release
helm upgrade sns-monitor . \
  --namespace sns-monitor \
  --values my-values.yaml

# Rollback
helm rollback sns-monitor -n sns-monitor

# Uninstall
helm uninstall sns-monitor -n sns-monitor

# Dry run (test before installing)
helm install sns-monitor . \
  --namespace sns-monitor \
  --dry-run \
  --debug
```

### Custom Values Example

```yaml
# my-values.yaml
global:
  namespace: sns-monitor
  environment: production

ingress:
  host: sns-monitor.example.com
  tls:
    enabled: true

okta:
  enabled: true
  issuer: "https://your-company.okta.com"
  clientId: "prod-client-id"
  clientSecret: "prod-client-secret"

apiBackend:
  replicas: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10

secrets:
  youtubeApiKey: "your-youtube-api-key"
```

---

## 🔐 Okta OIDC Setup

### 1. Create Okta Application

1. Log in to Okta Admin Console
2. Go to **Applications** → **Create App Integration**
3. Select **OIDC - OpenID Connect**
4. Select **Web Application**
5. Configure:
   - **App integration name**: SNS Monitor
   - **Sign-in redirect URIs**:
     - `https://sns-monitor.your-domain.com/oauth2/callback`
     - `http://localhost:3000/oauth2/callback` (dev)
   - **Sign-out redirect URIs**: `https://sns-monitor.your-domain.com`
   - **Assignments**: Choose who can access

### 2. Get Client Credentials

After creating the app:
- **Client ID**: Copy this value
- **Client Secret**: Copy this value
- **Okta Domain**: e.g., `https://your-company.okta.com`
- **Issuer**: `https://your-company.okta.com`

### 3. Generate Cookie Secret

```bash
# Generate a random cookie secret
python3 -c 'import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
```

### 4. Update Configuration

#### Docker (.env)

```bash
# .env file
OKTA_ISSUER=https://your-company.okta.com
OKTA_CLIENT_ID=your-client-id
OKTA_CLIENT_SECRET=your-client-secret
```

#### Kubernetes (secrets.yaml)

```yaml
# k8s/config/secrets.yaml
stringData:
  OKTA_CLIENT_SECRET: "your-client-secret"

# k8s/config/configmap.yaml
data:
  OKTA_ISSUER: "https://your-company.okta.com"
  OKTA_CLIENT_ID: "your-client-id"
```

#### Helm (values.yaml)

```yaml
# helm/sns-monitor/values.yaml
okta:
  enabled: true
  issuer: "https://your-company.okta.com"
  clientId: "your-client-id"
  clientSecret: "your-client-secret"
  cookieSecret: "GENERATED_COOKIE_SECRET"
```

### 5. Test Authentication

```bash
# Access your application
open https://sns-monitor.your-domain.com

# You should be redirected to Okta login
# After login, you'll be redirected back to the app
```

---

## 🔍 Monitoring with k9s

### Install k9s

```bash
# macOS
brew install k9s

# Linux
curl -sS https://webinstall.dev/k9s | bash

# Windows
scoop install k9s
```

### Using k9s

```bash
# Start k9s
k9s -n sns-monitor

# Or for all namespaces
k9s -A
```

### k9s Shortcuts

| Key | Action |
|-----|--------|
| `0` | Show all namespaces |
| `:pods` | View pods |
| `:svc` | View services |
| `:deploy` | View deployments |
| `:ing` | View ingresses |
| `l` | View logs |
| `d` | Describe resource |
| `e` | Edit resource |
| `s` | Shell into pod |
| `/` | Filter resources |
| `Ctrl+A` | Toggle all namespaces |

### Monitor Specific Resources

```bash
# View pods in sns-monitor namespace
k9s -n sns-monitor

# Press :pods to view pods
# Press l to view logs
# Press s to shell into pod
```

---

## 🛠️ Troubleshooting

### Port Conflicts

```bash
# Check what's using port 8000
lsof -i :8000

# If k9s or Okta is using it, that's correct!
# DynamoDB is now on port 8002
lsof -i :8002
```

### Docker Issues

```bash
# Restart services
docker-compose restart

# Rebuild images
docker-compose build --no-cache

# Clean up
docker system prune -a
```

### Kubernetes Issues

```bash
# Check pod status
kubectl get pods -n sns-monitor

# Describe failing pod
kubectl describe pod <pod-name> -n sns-monitor

# View logs
kubectl logs -f <pod-name> -n sns-monitor

# Delete and recreate
kubectl delete pod <pod-name> -n sns-monitor
```

### Ingress Issues

```bash
# Check ingress
kubectl describe ingress -n sns-monitor

# Check ingress controller logs
kubectl logs -f -n ingress-nginx deployment/nginx-ingress-controller

# Test without ingress
kubectl port-forward svc/frontend 3000:3000 -n sns-monitor
```

---

## 📊 Verification Checklist

### Docker Deployment

- [ ] All containers are running (`docker-compose ps`)
- [ ] Port 8002 is used for DynamoDB (not 8000)
- [ ] API health check passes (http://localhost:8080/api/health)
- [ ] Frontend is accessible (http://localhost:3000)
- [ ] k9s can use port 8000 without conflicts

### Kubernetes Deployment

- [ ] All pods are Running (`kubectl get pods -n sns-monitor`)
- [ ] Services are created (`kubectl get svc -n sns-monitor`)
- [ ] Ingress is configured (`kubectl get ingress -n sns-monitor`)
- [ ] PVCs are Bound (`kubectl get pvc -n sns-monitor`)
- [ ] ConfigMap and Secrets exist

### Okta OIDC

- [ ] Okta app is configured
- [ ] Client ID and Secret are set
- [ ] Redirect URIs are correct
- [ ] Cookie secret is generated
- [ ] OAuth2 Proxy pod is running
- [ ] Login redirects to Okta
- [ ] After login, redirects back to app

---

## 🚀 Production Checklist

Before going to production:

- [ ] Use production-grade storage (EBS, GCE PD)
- [ ] Enable TLS/HTTPS with valid certificates
- [ ] Configure resource limits and requests
- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Configure log aggregation (ELK, Loki)
- [ ] Enable auto-scaling (HPA)
- [ ] Set up backups for persistent data
- [ ] Configure alerts for critical issues
- [ ] Document runbooks for common issues
- [ ] Perform load testing
- [ ] Set up CI/CD pipeline
- [ ] Configure network policies
- [ ] Enable RBAC
- [ ] Regular security audits

---

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [k9s Documentation](https://k9scli.io/)
- [Okta OIDC Guide](https://developer.okta.com/docs/guides/implement-grant-type/authcode/main/)
- [NGINX Ingress Documentation](https://kubernetes.github.io/ingress-nginx/)
- [OAuth2 Proxy](https://oauth2-proxy.github.io/oauth2-proxy/)

---

## 🆘 Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/sns-monitoring-system/issues
- Email: support@example.com
- Documentation: https://docs.your-domain.com

---

## 🏗️ Terraform Deployment (AWS Lambda/API Gateway)

### Prerequisites

- AWS CLI installed and configured
- Terraform 1.6.0+
- YouTube API Key
- Telegram Bot Token (optional)

### API Key Setup

#### 1. YouTube Data API v3 (Required)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "YouTube Data API v3"
4. Create API Key in Credentials
5. Copy the API key

**Quota**: 10,000 units/day (free)

#### 2. Telegram Bot (Optional)

1. Search for [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` command
3. Follow instructions to create bot
4. Copy Bot Token

### Terraform Configuration

#### 1. Prepare Configuration File

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
vi terraform.tfvars
```

#### 2. Configure terraform.tfvars

```hcl
# Basic settings
project_name = "sns-monitor"
aws_region = "ap-northeast-2"
environment = "dev"

# Keywords
search_keywords = ["Levvels", "Vuddy", "굿즈"]

# Crawling schedule (every 1 hour = cost saving)
crawl_schedule = "rate(1 hour)"

# API Keys (Required: YouTube, Optional: Telegram)
youtube_api_key = "YOUR_YOUTUBE_API_KEY"
telegram_bot_token = "YOUR_TELEGRAM_BOT_TOKEN"
telegram_channels = ["@your_channel"]

# Platform activation
enable_youtube = true
enable_telegram = true
enable_twitter = false  # $100/month cost

# AI Model (cost saving)
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"

# Notifications (optional)
slack_webhook_url = ""
sns_email = ""

# Cost saving options
enable_cloudwatch_logs = false
enable_waf = false
```

#### 3. Enable Bedrock Model Access

```bash
# In AWS Console (us-east-1 region)
# 1. Go to Bedrock service
# 2. Navigate to Model access
# 3. Click "Manage model access"
# 4. Select "Anthropic Claude" models
# 5. Save changes

# Or via CLI
aws bedrock list-foundation-models --region us-east-1
```

#### 4. Deploy with Terraform

```bash
# Initialize Terraform
terraform init

# Review deployment plan
terraform plan

# Deploy
terraform apply
# Type "yes" to confirm
```

**Deployment Time**: ~5-10 minutes

#### 5. Check Outputs

After deployment, important information is displayed:

```bash
Outputs:

api_gateway_url = "https://xxxxx.execute-api.ap-northeast-2.amazonaws.com/dev"
cloudfront_url = "https://xxxxx.cloudfront.net"
youtube_crawler_function_name = "sns-monitor-youtube-crawler"
telegram_crawler_function_name = "sns-monitor-telegram-crawler"
llm_analyzer_function_name = "sns-monitor-llm-analyzer"
dynamodb_table_name = "sns-monitor-analysis-results"
```

**Important**: Save `api_gateway_url` and `cloudfront_url`!

### Chrome Extension Setup

1. Load extension in Chrome (`chrome://extensions`)
2. Enable Developer mode
3. Click "Load unpacked" and select `chrome-extension/` folder
4. Configure API Gateway URL and API Key in extension settings

### Troubleshooting Terraform Deployment

#### Bedrock Access Denied

**Error**: `AccessDeniedException: User is not authorized`

**Solution**: Enable Bedrock model access in AWS Console (us-east-1)

#### S3 Bucket Already Exists

**Error**: `BucketAlreadyExists`

**Solution**: Change `project_name` in terraform.tfvars to a unique name

#### YouTube API Quota Exceeded

**Solution**: Reduce crawling frequency in terraform.tfvars:
```hcl
crawl_schedule = "rate(2 hours)"  # Every 2 hours instead of 1
```

### Terraform Maintenance

```bash
# Update infrastructure
cd terraform
terraform plan
terraform apply

# Destroy all resources
terraform destroy
```

⚠️ **Warning**: S3 bucket data may need manual deletion.

---

**Version**: 1.1.0
**Last Updated**: 2025-12-29
