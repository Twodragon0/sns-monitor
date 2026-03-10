# SNS Monitor Helm Chart

Helm chart for deploying SNS Monitoring & Creator Analytics System on Kubernetes.

## Features

- **Security Hardened**: Pod Security Standards, Network Policies, read-only filesystems
- **Cost Optimized**: HPA autoscaling, CronJob crawlers, resource limits
- **High Availability**: PDB, multi-replica deployments
- **Production Ready**: TLS, rate limiting, secrets management

## Prerequisites

- Kubernetes 1.24+
- Helm 3.10+
- kubectl configured to communicate with your cluster
- PersistentVolume provisioner support (for data persistence)
- (Optional) cert-manager for TLS certificates
- (Optional) NGINX Ingress Controller

## Installing the Chart

### 1. Add the Helm repository (if published)

```bash
helm repo add sns-monitor https://your-charts-repo.com
helm repo update
```

### 2. Install with default values

```bash
helm install sns-monitor ./helm/sns-monitor \
  --namespace sns-monitor \
  --create-namespace
```

### 3. Install with custom values

```bash
# Create your values file
cp helm/sns-monitor/values.yaml my-values.yaml

# Edit my-values.yaml with your configuration

# Install
helm install sns-monitor ./helm/sns-monitor \
  --namespace sns-monitor \
  --create-namespace \
  --values my-values.yaml
```

### 4. Install with Okta OIDC enabled

```bash
helm install sns-monitor ./helm/sns-monitor \
  --namespace sns-monitor \
  --create-namespace \
  --set okta.enabled=true \
  --set okta.issuer="https://your-okta-domain.okta.com" \
  --set okta.clientId="your-client-id" \
  --set okta.clientSecret="your-client-secret" \
  --set okta.cookieSecret="$(python -c 'import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')" \
  --set ingress.host="sns-monitor.your-domain.com" \
  --set secrets.youtubeApiKey="your-youtube-api-key"
```

## Uninstalling the Chart

```bash
helm uninstall sns-monitor --namespace sns-monitor
```

## Configuration

The following table lists the configurable parameters and their default values.

### Global Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.namespace` | Namespace to deploy to | `sns-monitor` |
| `global.environment` | Environment label | `production` |
| `global.storageClass` | Storage class for PVCs | `standard` |

### Okta OIDC Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `okta.enabled` | Enable Okta OIDC authentication | `true` |
| `okta.issuer` | Okta issuer URL | `https://your-okta-domain.okta.com` |
| `okta.clientId` | Okta client ID | `your-okta-client-id` |
| `okta.clientSecret` | Okta client secret | `your-okta-client-secret` |
| `okta.cookieSecret` | OAuth2 Proxy cookie secret (base64) | `REPLACE_WITH_GENERATED_SECRET` |
| `okta.redirectUrl` | OAuth2 redirect URL | `https://sns-monitor.your-domain.com/oauth2/callback` |

### Ingress Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable Ingress | `true` |
| `ingress.className` | Ingress class | `nginx` |
| `ingress.host` | Ingress hostname | `sns-monitor.your-domain.com` |
| `ingress.tls.enabled` | Enable TLS | `true` |
| `ingress.tls.secretName` | TLS secret name | `sns-monitor-tls` |

### Application Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.searchKeywords` | Keywords to monitor | `ExampleCorp,CreatorBrand,goods` |
| `config.localMode` | Enable local mode | `false` |
| `config.s3Bucket` | S3 bucket name | `sns-monitor-data` |

### Service Replicas

| Parameter | Description | Default |
|-----------|-------------|---------|
| `apiBackend.replicas` | API Backend replicas | `2` |
| `frontend.replicas` | Frontend replicas | `2` |
| `authService.replicas` | Auth Service replicas | `2` |
| `oauth2Proxy.replicas` | OAuth2 Proxy replicas | `2` |

### Secrets

| Parameter | Description | Default |
|-----------|-------------|---------|
| `secrets.youtubeApiKey` | YouTube API key | `your-youtube-api-key` |
| `secrets.telegramBotToken` | Telegram bot token | `""` |
| `secrets.claudeApiKey` | Claude API key | `""` |
| `secrets.openaiApiKey` | OpenAI API key | `""` |

## Example Configurations

### Development Environment

```yaml
# values-dev.yaml
global:
  environment: development
  storageClass: standard

ingress:
  host: sns-monitor-dev.your-domain.com
  tls:
    enabled: false

okta:
  enabled: false

apiBackend:
  replicas: 1
  resources:
    requests:
      memory: "256Mi"
      cpu: "100m"

frontend:
  replicas: 1
  resources:
    requests:
      memory: "128Mi"
      cpu: "50m"

redis:
  persistence:
    size: 2Gi

dynamodb:
  persistence:
    size: 5Gi
```

### Production Environment

```yaml
# values-prod.yaml
global:
  environment: production
  storageClass: gp3

ingress:
  host: sns-monitor.your-domain.com
  tls:
    enabled: true
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"

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
    targetCPUUtilizationPercentage: 70

frontend:
  replicas: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 5

redis:
  persistence:
    size: 10Gi

dynamodb:
  persistence:
    size: 50Gi

monitoring:
  enabled: true
  prometheus:
    enabled: true
  grafana:
    enabled: true
```

## Deployment Commands

### Deploy to Development

```bash
helm upgrade --install sns-monitor ./helm/sns-monitor \
  --namespace sns-monitor-dev \
  --create-namespace \
  --values helm/sns-monitor/values-dev.yaml
```

### Deploy to Production

```bash
helm upgrade --install sns-monitor ./helm/sns-monitor \
  --namespace sns-monitor-prod \
  --create-namespace \
  --values helm/sns-monitor/values-prod.yaml
```

### Dry Run (Test before deployment)

```bash
helm install sns-monitor ./helm/sns-monitor \
  --namespace sns-monitor \
  --dry-run \
  --debug \
  --values my-values.yaml
```

## Post-Installation

### 1. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n sns-monitor

# Check services
kubectl get svc -n sns-monitor

# Check ingress
kubectl get ingress -n sns-monitor
```

### 2. Access the Application

```bash
# Get ingress URL
kubectl get ingress -n sns-monitor

# Open in browser
open https://sns-monitor.your-domain.com
```

### 3. Initialize DynamoDB Tables

```bash
# The init job should run automatically
kubectl get jobs -n sns-monitor

# Check logs
kubectl logs job/sns-monitor-dynamodb-init -n sns-monitor
```

## Troubleshooting

### Check Pod Logs

```bash
kubectl logs -f deployment/sns-monitor-api-backend -n sns-monitor
kubectl logs -f deployment/sns-monitor-frontend -n sns-monitor
```

### Check ConfigMap

```bash
kubectl get configmap sns-monitor-config -n sns-monitor -o yaml
```

### Check Secrets

```bash
kubectl get secrets -n sns-monitor
```

### Debug OAuth2 Proxy

```bash
kubectl logs -f deployment/sns-monitor-oauth2-proxy -n sns-monitor
```

## Upgrading

```bash
helm upgrade sns-monitor ./helm/sns-monitor \
  --namespace sns-monitor \
  --values my-values.yaml
```

## Rolling Back

```bash
# List releases
helm history sns-monitor -n sns-monitor

# Rollback to previous version
helm rollback sns-monitor -n sns-monitor

# Rollback to specific revision
helm rollback sns-monitor 2 -n sns-monitor
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/sns-monitoring-system/issues
- Documentation: https://docs.your-domain.com

## License

MIT License
