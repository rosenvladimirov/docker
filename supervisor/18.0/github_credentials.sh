#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 -u <username> -e <email> [-t <token>] [-p <password>]"
  echo "Notes:"
  echo "  - For GitHub, prefer using a Personal Access Token (-t)."
  echo "  - Password (-p) is deprecated for GitHub HTTPS and is ignored."
  exit 1
}

USERNAME=""
EMAIL=""
TOKEN=""
PASSWORD=""

while getopts 'u:p:t:e:' flag; do
  case "${flag}" in
    u) USERNAME="${OPTARG}" ;;
    p) PASSWORD="${OPTARG}" ;;  # deprecated for GitHub; kept for compatibility
    t) TOKEN="${OPTARG}" ;;
    e) EMAIL="${OPTARG}" ;;
    *) usage ;;
  esac
done

# Fallback към GH_TOKEN env var ако -t липсва
if [[ -z "${TOKEN}" && -n "${GH_TOKEN:-}" ]]; then
  TOKEN="${GH_TOKEN}"
fi

# Задължителни аргументи
[[ -z "${USERNAME}" || -z "${EMAIL}" ]] && usage

# Базова git конфигурация (валидна за всички протоколи)
git config --global user.name "${USERNAME}"
git config --global user.email "${EMAIL}"

# Включваме кеш (удобно в CI), но ще запишем и store ако имаме токен
git config --global credential.helper "cache --timeout=86400"

if [[ -n "${TOKEN}" ]]; then
  # Настройваме persistent store, за да не иска постоянно креденшъли
  git config --global credential.helper "store"

  # Безопасно записване на креденшъли за github.com
  CRED_FILE="${HOME}/.git-credentials"
  mkdir -p "$(dirname "${CRED_FILE}")"
  # Формат: https://<user>:<token>@github.com
  # Изтриваме стари редове за github.com за да избегнем дубликати
  if [[ -f "${CRED_FILE}" ]]; then
    grep -vE '^https://.*@github\.com/?$' "${CRED_FILE}" > "${CRED_FILE}.tmp" || true
    mv "${CRED_FILE}.tmp" "${CRED_FILE}"
  fi
  echo "https://${USERNAME}:${TOKEN}@github.com" >> "${CRED_FILE}"
  chmod 600 "${CRED_FILE}"

  # Пренасочване на SSH адресите към HTTPS с токен (покрива git@github.com:org/repo.git и ssh://git@github.com/...)
  git config --global url."https://${USERNAME}:${TOKEN}@github.com/".insteadOf "git@github.com:"
  git config --global url."https://${USERNAME}:${TOKEN}@github.com/".insteadOf "ssh://git@github.com/"
  # По желание: и чист HTTPS без креденшъли към този с токен
  git config --global url."https://${USERNAME}:${TOKEN}@github.com/".insteadOf "https://github.com/"
else
  # Нямаме токен – оставяме само кеш-а; потребителят ще бъде подканен при нужда
  echo "Info: No token provided. Using credential cache only. For GitHub HTTPS, provide a Personal Access Token via -t or GH_TOKEN."
fi

echo "Git credentials configured for ${USERNAME} (${EMAIL})"