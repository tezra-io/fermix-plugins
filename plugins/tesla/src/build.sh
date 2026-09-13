#!/usr/bin/env bash
# Build the fermix-tesla plugin binary.
#
#   ./build.sh                 build every supported target
#   ./build.sh macos-aarch64   build one or more named targets
#
# Output lands in plugins/tesla/bin/<target>/fermix-tesla, which is ignored by
# git: binaries are published through a release, never committed.
set -euo pipefail

src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="$(cd "${src_dir}/.." && pwd)/bin"

# target name -> GOOS/GOARCH
targets() {
  case "$1" in
    macos-aarch64) echo "darwin arm64" ;;
    macos-x86_64)  echo "darwin amd64" ;;
    linux-x86_64)  echo "linux amd64" ;;
    linux-aarch64) echo "linux arm64" ;;
    *) return 1 ;;
  esac
}

all_targets=(macos-aarch64 macos-x86_64 linux-x86_64 linux-aarch64)
requested=("$@")
if [ ${#requested[@]} -eq 0 ]; then
  requested=("${all_targets[@]}")
fi

for target in "${requested[@]}"; do
  if ! platform="$(targets "${target}")"; then
    echo "build.sh: unknown target '${target}'; expected one of ${all_targets[*]}" >&2
    exit 2
  fi
  read -r goos goarch <<<"${platform}"
  out="${bin_dir}/${target}/fermix-tesla"

  mkdir -p "$(dirname "${out}")"
  echo "building ${target} (${goos}/${goarch}) -> ${out}"
  (
    cd "${src_dir}"
    CGO_ENABLED=0 GOOS="${goos}" GOARCH="${goarch}" \
      go build -trimpath -ldflags="-s -w" -o "${out}" ./cmd/fermix-tesla
  )
  chmod 0755 "${out}"
done
