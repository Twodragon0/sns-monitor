{{/*
Expand the name of the chart.
*/}}
{{- define "sns-monitor.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "sns-monitor.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "sns-monitor.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "sns-monitor.labels" -}}
helm.sh/chart: {{ include "sns-monitor.chart" . }}
{{ include "sns-monitor.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "sns-monitor.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sns-monitor.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Pod Security Context
*/}}
{{- define "sns-monitor.podSecurityContext" -}}
runAsNonRoot: {{ .Values.security.podSecurityContext.runAsNonRoot }}
runAsUser: {{ .Values.security.podSecurityContext.runAsUser }}
runAsGroup: {{ .Values.security.podSecurityContext.runAsGroup }}
fsGroup: {{ .Values.security.podSecurityContext.fsGroup }}
seccompProfile:
  type: {{ .Values.security.podSecurityContext.seccompProfile.type }}
{{- end }}

{{/*
Container Security Context
*/}}
{{- define "sns-monitor.containerSecurityContext" -}}
allowPrivilegeEscalation: {{ .Values.security.containerSecurityContext.allowPrivilegeEscalation }}
readOnlyRootFilesystem: {{ .Values.security.containerSecurityContext.readOnlyRootFilesystem }}
capabilities:
  drop:
  {{- range .Values.security.containerSecurityContext.capabilities.drop }}
    - {{ . }}
  {{- end }}
{{- end }}
