{{- define "odoo-instance.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "odoo-instance.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "odoo-instance.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "odoo-instance.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "odoo-instance.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: kodpm
{{- end }}

{{- define "odoo-instance.selectorLabels" -}}
app.kubernetes.io/name: {{ include "odoo-instance.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "odoo-instance.postgresHost" -}}
{{- if .Values.postgres.enabled }}
{{- printf "%s-postgres" (include "odoo-instance.fullname" .) }}
{{- else }}
{{- .Values.postgres.externalHost }}
{{- end }}
{{- end }}

{{- define "odoo-instance.odooImage" -}}
{{- if .Values.image.repository }}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | toString) }}
{{- else }}
{{- printf "odoo:%s" (.Values.odooVersion | toString | replace ".0" "") }}
{{- end }}
{{- end }}

{{- define "odoo-instance.confPath" -}}
{{- printf "%s/%s" .Values.confMount .Values.confName }}
{{- end }}

{{- define "odoo-instance.addonsPath" -}}
{{- $paths := list }}
{{- range .Values.addons.repos }}
{{- $paths = append $paths (printf "/mnt/extra-addons/%s" .name) }}
{{- end }}
{{- if .Values.addons.hostPath.enabled }}
{{- $root := printf "/mnt/extra-addons/%s" (default "developing" .Values.addons.hostPath.name) }}
{{- range .Values.addons.hostPath.extraPaths }}
{{- if hasPrefix "/" . }}
{{- $paths = append $paths . }}
{{- else }}
{{- $paths = append $paths (printf "%s/%s" $root .) }}
{{- end }}
{{- end }}
{{- end }}
{{- if not $paths }}
{{- .Values.extraAddons | default "/mnt/extra-addons" }}
{{- else }}
{{- join "," $paths }}
{{- end }}
{{- end }}
