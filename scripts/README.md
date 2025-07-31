# Build and Deployment Scripts

This directory contains enhanced scripts for building, pushing, and deploying the ETL pipeline components.

## Scripts Overview

### 1. `build_and_push.sh` - Bash Script

Enhanced bash script for ECR authentication, Docker builds, and deployment.

**Key Features:**

- ECR authentication with error handling
- Multi-tag support (latest, version, commit hash, timestamp)
- Parallel or sequential builds
- Comprehensive logging with colors
- Terraform integration
- Robust error handling

**Usage Examples:**

```bash
# Basic build (all components)
./scripts/build_and_push.sh

# Build with custom tag
./scripts/build_and_push.sh --tag v1.2.3

# Parallel build with terraform deployment
./scripts/build_and_push.sh --parallel --terraform

# Build specific components
./scripts/build_and_push.sh --components extractor,loader --verbose
```

### 2. `build_and_push.py` - Python Script

Python implementation that integrates with existing deployment utilities.

**Key Features:**

- Integration with `DeploymentManager` class
- Uses existing version utilities from `shared.utils.version`
- Thread-based parallel building
- Comprehensive error handling and logging
- Terraform integration via deployment manager

**Usage Examples:**

```bash
# Basic build
python3 scripts/build_and_push.py

# Build with custom settings
python3 scripts/build_and_push.py --tag v1.2.3 --parallel --terraform

# Build specific components with dry-run terraform
python3 scripts/build_and_push.py --components extractor,loader --terraform-dry-run

# Skip build, only run terraform
python3 scripts/build_and_push.py --skip-build --terraform --tag latest
```

### 3. `deployment_utils.py` - Deployment Manager

Existing utility for deployment management and ECR operations.

**Usage Examples:**

```bash
# Show current status
python3 scripts/deployment_utils.py status

# Show deployment history
python3 scripts/deployment_utils.py history

# Deploy with specific tag
python3 scripts/deployment_utils.py deploy v1.2.3

# Rollback to previous version
python3 scripts/deployment_utils.py rollback --dry-run
```

## Docker Image Tagging Strategy

All images are tagged with multiple tags for flexibility:

1. **`latest`** - Always points to the most recent build
2. **Version tag** - From `get_version()` or custom `--tag` parameter
3. **Git commit hash** - Short commit hash (e.g., `abc1234`)
4. **Timestamp** - Build timestamp (e.g., `20250129-143022`)

## Component Architecture

The scripts build and push these components:

- **extractor** - Data extraction component
- **loader** - Data loading component
- **cache_manager** - Cache management component
- **param_generator** - Parameter generation component

Each component has its own Dockerfile at `src/{component}/Dockerfile`.

## Environment Variables

- `AWS_REGION` - AWS region (default: us-east-1)
- `AWS_ACCOUNT_ID` - AWS account ID (default: 937355130135)

## Prerequisites

- Docker daemon running
- AWS CLI configured with appropriate permissions
- ECR repositories created for each component:
  - `fest-vibes-ai-extractor`
  - `fest-vibes-ai-loader`
  - `fest-vibes-ai-cache_manager`
  - `fest-vibes-ai-param_generator`

## Integration with Terraform

Both scripts support automatic Terraform deployment after successful builds:

- Use `--terraform` flag to run `terraform apply` after build
- Use `--terraform-dry-run` flag to run `terraform plan` only
- Images are deployed using the primary tag (version or custom tag)

## Error Handling

- Comprehensive error checking at each step
- Rollback capabilities in case of failures
- Detailed logging with timestamps and status indicators
- Pre-flight checks for Docker and AWS CLI availability

## Performance Options

- **Parallel builds** - Build multiple components simultaneously using `--parallel`
- **Verbose output** - Show detailed build logs using `--verbose`
- **Component selection** - Build only specific components using `--components`

Choose the script that best fits your workflow - bash for simplicity or Python for integration with existing utilities.

## Local Docker Testing

To test your Lambda functions locally using Docker images, use these commands:

### Environment Variables Setup

**Option 1: Create a `.env` file (recommended)**
Create a `test.env` file in your project root:

```bash
# test.env
TEST_S3_KEY=raw_events/2025/07/30/event_data_2025-07-29_20250730_002901.json
AWS_LAMBDA_RUNTIME_API=localhost
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=XXXXXXXXXXXXX
# Add any other variables you need for testing
```

**Option 2: Export variables manually**

```bash
export TEST_S3_KEY=raw_events/2025/07/30/event_data_2025-07-29_20250730_002901.json
export AWS_LAMBDA_RUNTIME_API=localhost
```

### Testing Individual Components

**1. Parameter Generator**

```bash
docker run --rm --env-file .env \
  param_generator-test \
  python -c "
import json
from app import lambda_handler
result = lambda_handler({'days_ahead': 7}, None)
print(json.dumps(result, indent=2))
"
```

**2. Extractor**

```bash
# Using .env file
docker run --rm --env-file test.env \
  extractor-test \
  python -c "
import json
from extractor.app import lambda_handler
import asyncio
event = {'queryStringParameters': {'date': '2025-01-30'}}
result = asyncio.run(lambda_handler(event, None))
print(json.dumps(result, indent=2))
"

# Using manual environment variables
docker run --rm -e AWS_LAMBDA_RUNTIME_API=localhost \
  937355130135.dkr.ecr.us-east-1.amazonaws.com/fest-vibes-ai-extractor:latest \
  python -c "
import json
from extract.app import lambda_handler
import asyncio
event = {'queryStringParameters': {'date': '2025-01-30'}}
result = asyncio.run(lambda_handler(event, None))
print(json.dumps(result, indent=2))
"
```

**3. Loader**

```bash

# Create test.env file with your variables, then:
docker run --rm --env-file .env \
  loader-test\
  python -c "
import json
import os
from loader.app import lambda_handler
import asyncio
s3_key = os.environ.get('TEST_S3_KEY', 'events/2025-01-30.json')
event = {'s3_key': s3_key}
result = asyncio.run(lambda_handler(event, None))
print(json.dumps(result, indent=2))
"
```

**4. Cache Manager**

```bash
# Using .env file
docker run --rm --env-file test.env \
  937355130135.dkr.ecr.us-east-1.amazonaws.com/fest-vibes-ai-cache_manager:latest \
  python -c "
import json
from load.app import lambda_handler
import asyncio
event = {'date': '2025-01-30'}
result = asyncio.run(lambda_handler(event, None))
print(json.dumps(result, indent=2))
"

# Using manual environment variables
docker run --rm -e AWS_LAMBDA_RUNTIME_API=localhost \
  937355130135.dkr.ecr.us-east-1.amazonaws.com/fest-vibes-ai-cache_manager:latest \
  python -c "
import json
from load.app import lambda_handler
import asyncio
event = {'date': '2025-01-30'}
result = asyncio.run(lambda_handler(event, None))
print(json.dumps(result, indent=2))
"
```

### Interactive Testing

```bash
# Run container interactively with .env file
docker run -it --rm --env-file test.env \
  937355130135.dkr.ecr.us-east-1.amazonaws.com/fest-vibes-ai-param_generator:latest bash

# Or run with manual environment variables
docker run -it --rm -e AWS_LAMBDA_RUNTIME_API=localhost \
  937355130135.dkr.ecr.us-east-1.amazonaws.com/fest-vibes-ai-param_generator:latest bash

# Inside container, test directly
cd /app
python -c "
import json
from param_generator.app import lambda_handler
result = lambda_handler({'days_ahead': 5}, None)
print(json.dumps(result, indent=2))
"
```

### Debugging Tips

1. **Check container contents**:

   ```bash
   docker run -it --rm image_name ls -la /app
   ```

2. **Check Python imports**:

   ```bash
   docker run --rm image_name python -c "import sys; print(sys.path)"
   ```

3. **Verify module structure**:

   ```bash
   docker run --rm image_name find /app -name "*.py" | head -20
   ```

4. **Test imports individually**:
   ```bash
   docker run --rm image_name python -c "from shared.utils.logger import logger; print('OK')"
   ```

### Common Issues

- **ImportError**: Check that import paths match container structure (`shared.utils.*` not `src.shared.utils.*`)
- **ModuleNotFoundError**: Verify PYTHONPATH includes `/app`
- **Exit status 1**: Usually import or runtime errors - run interactively to debug
