#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deploy_dir="${1:-${repo_root}/project/deploy/html}"

if [[ ! -d "${deploy_dir}" ]]; then
  printf 'deploy directory not found: %s\n' "${deploy_dir}" >&2
  exit 1
fi

rm -rf "${deploy_dir}/web" "${deploy_dir}/web_compiler"
cp -R "${repo_root}/project/web" "${deploy_dir}/web"
mkdir -p "${deploy_dir}/web_compiler"
cp -R "${repo_root}/project/web_compiler/wwwroot/"* "${deploy_dir}/web_compiler/"
mkdir -p "${deploy_dir}/web_compiler/leanclr"
cp "${repo_root}/project/leanclr/mscorlib.dll" "${deploy_dir}/web_compiler/leanclr/mscorlib.dll"
cp "${repo_root}/project/leanclr/System.dll" "${deploy_dir}/web_compiler/leanclr/System.dll"
cp "${repo_root}/project/leanclr/GodotSharpCompat.dll" "${deploy_dir}/web_compiler/leanclr/GodotSharpCompat.dll"

printf 'copied web sidecar to %s\n' "${deploy_dir}"
