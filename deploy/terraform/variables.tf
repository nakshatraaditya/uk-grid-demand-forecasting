variable "project_id" {
  description = "GCP project id that owns the Cloud Run service."
  type        = string
}

variable "region" {
  description = "GCP region for Artifact Registry and Cloud Run."
  type        = string
  default     = "europe-west2"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "grid-demand-api"
}

variable "ar_repo" {
  description = "Artifact Registry Docker repository id."
  type        = string
  default     = "griddemand"
}

variable "image_uri" {
  description = "Fully-qualified Artifact Registry image URI to deploy, e.g. europe-west2-docker.pkg.dev/PROJECT/griddemand/grid-demand-api:SHA."
  type        = string
}

variable "cpu" {
  description = "CPU limit per container instance."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory limit per container instance."
  type        = string
  default     = "2Gi"
}

variable "min_instances" {
  description = "Minimum warm instances (0 = scale-to-zero, accepts cold starts)."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Autoscaling ceiling."
  type        = number
  default     = 3
}

variable "concurrency" {
  description = "Max concurrent requests per instance."
  type        = number
  default     = 40
}

variable "allow_unauthenticated" {
  description = "Bind roles/run.invoker to allUsers so the API is publicly reachable."
  type        = bool
  default     = true
}
