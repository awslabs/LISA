{
  # LISA Development Environment Flake
  #
  # LISA (LLM Inference Solution for Amazon) is an open source infrastructure-as-code
  # solution for deploying LLM inference capabilities into AWS accounts. This flake
  # provides a complete development environment with all necessary tools and dependencies
  # for developing, testing, and deploying LISA.
  description = "Development environment for LISA - LLM Inference Solution for Amazon";

  inputs = {
    # Use the unstable channel for latest package versions
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Utility functions for creating flakes that work across multiple systems
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    # Generate outputs for all default systems (x86_64-linux, aarch64-linux, x86_64-darwin, aarch64-darwin)
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        # Formatter for this flake (run with `nix fmt`)
        formatter = pkgs.nixpkgs-fmt;

        # Default development shell (enter with `nix develop`)
        devShells.default = pkgs.mkShell {
          # Core development tools needed for LISA
          packages = with pkgs; [
            awscli2     # AWS command-line interface for deployment and management
            jq          # JSON processor for parsing AWS responses and configuration
            pnpm        # Fast, disk space efficient package manager for JavaScript
            pre-commit  # Git hook framework for code quality checks
            python3     # Python runtime for LISA backend services
            nodejs      # Node.js runtime for CDK infrastructure and frontend tooling
            nodePackages.aws-cdk # AWS CDK CLI, the command line tool for CDK apps
            uv          # Fast Python package installer and virtual environment manager
            yq          # YAML processor for configuration management
          ];

          # Script that runs when entering the development shell
          shellHook = ''
            echo "Welcome to the LISA development environment!"
            echo "Python: $(python --version)"
            echo "Node: $(node --version)"
            echo ""

            # Set up Python virtual environment using uv
            if [ ! -d .venv ]; then
              echo "Creating Python virtual environment with uv..."
              uv venv
            else
              echo "Using existing Python virtual environment."
            fi

            # Ensure we start fresh if another venv is active
            if [ -n "$VIRTUAL_ENV" ]; then
              echo "Deactivating existing virtual environment..."
              deactivate
            fi

            # Activate the project virtual environment
            source .venv/bin/activate

            # Ensure pip is up to date
            uv pip install --upgrade pip

            # Initialize npm project if package.json doesn't exist
            if [ ! -f package.json ]; then
              echo "No package.json found. Running npm init..."
              npm init -y
            fi

            # Install Python development dependencies
            echo "Installing Python development dependencies from requirements-dev.txt..."

            # Extract packages that must be installed as binary wheels (no source builds)
            only_binary_packages=`grep "^--only-binary=" requirements-dev.txt | sed 's/^--only-binary=//' | tr ',' ' ' | tr -s ' ' | cut -d' ' -f1-`
            echo "Extracted binary-only packages: $only_binary_packages"

            # Install requirements with --only-binary flags converted to command-line arguments
            # This removes the --only-binary line from the file and passes it as CLI args instead
            echo "Installing filtered requirements-dev.txt..."
            uv pip install -r <(sed '/^--only-binary/d' requirements-dev.txt) `for p in "$$=only_binary_packages"; do echo "--only-binary=$$p"; done`

            # Install LISA SDK in editable mode with binary-only installation
            echo "Installing lisa-sdk in editable mode..."
            uv pip install --only-binary :all: -e lisa-sdk

            # Install Node.js dependencies
            echo "Installing Node.js dependencies..."
            pnpm install

            # Configure git hooks for pre-commit
            # Unset any existing hooks path to ensure pre-commit can manage hooks
            git config --unset-all core.hooksPath 2>/dev/null || true
            pre-commit install

            echo ""
            echo "Development environment ready!"
            echo "Available commands:"
            echo "  uv pip       - For faster package management"
            echo "  deploylisa   - Clean build and deploy LISA in headless mode"
          '';
        };
      }
    );
}
