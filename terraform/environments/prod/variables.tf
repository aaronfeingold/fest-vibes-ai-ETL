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
  description = "Container image tag - should be semantic version like v1.2.3"
  type        = string
  default     = "latest"
}

variable "param_generator_image_digest" {
  description = "SHA256 digest of param_generator container image"
  type        = string
  default     = ""
}

variable "extractor_image_digest" {
  description = "SHA256 digest of extractor container image"
  type        = string
  default     = ""
}

variable "loader_image_digest" {
  description = "SHA256 digest of loader container image"
  type        = string
  default     = ""
}

variable "cache_manager_image_digest" {
  description = "SHA256 digest of cache_manager container image"
  type        = string
  default     = ""
}

variable "user_agent" {
  description = "User agent string for web scraping requests"
  type        = string
  default     = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

variable "s3_region" {
  description = "AWS S3 region"
  type        = string
  default     = "us-east-1"
}

variable "db_echo" {
  description = "Enable database query logging for debugging"
  type        = bool
  default     = false
}

variable "db_pool_size" {
  description = "Database connection pool size"
  type        = number
  default     = 5
}

variable "db_max_overflow" {
  description = "Database connection pool max overflow"
  type        = number
  default     = 10
}

variable "db_pool_timeout" {
  description = "Database connection pool timeout in seconds"
  type        = number
  default     = 30
}

variable "redis_socket_timeout" {
  description = "Redis socket timeout in seconds"
  type        = number
  default     = 5
}

variable "redis_socket_connect_timeout" {
  description = "Redis socket connection timeout in seconds"
  type        = number
  default     = 5
}

variable "redis_retry_on_timeout" {
  description = "Enable Redis retry on timeout"
  type        = bool
  default     = true
}

variable "redis_decode_responses" {
  description = "Enable Redis response decoding"
  type        = bool
  default     = true
}
