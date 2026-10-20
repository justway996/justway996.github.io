#!/usr/bin/env bash
set -euo pipefail
node_archive=$1
quark_source=$2
owner=$3
browser=$4
install_dir=/opt/codex-quark
if [ -e "$install_dir/INSTALLER-OWNER" ] && [ "$(cat "$install_dir/INSTALLER-OWNER")" != "$owner" ]; then exit 71; fi
install -d -m 755 "$install_dir"
printf '%s\n' "$owner" > "$install_dir/INSTALLER-OWNER"
id codexbackup >/dev/null 2>&1 || useradd --create-home --shell /bin/bash codexbackup
test "$(id -u codexbackup)" -ne 0
if [ ! -x "$install_dir/node-v24.22.0-linux-x64/bin/node" ]; then
  tar -xJf "$node_archive" -C "$install_dir" --no-same-owner
fi
if [ -e /usr/local/bin/node ] && [ "$(readlink -f /usr/local/bin/node)" != "$install_dir/node-v24.22.0-linux-x64/bin/node" ]; then exit 72; fi
ln -sfn "$install_dir/node-v24.22.0-linux-x64/bin/node" /usr/local/bin/node
mkdir -p "$install_dir/1.0.24" "$install_dir/bin"
cp -R "$quark_source"/. "$install_dir/1.0.24/"
printf '#!/usr/bin/env bash\nexec %q url.dll,FileProtocolHandler "$1"\n' "$browser" > "$install_dir/bin/xdg-open"
chmod 755 "$install_dir/bin/xdg-open"
chown -R root:root "$install_dir"
chmod -R go-w "$install_dir"
if grep -q '^\[user\]' /etc/wsl.conf 2>/dev/null; then
  grep -q '^default=codexbackup$' /etc/wsl.conf || exit 73
else
  printf '\n[user]\ndefault=codexbackup\n' >> /etc/wsl.conf
fi
/usr/local/bin/node --version
/usr/local/bin/node "$install_dir/1.0.24/scripts/quark-drive.cjs" --version
