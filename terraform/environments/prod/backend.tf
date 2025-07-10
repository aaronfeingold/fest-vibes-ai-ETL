terraform {
  backend "s3" {
    bucket         = "fest-vibes-ai-ETL"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "fest-vibes-ai-ETL-terraform-locks"
  }
}
