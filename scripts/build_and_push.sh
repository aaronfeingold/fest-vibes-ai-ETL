#!/bin/bash
set -euo pipefail

# Enhanced ECR Build and Push Script
# Builds and pushes Docker images for all ETL pipeline components

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-937355130135}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
COMPONENTS=("extractor" "loader" "cache_manager" "param_generator")
PARALLEL_BUILDS=false
RUN_TERRAFORM=false
CUSTOM_TAG=""
VERBOSE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to get project version using Python utilities
get_project_version() {
    cd "$PROJECT_ROOT"
    python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
try:
    from shared.utils.version import get_version
    print(get_version())
except ImportError:
    print('latest')
" 2>/dev/null || echo "latest"
}

# Function to get current git commit hash
get_git_commit() {
    git rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

# Function for ECR authentication
ecr_login() {
    log_info "Authenticating with ECR registry: $ECR_REGISTRY"

    if ! aws ecr get-login-password --region "$AWS_REGION" | \
         docker login --username AWS --password-stdin "$ECR_REGISTRY"; then
        log_error "Failed to authenticate with ECR"
        return 1
    fi

    log_success "ECR authentication successful"
}

# Function to check if Docker daemon is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running or not accessible"
        return 1
    fi
}

# Function to build a single component
build_component() {
    local component="$1"
    local tags=("${@:2}")

    log_info "Building component: $component"

    local dockerfile_path="$PROJECT_ROOT/src/$component/Dockerfile"
    if [[ ! -f "$dockerfile_path" ]]; then
        log_error "Dockerfile not found: $dockerfile_path"
        return 1
    fi

    # Build with first tag
    local primary_tag="${tags[0]}"
    local image_name="$ECR_REGISTRY/fest-vibes-ai-$component:$primary_tag"

    log_info "Building $component with tag: $primary_tag"
    if [[ "$VERBOSE" == "true" ]]; then
        docker build -t "$image_name" -f "$dockerfile_path" "$PROJECT_ROOT"
    else
        docker build -t "$image_name" -f "$dockerfile_path" "$PROJECT_ROOT" >/dev/null
    fi

    # Tag with additional tags
    for tag in "${tags[@]:1}"; do
        local additional_image="$ECR_REGISTRY/fest-vibes-ai-$component:$tag"
        log_info "Tagging $component with additional tag: $tag"
        docker tag "$image_name" "$additional_image"
    done

    log_success "Built $component successfully"
}

# Function to push a component with all its tags
push_component() {
    local component="$1"
    local tags=("${@:2}")

    log_info "Pushing component: $component (${#tags[@]} tags)"

    for i in "${!tags[@]}"; do
        local tag="${tags[$i]}"
        local image_name="$ECR_REGISTRY/fest-vibes-ai-$component:$tag"
        local tag_num=$((i + 1))

        log_info "Pushing $component:$tag (tag $tag_num/${#tags[@]})"
        local start_time=$(date +%s)

        if [[ "$VERBOSE" == "true" ]]; then
            docker push "$image_name"
        else
            # Always show push progress for better visibility
            docker push "$image_name" 2>&1 | grep -E "(Pushing|Pushed|Layer already exists|Waiting|Preparing)" | while read -r line; do
                echo "  → $line"
            done
        fi

        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_success "Pushed $component:$tag (${duration}s)"
    done

    log_success "Pushed $component successfully (all tags)"
}

# Function to build and push a component (for parallel execution)
build_and_push_component() {
    local component="$1"
    local tags=("${@:2}")

    {
        build_component "$component" "${tags[@]}"
        push_component "$component" "${tags[@]}"
    } 2>&1 | while read -r line; do
        echo "[$component] $line"
    done
}

# Function to run terraform apply
run_terraform() {
    local image_tag="$1"

    log_info "Running Terraform apply with image tag: $image_tag"

    local terraform_dir="$PROJECT_ROOT/terraform/environments/prod"
    if [[ ! -d "$terraform_dir" ]]; then
        log_error "Terraform directory not found: $terraform_dir"
        return 1
    fi

    cd "$terraform_dir"
    terraform apply -auto-approve -var="image_version=$image_tag" -var-file=terraform.tfvars

    log_success "Terraform apply completed"
}

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Build and push Docker images for ETL pipeline components.

OPTIONS:
    -t, --tag TAG           Custom tag for images (default: auto-detected version)
    -r, --region REGION     AWS region (default: us-east-1)
    -c, --components LIST   Comma-separated list of components to build
                           (default: extractor,loader,cache_manager,param_generator)
    -p, --parallel          Build components in parallel
    -T, --terraform         Run terraform apply after successful build
    -v, --verbose           Verbose output
    -h, --help             Show this help message

EXAMPLES:
    # Build all components with auto-detected version
    $0

    # Build specific components with custom tag
    $0 --components extractor,loader --tag v1.2.3

    # Build in parallel and deploy with terraform
    $0 --parallel --terraform

    # Build with verbose output
    $0 --verbose --tag latest
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            CUSTOM_TAG="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
            shift 2
            ;;
        -c|--components)
            IFS=',' read -ra COMPONENTS <<< "$2"
            shift 2
            ;;
        -p|--parallel)
            PARALLEL_BUILDS=true
            shift
            ;;
        -T|--terraform)
            RUN_TERRAFORM=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    log_info "Starting ECR build and push process"

    # Pre-flight checks
    check_docker || exit 1
    ecr_login || exit 1

    # Determine tags
    local version_tag
    if [[ -n "$CUSTOM_TAG" ]]; then
        version_tag="$CUSTOM_TAG"
    else
        version_tag=$(get_project_version)
    fi

    local commit_hash=$(get_git_commit)
    local timestamp=$(date +%Y%m%d-%H%M%S)

    # Create tag array (latest, version, commit-hash, timestamp)
    local tags=("latest" "$version_tag")
    if [[ "$commit_hash" != "unknown" && "$commit_hash" != "$version_tag" ]]; then
        tags+=("$commit_hash")
    fi
    tags+=("$timestamp")

    log_info "Building with tags: ${tags[*]}"
    log_info "Components to build: ${COMPONENTS[*]}"

    # Build and push components
    if [[ "$PARALLEL_BUILDS" == "true" ]]; then
        log_info "Building components in parallel"
        local pids=()

        for component in "${COMPONENTS[@]}"; do
            build_and_push_component "$component" "${tags[@]}" &
            pids+=($!)
        done

        # Wait for all background jobs to complete
        local failed=false
        for pid in "${pids[@]}"; do
            if ! wait "$pid"; then
                failed=true
            fi
        done

        if [[ "$failed" == "true" ]]; then
            log_error "One or more component builds failed"
            exit 1
        fi
    else
        # Sequential build
        for component in "${COMPONENTS[@]}"; do
            build_component "$component" "${tags[@]}" || exit 1
            push_component "$component" "${tags[@]}" || exit 1
        done
    fi

    log_success "All components built and pushed successfully"

    # Run terraform if requested
    if [[ "$RUN_TERRAFORM" == "true" ]]; then
        run_terraform "$version_tag" || exit 1
    fi

    log_success "Build and push process completed"
    log_info "Images tagged with: ${tags[*]}"
}

# Execute main function
main "$@"
