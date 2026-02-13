#!/usr/bin/env bash
# Julian Secrets Setup Script
# Run on phoenix (the NixOS host) as root or with sudo

set -e

SECRETS_DIR="/etc/nixos/secrets/julian"
RICKY_SECRETS="/etc/nixos/secrets/ricky"

echo "=== Julian Secrets Setup ==="

# Create secrets directory
echo "Creating $SECRETS_DIR..."
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Copy reusable GCP credentials from Ricky
if [[ -d "$RICKY_SECRETS" ]]; then
    echo "Copying GCP credentials from Ricky..."
    cp "$RICKY_SECRETS/gcp-service-account.json" "$SECRETS_DIR/"
    cp "$RICKY_SECRETS/gcp-project" "$SECRETS_DIR/"
else
    echo "WARNING: Ricky secrets not found. You'll need to set up GCP credentials manually."
fi

# Generate webhook secret
echo "Generating webhook secret..."
tr -dc 'a-f0-9' < /dev/urandom | head -c 64 > "$SECRETS_DIR/webhook-secret"

# Placeholder files (need to be filled in after GitHub App creation)
echo "REPLACE_WITH_APP_ID" > "$SECRETS_DIR/app-id"
touch "$SECRETS_DIR/private-key.pem"
echo "REPLACE_WITH_TAILSCALE_KEY" > "$SECRETS_DIR/tailscale-auth-key"

# Lock down permissions
chmod 600 "$SECRETS_DIR"/*

echo ""
echo "=== Secrets directory created ==="
echo ""
echo "Next steps:"
echo ""
echo "1. Create GitHub App at: https://github.com/settings/apps/new"
echo "   - Name: Julian"
echo "   - Webhook URL: https://<julian-hostname>/julian/webhook"
echo "   - Webhook secret: $(cat $SECRETS_DIR/webhook-secret)"
echo "   - Permissions: contents:read, pull_requests:write, issues:write"
echo "   - Events: pull_request, issue_comment"
echo ""
echo "2. After creating the app, update these files:"
echo "   - $SECRETS_DIR/app-id (the App ID from GitHub)"
echo "   - $SECRETS_DIR/private-key.pem (download from GitHub App settings)"
echo ""
echo "3. Generate Tailscale auth key at: https://login.tailscale.com/admin/settings/keys"
echo "   - Create reusable key"
echo "   - Save to: $SECRETS_DIR/tailscale-auth-key"
echo ""
echo "4. Start the VM:"
echo "   sudo systemctl start microvm@julian"
echo ""
