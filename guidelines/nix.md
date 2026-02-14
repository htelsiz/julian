# Nix Style Guide

Derived from nixos-config patterns. Julian enforces these patterns on all Nix PRs.

---

## Module Pattern

Every Nix file follows the module function pattern.

```nix
{ config, pkgs, lib, ... }:

{
  options.services.myservice = {
    enable = lib.mkEnableOption "my service";
    port = lib.mkOption {
      type = lib.types.port;
      default = 8080;
    };
  };

  config = lib.mkIf config.services.myservice.enable {
    systemd.services.myservice = {
      # ...
    };
  };
}
```

- Arguments destructured in the function head
- `lib.mkIf` for conditional configuration
- `lib.mkEnableOption` for feature toggles
- `lib.mkOption` with types for all options

## Organization

### Feature-Based

Organize by feature, not by type.

```
nixos-config/
├── modules/
│   ├── audio.nix          # By feature
│   ├── networking.nix
│   ├── gaming.nix
│   └── development.nix
├── hosts/
│   ├── phoenix/           # Per-machine config
│   └── macbook/
└── flake.nix
```

### Documentation Headers

```nix
# =============================================================================
# Audio Configuration
# =============================================================================
# Pipewire setup with low-latency audio for music production.
# Includes JACK compatibility layer for DAW software.
# =============================================================================
```

## Formatting

- 2-space indentation
- `with` bindings for package lists
- Align `=` signs in attribute sets when it aids readability

```nix
{ pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    git
    neovim
    ripgrep
  ];
}
```

## Cross-Platform

Shared modules must work on both NixOS and Darwin.

```nix
{ config, pkgs, lib, ... }:

{
  config = lib.mkMerge [
    {
      # Common config
    }
    (lib.mkIf pkgs.stdenv.isLinux {
      # Linux-only
    })
    (lib.mkIf pkgs.stdenv.isDarwin {
      # macOS-only
    })
  ];
}
```

## Comments

Comments explain WHY, not what. The Nix expression shows what.

```nix
# Wrong
# Set the port to 8080
port = 8080;

# Correct
# Match the port used by the reverse proxy
port = 8080;
```

## Flakes

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }: {
    nixosConfigurations.hostname = nixpkgs.lib.nixosSystem {
      modules = [ ./configuration.nix ];
    };
  };
}
```

- Pin inputs explicitly
- Use `nixos-unstable` for workstations, stable for servers
- Keep `flake.nix` minimal — delegate to modules

## Code Review Checklist

1. Module function pattern with proper arguments
2. Feature-based organization — not type-based
3. `lib.mkIf` for conditional blocks
4. 2-space indentation
5. Comments explain WHY
6. Cross-platform compat with `stdenv.isLinux`/`isDarwin`
7. `with pkgs;` for package lists
8. Documentation headers on complex modules
9. Options use `lib.mkOption` with types
10. No hardcoded paths — use `pkgs` or options
