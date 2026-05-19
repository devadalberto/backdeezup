#!/usr/bin/env bash
# Generate self-signed TLS certificate for local development.
# Valid for localhost, 127.0.0.1, and WINWEB01 (10 years).
# Run once: bash scripts/gen-dev-certs.sh
# The resulting certs are git-ignored (nginx/certs/*.crt, *.key).

set -euo pipefail

CERT_DIR="$(dirname "$0")/../nginx/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout "$CERT_DIR/server.key" \
  -out    "$CERT_DIR/server.crt" \
  -subj "/CN=backdeezup-dev" \
  -addext "subjectAltName=DNS:localhost,DNS:WINWEB01,IP:127.0.0.1,IP:192.168.88.60"

chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"

echo ""
echo "Dev certs generated:"
echo "  $CERT_DIR/server.crt"
echo "  $CERT_DIR/server.key"
echo ""
echo "Browser will show 'Not Secure' — expected for self-signed."
echo "To trust it: import server.crt into your OS/browser cert store."
echo ""
echo "Access the app at: https://localhost:8445"
