PKG_NAME="SDL3_input"
# IMPORTANT: pin this to a commit/tag AFTER the "Triton" (new Steam
# Controller) hidapi commits landed (PR #15528, merged 2026-05-14; plus the
# rumble fix #15558 and input-report fix, both 2026-05-27/28). The 3.4.8
# tag predates some of these — check https://github.com/libsdl-org/SDL/releases
# or `git log` for the first tag/commit that includes all three, and use
# that SHA here the same way packages/libretro/retroarch/package.mk pins a
# specific RetroArch commit.
PKG_VERSION="<FILL_IN_COMMIT_OR_TAG_AFTER_TRITON_FIXES>"
PKG_SHA256="<FILL_IN_AFTER_CHOOSING_VERSION>"
PKG_LICENSE="ZLIB"
PKG_SITE="https://www.libsdl.org"
PKG_URL="https://github.com/libsdl-org/SDL/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET="toolchain dbus libusb systemd"
PKG_LONGDESC="SDL3 built with only input subsystems, used solely to drive the Steam Controller (2026)/Triton hidapi bridge -- NOT linked into RetroArch itself (RetroArch has no --enable-sdl3 upstream yet)."
PKG_TOOLCHAIN="cmake"
PKG_BUILD_FLAGS="+pic"

# NOTE: verify these option names against the actual SDL_*.cmake / top-level
# CMakeLists.txt in the SDL3 tree you pin above -- SDL3's CMake option names
# have shifted between releases (e.g. some subsystem toggles were renamed
# from the SDL2 `--enable-x` autotools convention). Grep for
# 'option(SDL_' in CMakeLists.txt to confirm before building.
PKG_CMAKE_OPTS_TARGET="-DSDL_SHARED=ON \
                       -DSDL_STATIC=OFF \
                       -DSDL_AUDIO=OFF \
                       -DSDL_VIDEO=OFF \
                       -DSDL_RENDER=OFF \
                       -DSDL_CAMERA=OFF \
                       -DSDL_POWER=OFF \
                       -DSDL_FILESYSTEM=OFF \
                       -DSDL_FILE=OFF \
                       -DSDL_LOADSO=ON \
                       -DSDL_THREADS=ON \
                       -DSDL_TIMERS=ON \
                       -DSDL_JOYSTICK=ON \
                       -DSDL_HAPTIC=ON \
                       -DSDL_SENSOR=ON \
                       -DSDL_HIDAPI=ON \
                       -DSDL_HIDAPI_LIBUSB=ON \
                       -DSDL_HIDAPI_JOYSTICK=ON"

makeinstall_target() {
  cmake --install ${PKG_BUILD}.${TARGET_NAME}
}
