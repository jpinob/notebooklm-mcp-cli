#!/usr/bin/env bash
# Pre-commit hook: Detect secrets and credentials in staged files
# Install: cp scripts/pre-commit-secrets.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

FOUND_SECRETS=0

# Get list of staged files (only added/modified, skip deleted)
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

echo "🔍 Scanning staged files for secrets..."

# =============================================================================
# Pattern definitions
# =============================================================================

# Google auth cookies (the most critical for this project)
COOKIE_PATTERNS=(
    'SID=[a-zA-Z0-9_-]{10,}'
    'HSID=[a-zA-Z0-9_-]{10,}'
    'SSID=[a-zA-Z0-9_-]{10,}'
    'APISID=[a-zA-Z0-9_-]{10,}'
    'SAPISID=[a-zA-Z0-9_-]{10,}'
    '__Secure-[13]PSID=[a-zA-Z0-9_-]{10,}'
    '__Secure-[13]PSIDTS=[a-zA-Z0-9_-]{10,}'
    'NID=[0-9]+='
)

# Generic secret patterns
SECRET_PATTERNS=(
    'AIza[0-9A-Za-z_-]{35}'          # Google API key
    'sk-[a-zA-Z0-9]{20,}'             # OpenAI / Stripe key
    'ghp_[a-zA-Z0-9]{36}'             # GitHub personal access token
    'gho_[a-zA-Z0-9]{36}'             # GitHub OAuth token
    'AKIA[0-9A-Z]{16}'                # AWS access key
    'Bearer [a-zA-Z0-9_-]{20,}'       # Bearer tokens
)

# Windows paths with real usernames (not generic patterns)
PATH_PATTERNS=(
    'C:\\Users\\[A-Z][a-z]+[a-zA-Z0-9]*\\'
    '/home/[a-z][a-z0-9_-]+/'
)

# Files to always skip (binary, docs with example patterns)
SKIP_PATTERNS="\.md$|\.txt$|\.rst$|\.sample$|\.mcpb$|\.jpg$|\.png$|\.gif$|\.svg$"

# =============================================================================
# Scanning functions
# =============================================================================

scan_pattern() {
    local pattern="$1"
    local label="$2"
    local file="$3"

    # Get staged content only (not working tree)
    local matches
    matches=$(git diff --cached -U0 -- "$file" 2>/dev/null | grep -E "^\+" | grep -v "^+++" | grep -oE "$pattern" 2>/dev/null || true)

    if [ -n "$matches" ]; then
        echo -e "  ${RED}[BLOCKED]${NC} $label found in ${YELLOW}$file${NC}"
        FOUND_SECRETS=1
    fi
}

# =============================================================================
# Main scan
# =============================================================================

for file in $STAGED_FILES; do
    # Skip non-text files and documentation
    if echo "$file" | grep -qE "$SKIP_PATTERNS"; then
        continue
    fi

    # Skip the pre-commit hook itself and security audit (contains patterns as examples)
    if echo "$file" | grep -qE "pre-commit|SECURITY_AUDIT"; then
        continue
    fi

    # Check if file exists (might have been deleted)
    if [ ! -f "$file" ]; then
        continue
    fi

    # Scan for Google auth cookies
    for pattern in "${COOKIE_PATTERNS[@]}"; do
        scan_pattern "$pattern" "Google auth cookie" "$file"
    done

    # Scan for generic secrets
    for pattern in "${SECRET_PATTERNS[@]}"; do
        scan_pattern "$pattern" "Secret/API key" "$file"
    done

    # Scan for personal paths (only in Python/config files)
    if echo "$file" | grep -qE "\.(py|toml|json|yaml|yml|cfg|ini)$"; then
        for pattern in "${PATH_PATTERNS[@]}"; do
            scan_pattern "$pattern" "Personal path" "$file"
        done
    fi
done

# =============================================================================
# Result
# =============================================================================

if [ "$FOUND_SECRETS" -eq 1 ]; then
    echo ""
    echo -e "${RED}❌ COMMIT BLOCKED: Potential secrets detected in staged files.${NC}"
    echo ""
    echo "If these are false positives (e.g., test patterns, documentation):"
    echo "  git commit --no-verify"
    echo ""
    echo "Otherwise, remove the secrets and try again."
    exit 1
else
    echo -e "${GREEN}✅ No secrets detected.${NC}"
    exit 0
fi
