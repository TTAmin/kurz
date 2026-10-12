{{- define "kurz.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "kurz.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "kurz.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{ include "kurz.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "kurz.selectorLabels" -}}
app.kubernetes.io/name: {{ include "kurz.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* The app's own pods and Service; the bundled Postgres carries component=database. */}}
{{- define "kurz.appSelectorLabels" -}}
{{ include "kurz.selectorLabels" . }}
app.kubernetes.io/component: app
{{- end }}

{{- define "kurz.image" -}}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{- define "kurz.postgresql.fullname" -}}
{{- printf "%s-postgresql" (include "kurz.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "kurz.databaseSecretName" -}}
{{- .Values.database.existingSecret | default (printf "%s-db" (include "kurz.fullname" .)) }}
{{- end }}

{{- define "kurz.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- with .Values.postgresql.auth }}
{{- printf "postgresql+psycopg://%s:%s@%s:5432/%s" .username .password (include "kurz.postgresql.fullname" $) .database }}
{{- end }}
{{- else }}
{{- required "database.url or database.existingSecret is required when postgresql.enabled is false" .Values.database.url }}
{{- end }}
{{- end }}
