# CloudWatch Log Groups for Lambda functions with retention policies

# Import existing log groups into Terraform state
import {
  to = aws_cloudwatch_log_group.param_generator
  id = "/aws/lambda/fest-vibes-ai-param_generator"
}

import {
  to = aws_cloudwatch_log_group.extractor
  id = "/aws/lambda/fest-vibes-ai-extractor"
}

import {
  to = aws_cloudwatch_log_group.loader
  id = "/aws/lambda/fest-vibes-ai-loader"
}

import {
  to = aws_cloudwatch_log_group.cache_manager
  id = "/aws/lambda/fest-vibes-ai-cache_manager"
}

# Param Generator Lambda Log Group
resource "aws_cloudwatch_log_group" "param_generator" {
  name              = "/aws/lambda/fest-vibes-ai-param_generator"
  retention_in_days = 14

  tags = {
    Name        = "fest-vibes-ai-param_generator-logs"
    Environment = "prod"
    Project     = "fest-vibes-ai"
    Component   = "lambda-logs"
  }
}

# Extractor Lambda Log Group
resource "aws_cloudwatch_log_group" "extractor" {
  name              = "/aws/lambda/fest-vibes-ai-extractor"
  retention_in_days = 14

  tags = {
    Name        = "fest-vibes-ai-extractor-logs"
    Environment = "prod"
    Project     = "fest-vibes-ai"
    Component   = "lambda-logs"
  }
}

# Loader Lambda Log Group
resource "aws_cloudwatch_log_group" "loader" {
  name              = "/aws/lambda/fest-vibes-ai-loader"
  retention_in_days = 14

  tags = {
    Name        = "fest-vibes-ai-loader-logs"
    Environment = "prod"
    Project     = "fest-vibes-ai"
    Component   = "lambda-logs"
  }
}

# Cache Manager Lambda Log Group
resource "aws_cloudwatch_log_group" "cache_manager" {
  name              = "/aws/lambda/fest-vibes-ai-cache_manager"
  retention_in_days = 14

  tags = {
    Name        = "fest-vibes-ai-cache_manager-logs"
    Environment = "prod"
    Project     = "fest-vibes-ai"
    Component   = "lambda-logs"
  }
}
