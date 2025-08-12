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
        ResultPath = "$.params"
        Next = "CheckParamGeneratorStatus"
      }
      "CheckParamGeneratorStatus" = {
        Type = "Choice"
        Choices = [
          {
            Variable = "$.params.statusCode"
            NumericEquals = 200
            Next = "ProcessParams"
          }
        ]
        Default = "ParamGeneratorFailed"
      }
      "ParamGeneratorFailed" = {
        Type = "Fail"
        Error = "ParamGeneratorTaskFailed"
        Cause = "Parameter generator task returned non-200 status code"
      }
      "ProcessParams" = {
        Type = "Map"
        ItemsPath = "$.params.body.dates"
        MaxConcurrency = 5
        ToleratedFailurePercentage = 10
        Iterator = {
          StartAt = "InitializeState"
          States = {
            "InitializeState" = {
              Type = "Pass"
              Parameters = {
                "date.$" = "$",
                "state": {}
              }
              Next = "ExtractorTask"
            },
            "ExtractorTask" = {
              Type = "Task"
              Resource = aws_lambda_function.extractor.arn
              Parameters = {
                queryStringParameters = {
                  "date.$" = "$.date"
                }
              }
              ResultPath = "$.state.extractorResult"
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
                  Variable = "$.state.extractorResult.statusCode"
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
                "s3_key.$" = "$.state.extractorResult.body.s3_key"
                "date.$" = "$.date"
                "extractorData.$" = "$.state.extractorResult"
              }
              ResultPath = "$.state.loaderResult"
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
                  Variable = "$.state.loaderResult.statusCode"
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
                "extractorData.$" = "$.state.extractorResult"
                "loaderData.$" = "$.state.loaderResult"
              }
              ResultPath = "$.state.cacheResult"
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
                  Variable = "$.state.cacheResult.statusCode"
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

# CloudWatch Event Rule to trigger Step Function daily at 3 AM CST/CDT
resource "aws_cloudwatch_event_rule" "daily_etl_trigger" {
  name                = "fest-vibes-ai-daily-etl-trigger"
  description         = "Triggers ETL pipeline daily at 3 AM CST/CDT"
  # UTC equivalent: 3 AM CST = 9 AM UTC (CST is UTC-6), 3 AM CDT = 8 AM UTC (CDT is UTC-5)
  # Using 8 AM UTC to account for CDT (daylight saving time)
  schedule_expression = "cron(0 8 * * ? *)"

  tags = {
    Name        = "fest-vibes-ai-daily-etl-trigger"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

# CloudWatch Event Target - Step Function
resource "aws_cloudwatch_event_target" "step_function_target" {
  rule      = aws_cloudwatch_event_rule.daily_etl_trigger.name
  target_id = "TriggerStepFunction"
  arn       = aws_sfn_state_machine.etl_pipeline.arn
  role_arn  = aws_iam_role.eventbridge_step_function_role.arn

  # Input to pass to Step Function (empty object since param generator creates the dates)
  input = jsonencode({})
}

# IAM Role for EventBridge to invoke Step Function
resource "aws_iam_role" "eventbridge_step_function_role" {
  name = "fest-vibes-ai-eventbridge-step-function-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "fest-vibes-ai-eventbridge-step-function-role"
    Environment = "prod"
    Project     = "fest-vibes-ai"
  }
}

# IAM Policy for EventBridge to invoke Step Function
resource "aws_iam_policy" "eventbridge_step_function" {
  name        = "fest-vibes-ai-eventbridge-step-function"
  description = "Allows EventBridge to start Step Function executions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = [
          aws_sfn_state_machine.etl_pipeline.arn
        ]
      }
    ]
  })
}

# Attach policy to EventBridge role
resource "aws_iam_role_policy_attachment" "eventbridge_step_function" {
  role       = aws_iam_role.eventbridge_step_function_role.name
  policy_arn = aws_iam_policy.eventbridge_step_function.arn
}
