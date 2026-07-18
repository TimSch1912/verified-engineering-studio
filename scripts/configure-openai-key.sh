#!/usr/bin/env bash
set -euo pipefail

VES_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VES_ENV_FILE="${VES_REPO_DIR}/.env"
VES_TEMP_FILE=""
VES_KEY_VALUE=""

cleanup() {
  unset VES_KEY_VALUE
  if [[ -n "${VES_TEMP_FILE}" && -f "${VES_TEMP_FILE}" ]]; then
    rm -f -- "${VES_TEMP_FILE}"
  fi
}
trap cleanup EXIT

read -r -s -p "OpenAI API key (input hidden): " VES_KEY_VALUE
printf '\n'

if [[ "${VES_KEY_VALUE}" != sk-* ]]; then
  echo "The value does not look like an OpenAI API key." >&2
  exit 1
fi

umask 077
VES_TEMP_FILE="$(mktemp "${VES_ENV_FILE}.XXXXXX")"
if [[ -f "${VES_ENV_FILE}" ]]; then
  awk '!/^OPENAI_API_KEY=/' "${VES_ENV_FILE}" > "${VES_TEMP_FILE}"
fi
printf 'OPENAI_API_KEY=%s\n' "${VES_KEY_VALUE}" >> "${VES_TEMP_FILE}"
mv -- "${VES_TEMP_FILE}" "${VES_ENV_FILE}"
VES_TEMP_FILE=""
chmod 600 "${VES_ENV_FILE}"

echo "OpenAI API key stored in the ignored server environment file."
echo "Restart verified-engineering-studio.service to activate it."
