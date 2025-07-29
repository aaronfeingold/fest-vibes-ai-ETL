variable "database_url" {
  description = "PostgreSQL database connection URL"
  type        = string
  sensitive   = true
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
  sensitive   = true
}

variable "google_maps_api_key" {
  description = "Google Maps API key for geocoding"
  type        = string
  sensitive   = true
  default     = ""
}

variable "base_url" {
  description = "Base URL for the website to scrape"
  type        = string
  default     = "https://www.wwoz.org"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for storing ETL pipeline data"
  type        = string
  default     = "fest-vibes-ai-etl-pipeline-data"
}

variable "image_version" {
  description = "Container image tag - can be commit SHA (commit-abc123), version (v1.2.3), or latest"
  type        = string
  default     = "latest"
}
