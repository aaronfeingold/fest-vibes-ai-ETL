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

### Environment Setup for Tests

**Important**: Tests require database connection and environment variables to be set.

**Option 1: Using pipenv (Recommended - auto-loads .env)**

```sh
pipenv run pytest tests/simple_tests.py
pipenv run pytest tests/test_concurrency_optimization.py
```

**Option 2: Manual environment loading**

```sh
# Load .env file manually and run tests
export $(cat .env | xargs) && PYTHONPATH=. pytest tests/simple_tests.py

# Or set specific variables
PG_DATABASE_URL="postgresql://user:pass@host:5432/db" PYTHONPATH=. pytest tests/simple_tests.py
```

**Option 3: Using python-dotenv**

```sh
pip install python-dotenv
PYTHONPATH=. python -c "from dotenv import load_dotenv; load_dotenv(); import pytest; pytest.main(['tests/simple_tests.py'])"
```

### Test Suites

**Basic functionality tests:**

```sh
pipenv run pytest tests/simple_tests.py -v
```

**Concurrency optimization tests:**

```sh
pipenv run pytest tests/test_concurrency_optimization.py -v
```

**All tests:**

```sh
pipenv run pytest tests/ -v
```

**Specific test class or method:**

```sh
# Run specific test class
pipenv run pytest tests/test_concurrency_optimization.py::TestConcurrencyOptimizations -v

# Run specific test method
pipenv run pytest tests/test_concurrency_optimization.py::TestConcurrencyOptimizations::test_deadlock_retry_logic_exists -v
```

### Test Coverage

```sh
pipenv run pytest tests/ --cov=src --cov-report=html
```

### Test Run

```sh
pipenv run python -m src.scraper.app
pipenv run python -m src.loader.app
pipenv run python -m src.cache_manager.app
pipenv run python -m src.date_range_generator.app
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
docker build --target dev -t fest-vibes-ai-ETL:dev .
# create new container from latest dev build
docker run \
  --network host \
  -v ~/.aws:/root/.aws \
  -e PG_DATABASE_URL=postgresql://{username}:{password}@localhost:{db_port}/{db_name} \
  -e BASE_URL="https://www.wwoz.org" \
  -e GOOGLE_MAPS_API_KEY=a_super_secret_thing \
  -e S3_BUCKET_NAME=your-data-bucket-name \
  -e REDIS_URL=rediss://username:password@hostname:port \
  fest-vibes-ai-ETL:dev
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

5. **Network Configuration**
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

The system has evolved from an event-driven architecture to a Step Function orchestrated approach. Below is the current visual representation:

![Current Architecture](image.png)

#### Architecture Comparison: Event-Driven vs Step Functions

```mermaid
flowchart TD
    subgraph "Architecture Comparison: Event-Driven vs Step Functions"

        subgraph left ["Event-Driven Architecture (Original Design)"]
            direction TB

            subgraph "CI/CD Process - Original"
                gh1[GitHub Repository] --> |Push to main| actions1[GitHub Actions]
                actions1 --> build_scraper1[Build Scraper Container]
                actions1 --> build_loader1[Build Loader Container]
                actions1 --> build_cache1[Build Cache Manager Container]
                actions1 --> build_date1[Build Date Generator Container]

                build_scraper1 --> push_ecr11[Push to ECR]
                build_loader1 --> push_ecr21[Push to ECR]
                build_cache1 --> push_ecr31[Push to ECR]
                build_date1 --> push_ecr41[Push to ECR]

                push_ecr11 --> |Update Lambda| deploy1[Deploy Infrastructure]
                push_ecr21 --> |Update Lambda| deploy1
                push_ecr31 --> |Update Lambda| deploy1
                push_ecr41 --> |Update Lambda| deploy1

                deploy1 --> |Terraform Apply| infra1[AWS Infrastructure]
            end

            subgraph "Event-Driven ETL Flow"
                cw1[CloudWatch Event] --> |Daily Trigger| date_gen1[Date Range Generator]
                date_gen1 --> |Generate dates| scraper1[Scraper Lambda]
                scraper1 --> |Store data| s31[(S3 Bucket)]
                s31 --> |S3 Notification| sns1[SNS Topic]
                sns1 --> |Fan out| sqs1[SQS Queue]
                sqs1 --> |Pull message| loader1[Loader Lambda]
                loader1 --> |Process & store| pg1[(PostgreSQL)]
                loader1 --> |Publish completion| result_sns1[Results SNS]
                result_sns1 --> |Trigger| cache1[Cache Manager]
                cache1 --> |Update cache| redis1[(Redis Cache)]
            end

            subgraph "Observability - Event-Driven"
                sqs1 --> |DLQ| dlq1[Dead Letter Queue]
                sns1 --> |CloudWatch Metrics| metrics1[Message Metrics]
                loader1 --> |Retry Logic| retry1[Built-in Retries]
            end
        end

        subgraph right ["Step Function Orchestration (Current Implementation)"]
            direction TB

            subgraph "CI/CD Process - Current"
                gh2[GitHub Repository] --> |Push to main| actions2[GitHub Actions]
                actions2 --> test2[Run Tests]
                test2 --> build_matrix[Build Matrix Strategy]
                build_matrix --> build_ext[Build Extractor]
                build_matrix --> build_load[Build Loader]
                build_matrix --> build_cache[Build Cache Manager]
                build_matrix --> build_param[Build Param Generator]

                build_ext --> ecr2[Push to ECR]
                build_load --> ecr2
                build_cache --> ecr2
                build_param --> ecr2

                ecr2 --> |Terraform Apply| deploy2[Deploy Infrastructure]
                deploy2 --> |Create/Update| infra2[AWS Infrastructure]
            end

            subgraph "Step Function ETL Flow"
                cw2[CloudWatch Event] --> |"cron(0 8 * * ? *)"| sf[Step Function]
                sf --> |Invoke| date_gen2[Date Range Generator]
                date_gen2 --> |Return dates array| map_state[Map State - Max Concurrency: 5]
                map_state --> |For each date| extractor2[Extractor Lambda]
                extractor2 --> |Store in S3| s32[(S3 Bucket)]
                extractor2 --> |Pass S3 key| loader2[Loader Lambda]
                loader2 --> |Write to DB| pg2[(PostgreSQL)]
                loader2 --> |Success| cache2[Cache Manager Lambda]
                cache2 --> |Update cache| redis2[(Redis Cache)]
            end

            subgraph "Step Function Features"
                sf --> |Built-in Retry| retry2[Lambda Retry Logic]
                sf --> |Error Handling| error_handling[Choice States]
                sf --> |Status Tracking| sf_console[Step Function Console]
                map_state --> |Tolerated Failure: 10%| fault_tolerance[Fault Tolerance]
            end
        end
    end

    subgraph "Trade-offs Analysis"
        direction LR

        subgraph "Event-Driven Benefits"
            eb1[High Observability]
            eb2[Loose Coupling]
            eb3[Built-in Retry/DLQ]
            eb4[Horizontal Scaling]
        end

        subgraph "Event-Driven Costs"
            ec1[SNS Message Costs]
            ec2[SQS Polling Costs]
            ec3[Additional Infrastructure]
            ec4[Complex Debugging]
        end

        subgraph "Step Function Benefits"
            sb1[Visual Workflow]
            sb2[Centralized Orchestration]
            sb3[Lower Message Costs]
            sb4[Built-in Error Handling]
        end

        subgraph "Step Function Costs"
            sc1[State Transition Costs]
            sc2[Reduced Observability]
            sc3[Tight Coupling]
            sc4[Complex Parallel Processing]
        end
    end

    classDef aws fill:#FF9900,stroke:#232F3E,color:white;
    classDef lambda fill:#FF9900,stroke:#232F3E,color:white;
    classDef storage fill:#3B48CC,stroke:#232F3E,color:white;
    classDef cache fill:#FF3333,stroke:#232F3E,color:white;
    classDef messaging fill:#CC2A6B,stroke:#232F3E,color:white;
    classDef stepfunctions fill:#CC771C,stroke:#232F3E,color:white;
    classDef benefits fill:#4CAF50,stroke:#2E7D32,color:white;
    classDef costs fill:#F44336,stroke:#C62828,color:white;

    class s31,s32,pg1,pg2 storage;
    class redis1,redis2 cache;
    class date_gen1,date_gen2,scraper1,extractor2,loader1,loader2,cache1,cache2 lambda;
    class sns1,sqs1,result_sns1,dlq1 messaging;
    class sf,map_state,sf_console stepfunctions;
    class infra1,infra2,cw1,cw2 aws;
    class eb1,eb2,eb3,eb4,sb1,sb2,sb3,sb4 benefits;
    class ec1,ec2,ec3,ec4,sc1,sc2,sc3,sc4 costs;
```

#### Architecture Evolution & Trade-offs

**From Event-Driven to Step Functions**

Our initial design used an event-driven architecture with S3 notifications triggering SNS topics that fanned out to SQS queues. This provided excellent observability and loose coupling, but came with significant AWS messaging costs and operational complexity.

**Key Trade-offs in Current Implementation:**

**Benefits of Step Functions:**

- **Reduced AWS Costs**: Eliminated SNS message fees (~$0.50 per million messages) and SQS polling costs
- **Visual Workflow Management**: Step Function console provides clear execution visibility
- **Centralized Orchestration**: All workflow logic in one place with built-in error handling
- **Simplified Architecture**: Fewer moving parts and integration points

**Trade-offs Made:**

- **Reduced Observability**: Lost granular message-level metrics and dead letter queue insights
- **Tighter Coupling**: Components now directly orchestrated rather than event-driven
- **State Transition Costs**: Step Functions charge per state transition (~$25 per million transitions)
- **Limited Parallel Processing**: Map state concurrency limits vs unlimited SQS consumers

**Cost Analysis:**

- **Event-Driven**: High volume messaging costs (SNS + SQS polling) + Lambda invocation costs
- **Step Functions**: State transition costs + Lambda invocation costs (messaging eliminated)
- **Break-even Point**: ~50,000 daily processing operations favors Step Functions for our use case

### ETL Pipeline Flow

The ETL pipeline runs automatically daily at 3 AM CST/CDT via CloudWatch Events triggering the Step Function:

**Current Implementation Flow:**

**Trigger**: CloudWatch Event Rule (`cron(0 8 * * ? *)`) → Step Function

1. **Step Function Orchestration**:

   - **Date Range Generator**: Generates dates to process (next 30 days)
   - **Map State**: Processes each date with max concurrency of 5
   - **Per-Date Workflow**: Extractor → Loader → Cache Manager (sequential for each date)

2. **Component Flow**:
   - **Extractor**: Extracts event data for date and stores in S3
   - **Loader**: Processes S3 data into PostgreSQL (with vector embeddings)
   - **Cache Manager**: Queries database and updates Redis cache

**Step Function Workflow Diagram:**

```mermaid

graph TD
    A[CloudWatch Event<br/>cron: 0 8 * * ? *] --> B[Step Function Start]
    B --> C[Date Range Generator<br/>Generate 30 days ahead]
    C --> D{Generator Success?}
    D -->|200 OK| E[Map State<br/>Max Concurrency: 5<br/>Tolerated Failure: 10%]
    D -->|Error| F[Fail: ParamGeneratorFailed]

    E --> G[For Each Date:]
    G --> H[Extractor Lambda<br/>Extract & Store in S3]
    H --> I{Extractor Success?}
    I -->|200 OK| J[Loader Lambda<br/>S3 → PostgreSQL + Vectors]
    I -->|Error| K[Fail: ExtractorFailed]

    J --> L{Loader Success?}
    L -->|200 OK| M[Cache Manager Lambda<br/>DB → Redis Cache]
    L -->|Error| N[Fail: LoaderFailed]

    M --> O{Cache Success?}
    O -->|200 OK| P[Success]
    O -->|Error| Q[Fail: CacheFailed]

    style B fill:#FF9900,color:white
    style E fill:#CC771C,color:white
    style H fill:#FF9900,color:white
    style J fill:#FF9900,color:white
    style M fill:#FF9900,color:white
    style P fill:#4CAF50,color:white
    style F fill:#F44336,color:white
    style K fill:#F44336,color:white
    style N fill:#F44336,color:white
    style Q fill:#F44336,color:white
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
