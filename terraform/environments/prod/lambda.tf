# Lambda functions for the ETL pipeline components

# Date Range Generator Lambda
resource "aws_lambda_function" "date_range_generator" {
  function_name = "fest-vibes-ai-date-range-generator"
  description   = "Generates date ranges for ETL pipeline"
  role          = aws_iam_role.lambda_execution_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.date_range_generator.repository_url}:${var.image_version}"
  timeout       = 300
  memory_size   = 512

  # Prevent recreation if only image_uri changes
  lifecycle {
    ignore_changes = [image_uri]
  }

  environment {
    variables = {
      BASE_URL = var.base_url
    }
  }

  tags = {
    Name        = "fest-vibes-ai-date-range-generator"
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
  image_uri     = "${aws_ecr_repository.extractor.repository_url}:${var.image_version}"
  timeout       = 300
  memory_size   = 1024

  # Prevent recreation if only image_uri changes
  lifecycle {
    ignore_changes = [image_uri]
  }

  environment {
    variables = {
      BASE_URL = var.base_url
      S3_BUCKET_NAME = aws_s3_bucket.data_bucket.id
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
  image_uri     = "${aws_ecr_repository.loader.repository_url}:${var.image_version}"
  timeout       = 300
  memory_size   = 1024

  # Prevent recreation if only image_uri changes
  lifecycle {
    ignore_changes = [image_uri]
  }

  environment {
    variables = {
      PG_DATABASE_URL = var.database_url
      S3_BUCKET_NAME  = aws_s3_bucket.data_bucket.id
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
  function_name = "fest-vibes-ai-cache-manager"
  description   = "Updates Redis cache with event data"
  role          = aws_iam_role.lambda_execution_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.cache_manager.repository_url}:${var.image_version}"
  timeout       = 300
  memory_size   = 512

  # Prevent recreation if only image_uri changes
  lifecycle {
    ignore_changes = [image_uri]
  }

  environment {
    variables = {
      REDIS_URL = var.redis_url
      PG_DATABASE_URL = var.database_url
    }
  }

  tags = {
    Name        = "fest-vibes-ai-cache-manager"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}
