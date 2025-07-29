# Import existing ECR repositories
import {
  to = aws_ecr_repository.extractor
  id = "fest-vibes-ai-extractor"
}

import {
  to = aws_ecr_repository.loader
  id = "fest-vibes-ai-loader"
}

import {
  to = aws_ecr_repository.cache_manager
  id = "fest-vibes-ai-cache-manager"
}

import {
  to = aws_ecr_repository.date_range_generator
  id = "fest-vibes-ai-param-generator"
}

# ECR repositories for Lambda functions with lifecycle policies

# Date Range Generator ECR Repository
resource "aws_ecr_repository" "date_range_generator" {
  name                 = "fest-vibes-ai-param-generator"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "fest-vibes-ai-param-generator"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

resource "aws_ecr_lifecycle_policy" "date_range_generator" {
  repository = aws_ecr_repository.date_range_generator.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the 3 most recent images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Extractor ECR Repository
resource "aws_ecr_repository" "extractor" {
  name                 = "fest-vibes-ai-extractor"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "fest-vibes-ai-extractor"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

resource "aws_ecr_lifecycle_policy" "extractor" {
  repository = aws_ecr_repository.extractor.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the 3 most recent images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Loader ECR Repository
resource "aws_ecr_repository" "loader" {
  name                 = "fest-vibes-ai-loader"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "fest-vibes-ai-loader"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

resource "aws_ecr_lifecycle_policy" "loader" {
  repository = aws_ecr_repository.loader.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the 3 most recent images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Cache Manager ECR Repository
resource "aws_ecr_repository" "cache_manager" {
  name                 = "fest-vibes-ai-cache-manager"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "fest-vibes-ai-cache-manager"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

resource "aws_ecr_lifecycle_policy" "cache_manager" {
  repository = aws_ecr_repository.cache_manager.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the 3 most recent images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
