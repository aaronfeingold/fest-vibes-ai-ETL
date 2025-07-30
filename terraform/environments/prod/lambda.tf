# Lambda functions for the ETL pipeline components
import {
  to = aws_lambda_function.param_generator
  id = "fest-vibes-ai-param_generator"
}

import {
  to = aws_lambda_function.extractor
  id = "fest-vibes-ai-extractor"
}

import {
  to = aws_lambda_function.loader
  id = "fest-vibes-ai-loader"
}

import {
  to = aws_lambda_function.cache_manager
  id = "fest-vibes-ai-cache_manager"
}

# Date Range Generator Lambda
resource "aws_lambda_function" "param_generator" {
  function_name = "fest-vibes-ai-param_generator"
  description   = "Generates date ranges for ETL pipeline"
  role          = aws_iam_role.lambda_execution_role.arn
  package_type  = "Image"
  image_uri     = var.param_generator_image_digest != "" ? "${aws_ecr_repository.param_generator.repository_url}@${var.param_generator_image_digest}" : "${aws_ecr_repository.param_generator.repository_url}:${var.image_version}"
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      BASE_URL = var.base_url
    }
  }

  tags = {
    Name        = "fest-vibes-ai-param_generator"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

# Extractor Lambda
resource "aws_lambda_function" "extractor" {
  function_name = "fest-vibes-ai-extractor"
  description   = "Extracts event data from website"
  role          = aws_iam_role.lambda_execution_role.arn
  package_type  = "Image"
  image_uri     = var.extractor_image_digest != "" ? "${aws_ecr_repository.extractor.repository_url}@${var.extractor_image_digest}" : "${aws_ecr_repository.extractor.repository_url}:${var.image_version}"
  timeout       = 300
  memory_size   = 1024

  environment {
    variables = {
      BASE_URL = var.base_url
      S3_BUCKET_NAME = aws_s3_bucket.data_bucket.id
      S3_REGION = var.s3_region
      USER_AGENT = var.user_agent
      GOOGLE_MAPS_API_KEY = var.google_maps_api_key
    }
  }

  tags = {
    Name        = "fest-vibes-ai-extractor"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

# Loader Lambda
resource "aws_lambda_function" "loader" {
  function_name = "fest-vibes-ai-loader"
  description   = "Loads data from S3 to database"
  role          = aws_iam_role.lambda_execution_role.arn
  package_type  = "Image"
  image_uri     = var.loader_image_digest != "" ? "${aws_ecr_repository.loader.repository_url}@${var.loader_image_digest}" : "${aws_ecr_repository.loader.repository_url}:${var.image_version}"
  timeout       = 300
  memory_size   = 1024

  environment {
    variables = {
      PG_DATABASE_URL = var.database_url
      S3_BUCKET_NAME  = aws_s3_bucket.data_bucket.id
      S3_REGION = var.s3_region
      DB_ECHO = var.db_echo
      DB_POOL_SIZE = var.db_pool_size
      DB_MAX_OVERFLOW = var.db_max_overflow
      DB_POOL_TIMEOUT = var.db_pool_timeout
    }
  }

  tags = {
    Name        = "fest-vibes-ai-loader"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

# Cache Manager Lambda
resource "aws_lambda_function" "cache_manager" {
  function_name = "fest-vibes-ai-cache_manager"
  description   = "Updates Redis cache with event data"
  role          = aws_iam_role.lambda_execution_role.arn
  package_type  = "Image"
  image_uri     = var.cache_manager_image_digest != "" ? "${aws_ecr_repository.cache_manager.repository_url}@${var.cache_manager_image_digest}" : "${aws_ecr_repository.cache_manager.repository_url}:${var.image_version}"
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      REDIS_URL = var.redis_url
      PG_DATABASE_URL = var.database_url
      DB_ECHO = var.db_echo
      DB_POOL_SIZE = var.db_pool_size
      DB_MAX_OVERFLOW = var.db_max_overflow
      DB_POOL_TIMEOUT = var.db_pool_timeout
      REDIS_SOCKET_TIMEOUT = var.redis_socket_timeout
      REDIS_SOCKET_CONNECT_TIMEOUT = var.redis_socket_connect_timeout
      REDIS_RETRY_ON_TIMEOUT = var.redis_retry_on_timeout
      REDIS_DECODE_RESPONSES = var.redis_decode_responses
    }
  }

  tags = {
    Name        = "fest-vibes-ai-cache_manager"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}
