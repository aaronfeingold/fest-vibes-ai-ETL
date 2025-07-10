# Step Function for ETL pipeline orchestration
resource "aws_sfn_state_machine" "etl_pipeline" {
  name     = "fest-vibes-ai-etl-pipeline"
  role_arn = aws_iam_role.step_function_role.arn

  definition = jsonencode({
    Comment = "ETL Pipeline for Fest Vibes AI"
    StartAt = "GenerateDateRange"
    States = {
      "GenerateDateRange" = {
        Type = "Task"
        Resource = aws_lambda_function.date_range_generator.invoke_arn
        Parameters = {
          days_ahead = 30
        }
        ResultPath = "$.dateRange"
        Next = "ProcessDateRange"
      }
      "ProcessDateRange" = {
        Type = "Map"
        ItemsPath = "$.dateRange.dates"
        MaxConcurrency = 5
        Iterator = {
          StartAt = "ScraperTask"
          States = {
            "ScraperTask" = {
              Type = "Task"
              Resource = aws_lambda_function.scraper.invoke_arn
              Parameters = {
                queryStringParameters = {
                  "date.$" = "$"
                }
              }
              ResultPath = "$.scraperResult"
              Next = "CheckScraperStatus"
            }
            "CheckScraperStatus" = {
              Type = "Choice"
              Choices = [
                {
                  Variable = "$.scraperResult.statusCode"
                  NumericEquals = 200
                  Next = "LoaderTask"
                }
              ]
              Default = "ScraperFailed"
            }
            "ScraperFailed" = {
              Type = "Fail"
              Error = "ScraperTaskFailed"
              Cause = "Scraper task returned non-200 status code"
            }
            "LoaderTask" = {
              Type = "Task"
              Resource = aws_lambda_function.loader.invoke_arn
              Parameters = {
                s3_key = "$.scraperResult.body.s3_url"
              }
              ResultPath = "$.loaderResult"
              Next = "CheckLoaderStatus"
            }
            "CheckLoaderStatus" = {
              Type = "Choice"
              Choices = [
                {
                  Variable = "$.loaderResult.statusCode"
                  NumericEquals = 200
                  Next = "CacheTask"
                }
              ]
              Default = "LoaderFailed"
            }
            "LoaderFailed" = {
              Type = "Fail"
              Error = "LoaderTaskFailed"
              Cause = "Loader task returned non-200 status code"
            }
            "CacheTask" = {
              Type = "Task"
              Resource = aws_lambda_function.cache_manager.invoke_arn
              Parameters = {
                date = "$"
              }
              ResultPath = "$.cacheResult"
              Next = "CheckCacheStatus"
            }
            "CheckCacheStatus" = {
              Type = "Choice"
              Choices = [
                {
                  Variable = "$.cacheResult.statusCode"
                  NumericEquals = 200
                  Next = "Success"
                }
              ]
              Default = "CacheFailed"
            }
            "CacheFailed" = {
              Type = "Fail"
              Error = "CacheTaskFailed"
              Cause = "Cache task returned non-200 status code"
            }
            "Success" = {
              Type = "Succeed"
            }
          }
        }
        End = true
      }
    }
  })

  tags = {
    Name        = "fest-vibes-ai-etl-pipeline"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

# IAM role for Step Function
resource "aws_iam_role" "step_function_role" {
  name = "fest-vibes-ai-step-function-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "fest-vibes-ai-step-function-role"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

# Policy for Step Function to invoke Lambda
resource "aws_iam_policy" "step_function_lambda" {
  name        = "fest-vibes-ai-step-function-lambda"
  description = "Allows Step Function to invoke Lambda functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.date_range_generator.arn,
          aws_lambda_function.scraper.arn,
          aws_lambda_function.loader.arn,
          aws_lambda_function.cache_manager.arn
        ]
      }
    ]
  })
}

# Attach policy to Step Function role
resource "aws_iam_role_policy_attachment" "step_function_lambda" {
  role       = aws_iam_role.step_function_role.name
  policy_arn = aws_iam_policy.step_function_lambda.arn
}
