# Import existing IAM resources
import {
  to = aws_iam_role.lambda_execution_role
  id = "fest-vibes-ai-lambda-execution-role"
}

import {
  to = aws_iam_policy.lambda_s3_access
  id = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/fest-vibes-ai-lambda-s3-access"
}

import {
  to = aws_iam_policy.lambda_ecr_access
  id = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/fest-vibes-ai-lambda-ecr-access"
}

# Get current AWS account ID for dynamic ARN construction
data "aws_caller_identity" "current" {}

# IAM role for Lambda execution
resource "aws_iam_role" "lambda_execution_role" {
  name = "fest-vibes-ai-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "fest-vibes-ai-lambda-execution-role"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Custom policy for S3 access
resource "aws_iam_policy" "lambda_s3_access" {
  name        = "fest-vibes-ai-lambda-s3-access"
  description = "Allows Lambda functions to access S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data_bucket.arn,
          "${aws_s3_bucket.data_bucket.arn}/*"
        ]
      }
    ]
  })
}

# Attach S3 access policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_s3" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_s3_access.arn
}

# Custom policy for ECR access
resource "aws_iam_policy" "lambda_ecr_access" {
  name        = "fest-vibes-ai-lambda-ecr-access"
  description = "Allows Lambda functions to pull from ECR"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach ECR access policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_ecr" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_ecr_access.arn
}
