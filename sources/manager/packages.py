# packages.py
from pathlib import Path
import os
from utils.download import download_file, extract_archive
from utils.execute import run_command_live

CROSS_PREFIX = "aarch64-linux-gnu"

def build_package(name, url, dirs, configure_args=None):
    """
    dirs: dict mit Schlüsseln 'downloads', 'build', 'rootfs'
    """
    ENV = os.environ.copy()
    ENV["CC"] = f"{CROSS_PREFIX}-gcc"
    ENV["CXX"] = f"{CROSS_PREFIX}-g++"
    ENV["AR"] = f"{CROSS_PREFIX}-ar"
    ENV["RANLIB"] = f"{CROSS_PREFIX}-ranlib"
    ENV["STRIP"] = f"{CROSS_PREFIX}-strip"

    # 1. Download ins downloads_dir
    tarball = download_file(url, dirs["downloads"])

    # 2. Extract ins build_dir/<name>
    src_dir = extract_archive(tarball, dirs["build"] / name)

    # 3. Configure
    configure_script = src_dir / "configure"
    if configure_script.exists():
        args = ["./configure", f"--host={CROSS_PREFIX}", "--prefix=/usr"]
        if configure_args:
            args.extend(configure_args)
        run_command_live(args, cwd=src_dir, env=ENV, desc=f"{name}: configure")

    # 4. Build
    run_command_live(["make", "-j4"], cwd=src_dir, env=ENV, desc=f"{name}: build")

    # 5. Install ins rootfs_dir
    run_command_live(
        ["make", f"DESTDIR={dirs['rootfs']}", "install"],
        cwd=src_dir,
        env=ENV,
        desc=f"{name}: install"
    )

def build_bash(dirs):
    build_package(
        "bash",
        "http://ftp.gnu.org/gnu/bash/bash-1.14.7.tar.gz",
        dirs,
        configure_args=["--without-bash-malloc"]
    )

def build_nano(dirs):
    build_package(
        "nano",
        "http://ftp.gnu.org/gnu/nano/nano-1.0.0.tar.gz",
        dirs
    )

def build_make(dirs):
    build_package(
        "make",
        "http://ftp.gnu.org/gnu/make/make-3.75.tar.gz",
        dirs
    )
