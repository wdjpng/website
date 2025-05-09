#!/bin/bash

# Navigate to the script's directory (optional, but good practice)
# cd "$(dirname "$0")"

echo "Starting Jekyll development server..."

# Run Jekyll serve using Bundler
bundle exec jekyll serve 

echo "Jekyll server stopped." 