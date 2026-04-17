# AGENTS.md — Kubernetes Helm Chart

<!-- Parent: ../AGENTS.md -->
Generated: 2026-04-08

## Overview

Helm chart for production Kubernetes deployment of SNS Monitor. Subdirectory `sns-monitor/` contains templates for API backend, frontend, Redis, crawlers, RBAC, networking, and autoscaling.

## Chart Structure

```
helm/sns-monitor/
  Chart.yaml                          # Chart metadata (v1.0.0)
  values.yaml                         # Default values (dev environment)
  values-production.yaml              # Production overrides
  templates/
    namespace.yaml                    # Namespace creation
    serviceaccount.yaml               # Service account for pod identity
    rbac.yaml                         # Roles and role bindings
    configmap.yaml                    # Environment configuration
    secrets.yaml                      # Sealed secrets template
    deployment-api-backend.yaml       # API backend deployment
    deployment-frontend.yaml          # Frontend deployment (Vite + nginx)
    deployment-auth-service.yaml      # OAuth2 proxy (optional)
    deployment-dynamodb-local.yaml    # Local DynamoDB (dev only)
    deployment-llm-analyzer.yaml      # MiroFish/LLM service (optional)
    services.yaml                     # Service definitions (backend, frontend, Redis)
    ingress.yaml                      # Ingress routing (API + frontend)
    hpa.yaml                          # Horizontal Pod Autoscaler (backend, frontend)
    pdb.yaml                          # Pod Disruption Budget
    networkpolicy.yaml                # Network policies (optional)
    redis.yaml                        # Redis StatefulSet
    cronjob-crawlers.yaml             # YouTube/DCInside/Naver crawlers
    cronjob-s3-sync.yaml              # S3 data sync (optional)
    cronjob-scaler.yaml               # HPA scaling triggers (optional)
    pvc.yaml                          # PersistentVolumeClaims
    _helpers.tpl                      # Template helpers (labels, image pulls)
```

## Key Templates

### deployment-api-backend.yaml
- Runs `app-backend:latest` image
- Liveness probe: `GET /health` port 8080
- Environment: loaded from ConfigMap + Secrets
- Replicas: controlled by HPA (min 2, max 10)
- Resource limits: CPU 500m, memory 512Mi

### deployment-frontend.yaml
- Runs `app-frontend:latest` image (Vite build + nginx)
- Exposed via Service + Ingress
- Cache headers: static assets (Cache-Control: max-age=31536000)
- Replicas: 2 (no HPA, stable load)

### cronjob-crawlers.yaml
- YouTube crawler: every 2 hours (0 */2 * * *)
- DCInside crawler: every 4 hours (0 */4 * * *)
- Naver crawler: every 6 hours (0 */6 * * *)
- Mounts: shared PVC for `/local-data/`

### ingress.yaml
- API backend: `api.example.com/api/*` → Service api-backend:8080
- Frontend: `example.com/` → Service frontend:3000
- TLS: cert-manager (optional)

## Configuration Files

### values.yaml (Development)
- Namespace: `platform`
- Registry: `ghcr.io/your-org`
- Backend replicas: 2
- Frontend replicas: 2
- Redis enabled: true
- HPA enabled: true

### values-production.yaml
- Backend replicas: 3
- Frontend replicas: 3
- Resource requests/limits increased
- Pod disruption budgets enforced
- Network policies enabled

## Common Commands

```bash
# Lint chart
helm lint helm/sns-monitor

# Dry-run install
helm install sns-monitor helm/sns-monitor \
  --namespace platform \
  --values helm/sns-monitor/values.yaml \
  --dry-run --debug

# Install (dev)
helm install sns-monitor helm/sns-monitor \
  --namespace platform \
  --values helm/sns-monitor/values.yaml

# Upgrade (dev)
helm upgrade sns-monitor helm/sns-monitor \
  --namespace platform \
  --values helm/sns-monitor/values.yaml

# Install (production)
helm install sns-monitor helm/sns-monitor \
  --namespace platform \
  --values helm/sns-monitor/values.yaml \
  --values helm/sns-monitor/values-production.yaml

# Check status
helm status sns-monitor -n platform

# Rollback previous release
helm rollback sns-monitor 1 -n platform

# Delete release
helm uninstall sns-monitor -n platform
```

## Customization

**Image registry**: Edit `appImages.registry` in values.yaml
```yaml
appImages:
  registry: "ghcr.io/your-org"
```

**Replica counts**: Edit deployments section
```yaml
backend:
  replicaCount: 3
frontend:
  replicaCount: 2
```

**HPA settings**: Edit hpa.yaml minReplicas, maxReplicas, targetCPUUtilization

**Ingress domain**: Edit ingress.yaml hosts and TLS issuer

**Environment variables**: Edit configmap.yaml or use `--set key=value`

## Deployment Flow (deploy-k8s.sh)

Script in `scripts/deploy-k8s.sh` automates deployment:

1. Verify kubeconfig
2. Create/confirm namespace
3. Build frontend (if needed)
4. Restart backend deployment or Helm install
5. Restart frontend deployment or Helm install
6. Verify pods, services, deployments

Usage:
```bash
./scripts/deploy-k8s.sh platform dev all
./scripts/deploy-k8s.sh platform prod backend
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| CrashLoopBackOff | Image pull failed | Check registry auth, image tag in values.yaml |
| Pending PVC | Storage class missing | Verify `ebs-gp3-ext4` exists: `kubectl get sc` |
| Helm lint fails | Template syntax error | Check indentation, conditionals in YAML |
| Pods not ready | Health probe failing | Verify app listening on declared port (8080/3000) |

## Related Files

- `docker-compose.yml` — Local dev equivalent
- `docker/` — Dockerfile definitions
- `scripts/deploy-k8s.sh` — Deployment automation script
- `CLAUDE.md` — Environment variables and secrets management
