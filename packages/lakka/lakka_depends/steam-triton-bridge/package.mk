PKG_NAME="steam-triton-bridge"
PKG_VERSION="1.0"
PKG_ARCH="any"
PKG_LICENSE="GPL"
PKG_SITE="https://github.com/NightmareVulkan/Lakka-LibreELEC"
PKG_URL=""
PKG_SOURCE_DIR=""
# python3 must already be on the image (Kodi/LibreELEC ships it for addons);
# SDL3_input provides libSDL3.so for the bridge to dlopen via ctypes.
PKG_DEPENDS_TARGET="toolchain Python3 SDL3_input systemd"
PKG_LONGDESC="Bridges the new Steam Controller (2026)/Triton + Puck dongle into a full-featured virtual joystick via SDL3's hidapi driver, so RetroArch's udev joypad driver sees all buttons (including the back paddles) instead of the kernel's lizard-mode-only fallback."
PKG_TOOLCHAIN="manual"

make_target() {
  :
}

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/lib/steam-triton-bridge
  cp -v ${PKG_DIR}/scripts/steam_triton_bridge.py \
        ${INSTALL}/usr/lib/steam-triton-bridge/steam_triton_bridge.py
  chmod +x ${INSTALL}/usr/lib/steam-triton-bridge/steam_triton_bridge.py

  mkdir -p ${INSTALL}/usr/lib/systemd/system
  cp -v ${PKG_DIR}/system.d/steam-triton-bridge.service \
        ${INSTALL}/usr/lib/systemd/system/steam-triton-bridge.service

  mkdir -p ${INSTALL}/usr/lib/udev/rules.d
  cp -v ${PKG_DIR}/udev.rules.d/99-steam-triton-bridge.rules \
        ${INSTALL}/usr/lib/udev/rules.d/99-steam-triton-bridge.rules
}

post_install() {
  : # Deliberately NOT enable_service'd -- this unit is udev-triggered
    # (SYSTEMD_WANTS) only when the Puck (28de:1304) is actually plugged
    # in, not started at boot unconditionally.
}
