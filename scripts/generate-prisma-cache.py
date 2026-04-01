#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Generate Prisma engine binary cache for offline/airgapped Docker builds.

Downloads Prisma engine binaries from binaries.prisma.sh and places them in
the PRISMA_CACHE directory so the Dockerfile can use them without internet.

Unlike running `prisma version` (which downloads binaries for the *current*
host platform), this script downloads binaries for a specified *target*
platform. This is critical when the build machine OS differs from the Docker
container OS — e.g. building on Amazon Linux or macOS while the container
uses python:3.13-slim (Debian).

The Dockerfile sets PRISMA_QUERY_ENGINE_BINARY and PRISMA_SCHEMA_ENGINE_BINARY
env vars to point at these cached files, bypassing Prisma's platform detection
and download logic entirely.

Usage:
    python3 scripts/generate-prisma-cache.py <output_dir> [--platform <platform>]

    platform defaults to 'debian-openssl-3.0.x' which matches python:3.13-slim.
    Common platforms:
        debian-openssl-3.0.x   (Debian Bookworm/Trixie, python:3.13-slim)
        debian-openssl-1.1.x   (Debian Bullseye)
        rhel-openssl-1.0.x     (Amazon Linux 2, RHEL 7)
        rhel-openssl-3.0.x     (Amazon Linux 2023, RHEL 9)
        linux-musl             (Alpine)
        linux-musl-openssl-3.0.x (Alpine with OpenSSL 3)
"""

import gzip
import os
import shutil
import stat
import sys
import urllib.request

# Engine binaries to download
ENGINES = ["query-engine", "schema-engine"]

# Mirror URL (can be overridden with PRISMA_ENGINES_MIRROR env var)
DEFAULT_MIRROR = "https://binaries.prisma.sh"


def get_engine_version() -> str:
    """Get the expected engine version from prisma-client-py."""
    try:
        from prisma import config
        return config.expected_engine_version
    except ImportError:
        raise SystemExit(
            "prisma-client-py must be installed to determine the engine version. "
            "Install it with: pip install prisma"
        )


def download_engine(mirror: str, engine_hash: str, platform: str, engine_name: str, output_dir: str) -> str:
    """Download a single engine binary and return the output path."""
    url = f"{mirror}/all_commits/{engine_hash}/{platform}/{engine_name}.gz"
    output_path = os.path.join(output_dir, f"{engine_name}-{platform}")

    print(f"  Downloading {engine_name} for {platform}...")
    print(f"    URL: {url}")

    try:
        import ssl
        ctx = ssl.create_default_context()
        # Honor REQUESTS_CA_BUNDLE / SSL_CERT_FILE / AWS_CA_BUNDLE env vars
        ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE") or os.environ.get("AWS_CA_BUNDLE")
        if ca_bundle:
            ctx.load_verify_locations(ca_bundle)
        else:
            # Try certifi if available (common in pip-managed environments)
            try:
                import certifi
                ctx.load_verify_locations(certifi.where())
            except ImportError:
                pass
        req = urllib.request.Request(url, headers={"User-Agent": "prisma-client-py"})
        with urllib.request.urlopen(req, context=ctx) as response:
            compressed_data = response.read()

        # Decompress gzip
        decompressed_data = gzip.decompress(compressed_data)

        with open(output_path, "wb") as f:
            f.write(decompressed_data)

        # Make executable
        os.chmod(output_path, os.stat(output_path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        size_mb = len(decompressed_data) / (1024 * 1024)
        print(f"    Saved: {output_path} ({size_mb:.1f} MB)")
        return output_path

    except urllib.error.HTTPError as e:
        print(f"    Failed to download {url}: HTTP {e.code}")
        raise
    except Exception as e:
        print(f"    Failed to download {url}: {e}")
        raise


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/generate-prisma-cache.py <output_dir> [--platform <platform>]")
        print("\nDefaults to debian-openssl-3.0.x (matches python:3.13-slim)")
        sys.exit(1)

    output_dir = sys.argv[1]
    platform = "debian-openssl-3.0.x"

    # Parse --platform flag
    for i, arg in enumerate(sys.argv):
        if arg == "--platform" and i + 1 < len(sys.argv):
            platform = sys.argv[i + 1]

    mirror = os.environ.get("PRISMA_ENGINES_MIRROR", DEFAULT_MIRROR)
    engine_hash = get_engine_version()

    print(f"Generating Prisma engine cache:")
    print(f"  Engine hash: {engine_hash}")
    print(f"  Platform: {platform}")
    print(f"  Mirror: {mirror}")
    print(f"  Output: {output_dir}")
    print()

    # Create output directory (clean existing non-.gitkeep files)
    os.makedirs(output_dir, exist_ok=True)
    for item in os.listdir(output_dir):
        if item == ".gitkeep":
            continue
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
        else:
            os.remove(item_path)

    # Download each engine binary
    downloaded = []
    for engine_name in ENGINES:
        path = download_engine(mirror, engine_hash, platform, engine_name, output_dir)
        downloaded.append(path)

    print()
    print(f"Prisma engine cache generated successfully at {output_dir}")
    print(f"  Files: {', '.join(os.path.basename(p) for p in downloaded)}")


if __name__ == "__main__":
    main()
