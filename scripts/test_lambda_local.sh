#!/bin/bash
set -euo pipefail

# Local Lambda Testing Script
# Test Docker images locally with sample events

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-937355130135}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Test functions for each component
test_param_generator() {
    local days_ahead=${1:-7}
    local image_name="$ECR_REGISTRY/fest-vibes-ai-param_generator:$IMAGE_TAG"

    log_info "Testing param_generator with days_ahead=$days_ahead"

    docker run --rm "$image_name" python -c "
import json
import sys
sys.path.insert(0, '/app')

try:
    from param_generator.app import lambda_handler
    result = lambda_handler({'days_ahead': $days_ahead}, None)
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
"
}

test_extractor() {
    local test_date=${1:-$(date +%Y-%m-%d)}
    local image_name="$ECR_REGISTRY/fest-vibes-ai-extractor:$IMAGE_TAG"

    log_info "Testing extractor with date=$test_date"

    docker run --rm "$image_name" python -c "
import json
import sys
import asyncio
sys.path.insert(0, '/app')

async def test():
    try:
        from extract.app import lambda_handler
        event = {'queryStringParameters': {'date': '$test_date'}}
        result = await lambda_handler(event, None)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

asyncio.run(test())
"
}

test_loader() {
    local s3_key=${1:-"events/$(date +%Y-%m-%d).json"}
    local image_name="$ECR_REGISTRY/fest-vibes-ai-loader:$IMAGE_TAG"

    log_info "Testing loader with s3_key=$s3_key"

    docker run --rm "$image_name" python -c "
import json
import sys
import asyncio
sys.path.insert(0, '/app')

async def test():
    try:
        from transform.app import lambda_handler
        event = {'s3_key': '$s3_key'}
        result = await lambda_handler(event, None)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

asyncio.run(test())
"
}

test_cache_manager() {
    local test_date=${1:-$(date +%Y-%m-%d)}
    local image_name="$ECR_REGISTRY/fest-vibes-ai-cache_manager:$IMAGE_TAG"

    log_info "Testing cache_manager with date=$test_date"

    docker run --rm "$image_name" python -c "
import json
import sys
import asyncio
sys.path.insert(0, '/app')

async def test():
    try:
        from load.app import lambda_handler
        event = {'date': '$test_date'}
        result = await lambda_handler(event, None)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

asyncio.run(test())
"
}

# Interactive debugging
debug_component() {
    local component="$1"
    local image_name="$ECR_REGISTRY/fest-vibes-ai-$component:$IMAGE_TAG"

    log_info "Starting interactive session for $component"
    log_info "Container structure at /app:"

    docker run -it --rm "$image_name" bash -c "
echo 'Container contents:'
ls -la /app
echo
echo 'Python path:'
python -c 'import sys; print(sys.path)'
echo
echo 'Available modules:'
find /app -name '*.py' | head -10
echo
echo 'Starting bash shell...'
bash
"
}

# Usage function
usage() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

Test Lambda functions locally using Docker images.

COMMANDS:
    param-generator [days]     Test parameter generator (default: 7 days)
    extractor [date]          Test extractor (default: today)
    loader [s3_key]           Test loader (default: events/today.json)
    cache-manager [date]      Test cache manager (default: today)
    debug <component>         Interactive debugging session
    all                       Test all components with defaults

OPTIONS:
    --tag TAG                 Docker image tag (default: latest)
    --help                    Show this help

EXAMPLES:
    # Test specific components
    $0 param-generator 14
    $0 extractor 2025-01-30
    $0 loader events/2025-01-30.json

    # Debug a component interactively
    $0 debug param-generator

    # Test all components
    $0 all

    # Use specific image tag
    $0 --tag v1.2.3 param-generator
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        param-generator)
            test_param_generator "${2:-7}"
            exit 0
            ;;
        extractor)
            test_extractor "${2:-$(date +%Y-%m-%d)}"
            exit 0
            ;;
        loader)
            test_loader "${2:-events/$(date +%Y-%m-%d).json}"
            exit 0
            ;;
        cache-manager)
            test_cache_manager "${2:-$(date +%Y-%m-%d)}"
            exit 0
            ;;
        debug)
            if [[ -z "${2:-}" ]]; then
                log_error "Component name required for debug"
                usage
                exit 1
            fi
            debug_component "$2"
            exit 0
            ;;
        all)
            log_info "Testing all components..."
            echo
            test_param_generator 7
            echo
            test_extractor
            echo
            test_loader
            echo
            test_cache_manager
            log_success "All tests completed"
            exit 0
            ;;
        *)
            log_error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
done

# Default: show usage
usage
