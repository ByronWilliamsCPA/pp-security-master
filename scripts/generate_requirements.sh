#!/bin/bash
# Generate requirements.txt with cryptographic hashes for security validation

set -euo pipefail

echo "🔐 Generating requirements.txt with cryptographic hashes..."

# Export production requirements (no dev group)
uv export \
    --frozen \
    --no-dev \
    --no-emit-project \
    --no-hashes \
    --output-file requirements.txt

echo "✅ Base requirements.txt generated"

# Generate requirements with dev dependencies
uv export \
    --frozen \
    --no-emit-project \
    --no-hashes \
    --output-file requirements-dev.txt

echo "✅ Development requirements.txt generated"

# Generate requirements with hashes for production security
uv export \
    --frozen \
    --no-dev \
    --no-emit-project \
    --output-file requirements-hashed.txt

echo "✅ Hashed requirements for production generated"

echo "📋 Files generated:"
echo "  - requirements.txt (production)"
echo "  - requirements-dev.txt (development)"
echo "  - requirements-hashed.txt (production with hashes)"
