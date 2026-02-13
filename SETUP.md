# Julian Setup Guide

Quick setup for the Julian pattern enforcer.

## 1. Create GitHub App

Go to **GitHub Settings → Developer settings → GitHub Apps → New GitHub App**

| Setting | Value |
|---------|-------|
| Name | Julian (or your preferred name) |
| Homepage URL | https://github.com/htelsiz/julian |
| Webhook URL | `https://<julian-tailscale-hostname>/julian/webhook` |
| Webhook secret | Generate with `openssl rand -hex 32` |

### Permissions

| Permission | Access |
|------------|--------|
| Contents | Read |
| Pull requests | Read & Write |
| Issues | Read & Write |

### Events

- [x] Pull request
- [x] Issue comment

Save the App ID, generate a private key, and note the webhook secret.

## 2. Create Secrets Directory

```bash
sudo mkdir -p /etc/nixos/secrets/julian
sudo chmod 700 /etc/nixos/secrets/julian
```

## 3. Add Secrets

```bash
# GitHub App credentials
echo "YOUR_APP_ID" | sudo tee /etc/nixos/secrets/julian/app-id
sudo cp ~/Downloads/julian.private-key.pem /etc/nixos/secrets/julian/private-key.pem
echo "YOUR_WEBHOOK_SECRET" | sudo tee /etc/nixos/secrets/julian/webhook-secret

# GCP credentials (can reuse from Ricky if same project)
sudo cp /etc/nixos/secrets/ricky/gcp-service-account.json /etc/nixos/secrets/julian/
sudo cp /etc/nixos/secrets/ricky/gcp-project /etc/nixos/secrets/julian/

# Tailscale auth key (generate new reusable key from Tailscale admin)
echo "tskey-auth-..." | sudo tee /etc/nixos/secrets/julian/tailscale-auth-key

# Lock down permissions
sudo chmod 600 /etc/nixos/secrets/julian/*
```

## 4. Push Julian to GitHub

```bash
cd /Users/hkt/projects/julian
gh repo create htelsiz/julian --public --source=. --push
```

## 5. Deploy

```bash
# Update flake lock to fetch julian-src
cd /etc/nixos
sudo nix flake update julian-src

# Rebuild NixOS (includes Julian MicroVM)
sudo nixos-rebuild switch --flake /etc/nixos#phoenix
```

## 6. Verify

```bash
# Check VM is running
systemctl status microvm@julian

# Health check (from host)
curl http://192.168.83.11:8000/health

# SSH into VM
ssh root@julian

# Check service logs
journalctl -u julian -f
```

## 7. Configure Tailscale Funnel

The funnel is configured declaratively in `julian.nix`, but verify it's working:

```bash
ssh root@julian
tailscale status
tailscale serve status
```

Public URL: `https://<julian-hostname>/julian/webhook`

## 8. Install on Repos

Install the Julian GitHub App on repos where you want pattern enforcement.

Optionally add per-repo customization:
- `.gemini/patterns.md` — repo-specific patterns
- `.gemini/styleguide.md` — customize Julian's persona

## Network

| Host | IP | Port | Purpose |
|------|-----|------|---------|
| ricky | 192.168.83.10 | 8000 | General code review |
| julian | 192.168.83.11 | 8000 | Pattern enforcement |

Both VMs share the same bridge (`microbr`) and can reach the internet via NAT.
