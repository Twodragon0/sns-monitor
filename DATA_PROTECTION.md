# 데이터 보호 및 GitHub 업로드 금지 사항

회사 개인정보, 계정 ID, Role, 비밀번호 등 내부 정보가 저장소에 커밋·푸시되지 않도록 정리한 가이드입니다.

## 1. GitHub에 올리면 안 되는 것

| 구분 | 예시 | 대응 |
|------|------|------|
| **계정/리소스 ID** | AWS Account ID, EKS Role ARN, Certificate ARN | `.gitignore` + `*.example` 파일만 커밋 |
| **인증 정보** | API Key, Client Secret, OAuth Client ID/Secret, Okta 토큰 | 환경 변수·Secret Manager·K8s Secret 사용 |
| **개인정보** | 이메일, 전화번호, 실명, 사내 계정 정보 | 코드/설정에 포함 금지 |
| **로컬/내부 설정** | 실제 도메인, 실제 클러스터명, 내부 URL | `*-local.yaml`, `terraform.tfvars` 사용 후 커밋 제외 |

## 2. .gitignore로 막힌 파일/디렉터리

다음은 **절대 커밋하지 않습니다**. 이미 무시 대상입니다.

- **환경 변수**: `.env`, `.env.*` (단, `.env.example`만 예외로 커밋)
- **Terraform**: `terraform/terraform.tfvars`, `terraform/*.auto.tfvars`
- **K8s 시크릿**: `k8s/config/secrets.yaml`
- **Helm 로컬 오버라이드**: `**/values-*-local.yaml`, `**/*-local.yaml`, `**/*internal*.yaml`
- **기타**: `**/secrets/*.yaml` (예: `*.example.yaml`만 커밋), `local-data/`, `*_analysis.json` 등

## 3. 실제 값을 넣는 방법 (권장)

- **앱 환경 변수**: `.env`에만 넣고, 저장소에는 `.env.example`(플레이스홀더)만 둡니다.
- **Terraform**: `terraform.tfvars`에 실제 계정 ID·리소스 ID를 넣고, 저장소에는 `terraform.tfvars.example`만 커밋합니다.
- **Kubernetes**: `kubectl create secret`, Vault, External Secrets 등으로 시크릿을 주입하고, 저장소에는 `k8s/config/secrets.example.yaml`만 둡니다.
- **Helm**: 실제 계정/역할/도메인은 `--set`, `values-*-local.yaml`(커밋 제외) 또는 CI/배포 시 주입합니다.

## 4. 기존에 이미 커밋된 파일 정리 (한 번만 실행)

아래 파일이 이전에 커밋된 상태라면, **실제 값이 들어 있지 않을 때만** 추적 해제할 수 있습니다.

```bash
# 실제 값이 들어 있지 않은 경우에만 실행
git rm --cached k8s/config/secrets.yaml 2>/dev/null || true
git rm --cached terraform/terraform.tfvars 2>/dev/null || true
```

이후에는 `secrets.yaml`, `terraform.tfvars`를 로컬에서만 사용하고, 저장소에는 `*.example` 파일만 푸시합니다.

## 5. 보안 원칙 (CLAUDE.md·프로젝트 규칙과 동일)

- **비밀/키 하드코딩 금지**: `os.getenv()`, 환경 변수, K8s Secret 사용.
- **외부 입력 검증**: 화이트리스트 기반 검증.
- **Python**: `logging` 사용, `eval`/`exec`/`pickle` 사용 금지.

이 문서는 DevSecOps 관점에서 개인정보 및 내부 정보가 GitHub에 올라가지 않도록 구성한 내용입니다.
