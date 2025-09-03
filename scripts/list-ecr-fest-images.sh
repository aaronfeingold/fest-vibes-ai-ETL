#!/bin/bash

echo "Listing ECR repositories with 'fest' in the name and their image details..."
echo "=================================================================="

for repo in $(aws ecr describe-repositories --query 'repositories[?contains(repositoryName, `fest`)].repositoryName' --output text); do
  echo ""
  echo "Repository: $repo"
  echo "----------------------------------------"
  aws ecr describe-images --repository-name "$repo" --query 'imageDetails[*].[imageTags[0], imageSizeInBytes, imagePushedAt]' --output table
done

echo ""
echo "Finding largest images across all 'fest' repositories..."
echo "======================================================="

for repo in $(aws ecr describe-repositories --query 'repositories[?contains(repositoryName, `fest`)].repositoryName' --output text); do
  aws ecr describe-images --repository-name "$repo" --query "imageDetails[*].[\`$repo\`, imageTags[0], imageSizeInBytes]" --output text
done | sort -k3 -nr | head -10 | while read line; do
  repo=$(echo "$line" | awk '{print $1}')
  tag=$(echo "$line" | awk '{print $2}')
  size=$(echo "$line" | awk '{print $3}')
  size_mb=$(echo "scale=2; $size / 1024 / 1024" | bc -l 2>/dev/null || echo "$(($size / 1024 / 1024))")
  echo "$repo:$tag - ${size_mb}MB ($size bytes)"
done
