# Fest Vibes AI ETL Pipeline

## Overview
This project implements an ETL (Extract, Transform, Load) pipeline for scraping event data from a sample website, processing the data, and making it available via a cache and database.

### System Design
The project is built with a microservices architecture based on AWS Lambda functions and Step Functions for orchestration. The components are:

1. Date Range Generator: Generates a range of dates to scrape
2. Scraper: Extracts event data from the website and stores it in S3
3. Loader: Loads event data from S3 into the PostgreSQL database
4. Cache Manager: Updates Redis cache with event data from the database

### ETL Flow
1. The Step Function workflow starts with the Date Range Generator to get dates to process
2. For each date, the workflow executes:
    a. Scraper component to extract data and store it in S3
    b. Loader component to process S3 data and insert into the database
    c. Cache Manager to update the Redis cache with processed data

## Prerequisites
- AWS CLI configured with appropriate permissions
- Python 3.11.10
  - recommended: use `pyenv`
  - `pipenv`
- PostgreSQL
- Docker
- Redis instance
- Poetry for dependency management

## Installation

### Recommended: `pyenv`
- `pyenv` is a simple, powerful tool for managing multiple versions of Python. Follow the instructions below to install `pyenv` on your system.
- Check out [this project](https://github.com/aaronfeingold/ajf-fedora-workstation-ansible?tab=readme-ov-file#fedora-workstation-ansible) for an automated installation via Ansible.

#### Linux:
```sh
# Install dependencies
sudo apt-get update
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev \
python-openssl git

# Install pyenv
curl https://pyenv.run | bash

# Add pyenv to bash so that it loads every time you open a terminal
echo -e '\n# Pyenv Configuration' >> ~/.bashrc
echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
source ~/.bashrc
```

#### Install Python 3.11.10 using `pyenv`
```sh
pyenv install 3.11.10
pyenv global 3.11.10
```

### Install `pipenv`
- `pipenv` is a tool that aims to bring the best of all packaging worlds (bundled, development, and deployment) to the Python world. It automatically creates and manages a virtual environment for your projects, as well as adds/removes packages from your Pipfile as you install/uninstall packages.

```sh
pip install pipenv
```

### Clone the Repository
```sh
git clone https://github.com/aaronfeingold/ajf-live-re-wire.git
cd ajf-live-re-wire
```

## Usage

### Configuration
The application uses environment variables for configuration. Key configuration items:

- `BASE_URL`: Base URL for the website to scrape
- `PG_DATABASE_URL`: PostgreSQL database URL
- `REDIS_URL`: Redis instance URL
- `S3_BUCKET_NAME`: S3 bucket for storing scraped data
- `GOOGLE_MAPS_API_KEY`: API key for geocoding services
See src/shared/config.py for all available configuration options.

### Activate the Pipenv Shell
```sh
pipenv shell
```

### Install Dependencies
```sh
pipenv install
```

### Use pre-commit hooks
1. Install the git hooks:
```sh
pre-commit install
```
2. Run pre-commit on all files:
```sh
pre-commit run --all-files
```

## Database Migrations

The project includes database migrations to optimize performance and add new features. Migrations are stored in `src/shared/db/migrations/`.

### Running Migrations

**Prerequisites:**
- Database connection configured in `PG_DATABASE_URL`
- PostgreSQL client (`psql`) installed
- Database server accessible

**Run a specific migration:**
```sh
# Run the concurrency optimization migration
psql $PG_DATABASE_URL -f src/shared/db/migrations/add_concurrency_indexes.sql

# Or if using connection parameters:
psql -h hostname -p port -U username -d database -f src/shared/db/migrations/add_concurrency_indexes.sql
```

**Check migration status:**
```sh
# List all indexes to verify migration completed
psql $PG_DATABASE_URL -c "\d+ artists" -c "\d+ venues" -c "\d+ events"

# Check specific concurrency indexes
psql $PG_DATABASE_URL -c "SELECT indexname, tablename FROM pg_indexes WHERE indexname LIKE 'idx_%' ORDER BY tablename, indexname;"
```

**Important Notes:**
- All indexes use `CREATE INDEX CONCURRENTLY` for zero-downtime deployment
- Migrations are idempotent and safe to run multiple times
- The concurrency optimization migration adds critical indexes to prevent deadlocks with concurrent Lambda executions

## Local Development & Testing
### Test Suites
**Ensure the PYTHONPATH is set**
```sh
PYTHONPATH=. pytest tests/simple_tests.py
```

### Test Run
```sh
poetry run python -m src.scraper.app
poetry run python -m src.loader.app
poetry run python -m src.cache_manager.app
poetry run python -m src.date_range_generator.app
```

### Python Debugger
**Python: Select Interpreter**

- Press Cmd+Shift+P (Mac) or Ctrl+Shift+P (Windows/Linux)
- Type "Python: Select Interpreter"
- Look for the interpreter that points to your Pipenv virtual environment (it should be something like ~/.local/share/virtualenvs/your-project-name-xxxxx/bin/python)

**Run Python: Pipenv Debug with VSCode's Debugger tool**

### Docker Image
- Lambda Invocation:
```
# build and tag locally
docker build --target dev -t ajf-live-re-wire:dev .
# create new container from latest dev build
docker run \
  --network host \
  -v ~/.aws:/root/.aws \
  -e PG_DATABASE_URL=postgresql://{username}:{password}@localhost:{db_port}/{db_name} \
  -e BASE_URL="https://www.wwoz.org" \
  -e GOOGLE_MAPS_API_KEY=a_super_secret_thing \
  -e S3_BUCKET_NAME=your-data-bucket-name \
  -e REDIS_URL=rediss://username:password@hostname:port \
  ajf-live-re-wire:dev
```
- Note: `rediss` with 2x 's' is not a typo. This indicates ssl, which is the case for the hosted Upstash service.
#### Redis Configuration for Local Development

1. **Configure Redis to Accept External Connections**
   ```bash
   # Edit Redis configuration
   sudo nano /etc/redis/redis.conf

   # Find and modify the bind line to:
   bind 0.0.0.0

   # Restart Redis
   sudo systemctl restart redis
   ```

2. **Verify Redis is Running**
   ```bash
   # Check Redis status
   sudo systemctl status redis

   # Test Redis connection
   redis-cli ping
   ```

3. **Querying Redis Data**
   ```bash
   # Connect to Redis CLI
   redis-cli

   # List all keys (our events are stored with pattern "events:YYYY-MM-DD")
   KEYS "events:*"

   # Get a specific event date's data
   GET "events:2024-03-20"

   # Monitor Redis in real-time
   redis-cli monitor

   # Check Redis memory usage
   redis-cli info memory

   # Get all keys with their TTL (time to live)
   redis-cli --scan --pattern "events:*" | while read key; do echo "$key: $(redis-cli ttl "$key")"; done
   ```

4. **Debugging Redis Connection Issues**

   a. **From Host Machine:**
   ```bash
   # Test basic Redis connectivity
   redis-cli ping

   # Check Redis is listening on all interfaces
   netstat -tulpn | grep 6379
   ```

   b. **From Docker Container:**
   ```bash
   # Enter the container
   docker exec -it <container_id> bash

   # Test Redis connection using Python
   python3
   >>> import redis
   >>> r = redis.Redis(host='localhost', port=6379, decode_responses=True)
   >>> print(r.ping())  # Should return True
   ```

   c. **Common Issues:**
   - If `redis-cli` is not found in container: This is expected as we don't install it in the container
   - Connection refused: Check Redis is running and configured to accept external connections
   - Timeout: Verify network settings and firewall rules
   - Authentication error: Check if Redis password is required and properly configured

4. **Network Configuration**
   - Using `--network host` allows the container to access Redis on localhost
   - For non-host networking, use the host machine's IP address instead of localhost
   - Ensure no firewall rules are blocking Redis port (6379)

## Deployment

### Prerequisites

Before deploying, you need to set up the following resources and GitHub Secrets:

#### 1. Terraform Backend Setup (Required)

The deployment uses Terraform to manage infrastructure. You must create these resources manually before the first deployment:

**S3 Bucket for Terraform State:**
```bash
# Create the S3 bucket for Terraform state
aws s3 mb s3://<tf-state-bucket-name>--region us-east-1

# Enable versioning on the bucket
aws s3api put-bucket-versioning --bucket <tf-state-bucket-name> --versioning-configuration Status=Enabled

# Enable encryption on the S3 bucket
aws s3api put-bucket-encryption \
  --bucket <tf-state-bucket-name> \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }
    ]
  }'

# Block public access on the S3 bucket
aws s3api put-public-access-block \
  --bucket <tf-state-bucket-name> \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

**DynamoDB Table for State Locking:**
```bash
# Create the DynamoDB table for Terraform state locking
aws dynamodb create-table \
  --table-name <tf-state-bucket-name>-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

#### 2. GitHub Secrets Setup

Add the following secrets to your GitHub repository (Settings > Secrets and variables > Actions > Secrets):

**AWS Credentials (required):**
- `AWS_ACCESS_KEY_ID` - Your AWS access key
- `AWS_SECRET_ACCESS_KEY` - Your AWS secret key

**Database & Cache (required):**
- `PG_DATABASE_URL` - PostgreSQL connection string (e.g., `postgresql://user:pass@host:5432/db`)
- `REDIS_URL` - Redis connection string (e.g., `redis://user:pass@host:6379`)

**Infrastructure Configuration (optional):**
- `S3_BUCKET_NAME` - S3 bucket name for data storage (defaults to `fest-vibes-ai-etl-pipeline-data`)
- `BASE_URL` - Base URL for scraping (defaults to `https://www.wwoz.org`)

**External APIs (optional):**
- `GOOGLE_MAPS_API_KEY` - Google Maps API key for geocoding

#### 3. GitHub Variables Setup (Optional)

Add the following variables to your GitHub repository (Settings > Secrets and variables > Actions > Variables):

**Terraform Backend Configuration:**
- `TERRAFORM_BACKEND_BUCKET` - S3 bucket name for Terraform state (defaults to `fest-vibes-ai-et-tf-statel`)

These variables are used to configure the Terraform backend and can be changed without updating the workflow code.

### Manual Terraform Deployment

If you need to deploy manually or debug Terraform issues, you can run Terraform directly:

```bash
# Navigate to the production environment
cd terraform/environments/prod

# Make sure you have your tfvars file
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your actual values

# Initialize Terraform with backend configuration
terraform init \
  -backend-config="bucket=YOUR_TERRAFORM_BACKEND_BUCKET" \
  -backend-config="key=prod/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="encrypt=true"

# Review the planned changes
terraform plan   # You'll see lots of "will be imported" messages

# Apply the changes
terraform apply  # This imports everything into your state bucket
```

**Note:** Replace `YOUR_TERRAFORM_BACKEND_BUCKET` with your actual Terraform state bucket name.

### GitHub Actions Deployment

The GitHub Actions workflow automates the complete deployment process:

1. **Test Phase**
   - Runs pytest on the test suite
   - Ensures code quality before deployment

2. **Build & Push Phase**
   - Builds Docker images for all 4 components:
     - `extractor` - Extracts event data from websites
     - `loader` - Processes S3 data into PostgreSQL database
     - `cache_manager` - Updates Redis cache with latest data
     - `date_range_generator` - Generates date ranges for processing
   - Pushes images to AWS ECR with both commit SHA and `latest` tags

3. **Deploy Phase**
   - Runs `terraform apply` to create/update infrastructure:
     - S3 buckets (state storage + data storage)
     - IAM roles and policies
     - Lambda functions using the Docker images
     - Step Function for orchestration

### Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub Push   │───▶│  GitHub Actions │───▶│   AWS ECR       │
│   (main branch) │    │   (CI/CD)       │    │   (Docker Images)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Terraform     │◀───│   Lambda        │◀───│   Step Function │
│   (Infrastructure)│    │   Functions     │    │   (Orchestrator) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   S3 Bucket     │    │   PostgreSQL    │    │   Redis Cache   │
│   (Data Storage)│    │   (Vector DB)   │    │   (API Cache)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │   Next.js App   │
                        │   (Frontend)    │
                        └─────────────────┘
```

### ETL Pipeline Flow

The Step Function orchestrates the complete ETL pipeline:

1. **Date Range Generator** → Generates dates to process (next 30 days)
2. **Extractor** → Extracts event data for each date and stores in S3
3. **Loader** → Processes S3 data into PostgreSQL (with vector embeddings)
4. **Cache Manager** → Queries database and updates Redis cache

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Date Generator  │───▶│   Extractor     │───▶│     Loader      │───▶│  Cache Manager  │
│ (Lambda)        │    │   (Lambda)      │    │   (Lambda)      │    │   (Lambda)      │
│                 │    │                 │    │                 │    │                 │
│ • Generate      │    │ • Extract HTML  │    │ • Read S3 data  │    │ • Query DB      │
│   date ranges   │    │ • Parse events  │    │ • Vectorize     │    │ • Update Redis  │
│ • Pass to       │    │ • Store in S3   │    │ • Store in DB   │    │ • Cache results │
│   extractor     │    │ • Trigger loader│    │ • Trigger cache │    │ • Ready for API │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Date List     │    │   S3 Bucket     │    │   PostgreSQL    │    │   Redis Cache   │
│   (JSON Array)  │    │   (Raw Data)    │    │   (Vector DB)   │    │   (API Data)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

1. **Input**: Date ranges generated by the date generator
2. **Extract**: Scraper pulls event data from websites for each date
3. **Transform**: Loader processes raw data, creates vector embeddings, and stores in PostgreSQL
4. **Load**: Cache manager queries the database and updates Redis with the latest data
5. **Output**: Next.js app consumes Redis cache for fast API responses

### Infrastructure Components

- **S3 Buckets**:
  - `fest-vibes-ai-ETL` - Terraform state storage
  - `fest-vibes-ai-data` - Raw scraped data storage

- **Lambda Functions**:
  - `fest-vibes-ai-param_generator`
  - `fest-vibes-ai-extractor`
  - `fest-vibes-ai-loader`
  - `fest-vibes-ai-cache_manager`

- **Step Function**: `fest-vibes-ai-etl-pipeline` - Orchestrates the entire workflow

- **Database**: PostgreSQL with vector extensions for similarity search

- **Cache**: Redis for fast API responses

### Monitoring & Debugging

- **CloudWatch Logs**: Each Lambda function logs to CloudWatch
- **Step Function Console**: Monitor ETL pipeline execution
- **S3 Console**: View stored data and artifacts
- **Terraform State**: Track infrastructure changes

The workflow ensures consistent deployments and reduces manual intervention in the deployment process.
