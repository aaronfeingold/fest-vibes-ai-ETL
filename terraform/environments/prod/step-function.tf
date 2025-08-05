# Import existing step function role
import {
  to = aws_iam_role.step_function_role
  id = "fest-vibes-ai-step-function-role"
}

# Import existing step function state machine
import {
  to = aws_sfn_state_machine.etl_pipeline
  id = "arn:aws:states:us-east-1:937355130135:stateMachine:fest-vibes-ai-etl-pipeline"
}

# Step Function for ETL pipeline orchestration
resource "aws_sfn_state_machine" "etl_pipeline" {
  name     = "fest-vibes-ai-etl-pipeline"
  role_arn = aws_iam_role.step_function_role.arn

  definition = jsonencode({
    Comment = "ETL Pipeline for Fest Vibes AI"
    StartAt = "GenerateParams"
    States = {
      "GenerateParams" = {
        Type = "Task"
        Resource = aws_lambda_function.param_generator.arn
        Parameters = {
          days_ahead = 30
        }
        ResultPath = "$.dateRange"
        Next = "CheckParamGeneratorStatus"
      }
      "CheckParamGeneratorStatus" = {
        Type = "Choice"
        Choices = [
          {
            Variable = "$.dateRange.statusCode"
            NumericEquals = 200
            Next = "ProcessDateRangeParam"
          }
        ]
        Default = "ParamGeneratorFailed"
      }
      "ParamGeneratorFailed" = {
        Type = "Fail"
        Error = "ParamGeneratorTaskFailed"
        Cause = "Parameter generator task returned non-200 status code"
      }
      "ProcessDateRangeParam" = {
        Type = "Map"
        ItemsPath = "$.dateRange.body.dates"
        MaxConcurrency = 5
        ToleratedFailurePercentage = 10
        Parameters = {
          "date.$" = "$"
          "iterationIndex.$" = "$$.Map.Item.Index"
        }
        Iterator = {
          StartAt = "ExtractorTask"
          States = {
            "ExtractorTask" = {
              Type = "Task"
              Resource = aws_lambda_function.extractor.arn
              Parameters = {
                queryStringParameters = {
                  "date.$" = "$.date"
                }
              }
              ResultPath = "$.extractorResult"
              Retry = [
                {
                  ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"]
                  IntervalSeconds = 2
                  MaxAttempts = 3
                  BackoffRate = 2.0
                }
              ]
              Next = "CheckExtractorStatus"
            }
            "CheckExtractorStatus" = {
              Type = "Choice"
              Choices = [
                {
                  Variable = "$.extractorResult.statusCode"
                  NumericEquals = 200
                  Next = "LoaderTask"
                }
              ]
              Default = "ExtractorFailed"
            }
            "ExtractorFailed" = {
              Type = "Fail"
              Error = "ExtractorTaskFailed"
              Cause = "Extractor task returned non-200 status code"
            }
            "LoaderTask" = {
              Type = "Task"
              Resource = aws_lambda_function.loader.arn
              Parameters = {
                "s3_key.$" = "$.extractorResult.body.s3_url"
              }
              ResultPath = "$.loaderResult"
              Retry = [
                {
                  ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"]
                  IntervalSeconds = 2
                  MaxAttempts = 3
                  BackoffRate = 2.0
                }
              ]
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
              Resource = aws_lambda_function.cache_manager.arn
              Parameters = {
                "date.$" = "$.date"
              }
              ResultPath = "$.cacheResult"
              Retry = [
                {
                  ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"]
                  IntervalSeconds = 2
                  MaxAttempts = 3
                  BackoffRate = 2.0
                }
              ]
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

# Import existing IAM policy
import {
  to = aws_iam_policy.step_function_lambda
  id = "arn:aws:iam::937355130135:policy/fest-vibes-ai-step-function-lambda"
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
          aws_lambda_function.param_generator.arn,
          aws_lambda_function.extractor.arn,
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
