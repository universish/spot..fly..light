#!/usr/bin/env bash

destine_dir=$1
version=$2

# Only Fedora 45's observed Spotify WM_CLASS differs. Keep other targets unchanged.
wm_class=spotify
os_release=${SPOT_FLY_LIGHT_OS_RELEASE_FILE:-/etc/os-release}
if [[ -r "$os_release" ]] && grep -Eq '^ID="?fedora"?$' "$os_release" \
    && grep -Eq '^VERSION_ID="?45"?$' "$os_release"; then
    wm_class=Spotify
fi

mkdir -p "${destine_dir}"
cat > "${destine_dir}/spotify.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Spotify
Version=1.0
GenericName=Music Player
Comment=Spotify streaming music client
Icon=spotify-client
Exec=spotify %U
Terminal=false
MimeType=x-scheme-handler/spotify;
Categories=Audio;Music;Player;AudioVideo;
StartupWMClass=${wm_class}
X-GNOME-UsesNotifications=true
DESKTOP
