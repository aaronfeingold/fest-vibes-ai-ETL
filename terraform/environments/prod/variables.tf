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
