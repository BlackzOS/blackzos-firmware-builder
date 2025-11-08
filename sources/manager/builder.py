import os
import subprocess
import urllib.request
import tarfile
import hashlib
from pathlib import Path

class PackageBuilder:
    def __init__(self, app_dir: Path):
        # Basispfade relativ zu main.py
        self.app_dir = app_dir
        self.work_dir = app_dir / "work"
        self.downloads_dir = self.work_dir / "downloads"
        self.build_dir = self.work_dir / "build"
        self.output_dir = self.work_dir / "output"
        self.rootfs_dir = self.build_dir / "rootfs"
        self.bootfs_dir = self.build_dir / "bootfs"

        # Verzeichnisse erstellen
        for d in [self.downloads_dir, self.build_dir, self.output_dir, self.rootfs_dir, self.bootfs_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.arch = 'aarch64'

    def download(self, url, checksum=None):
        filename = self.downloads_dir / os.path.basename(url)
        if filename.exists():
            print(f"{filename} already exists. Skipping download.")
        else:
            print(f"Downloading {url} to {filename}...")
            urllib.request.urlretrieve(url, filename)
        if checksum:
            if not self.verify_checksum(filename, checksum):
                raise ValueError(f"Checksum mismatch for {filename}")
        return filename

    def verify_checksum(self, filename, checksum):
        sha256 = hashlib.sha256()
        with open(filename, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest() == checksum

    def extract(self, tar_path):
        extract_dir = self.build_dir / os.path.splitext(os.path.basename(tar_path))[0]
        if extract_dir.exists():
            print(f"{extract_dir} already extracted. Skipping extraction.")
            return extract_dir

        print(f"Extracting {tar_path} to {extract_dir}...")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar_path, 'r:*') as tar:
            tar.extractall(path=extract_dir)

        # Prüfe auf Unterverzeichnis
        subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        if len(subdirs) == 1:
            return subdirs[0]
        return extract_dir

    def run_cmd(self, cmd, cwd=None, env=None):
        print(f"Running: {' '.join(cmd)}")
        try:
            subprocess.check_call(cmd, cwd=cwd, env=env)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Command failed: {e}")

    def build_package(self, name, url, configure_opts=None, checksum=None):
        print(f"\n=== Building {name} ===")
        try:
            tar_path = self.download(url, checksum)
            src_dir = self.extract(tar_path)

            env = os.environ.copy()
            env.update({
                'CC': 'aarch64-linux-gnu-gcc',
                'CXX': 'aarch64-linux-gnu-g++',
                'AR': 'aarch64-linux-gnu-ar',
                'RANLIB': 'aarch64-linux-gnu-ranlib',
                'LD': 'aarch64-linux-gnu-ld',
            })

            configure_opts = configure_opts or []
            configure_cmd = ['./configure', f'--host={self.arch}-linux-gnu', '--prefix=/usr'] + configure_opts

            self.run_cmd(configure_cmd, cwd=src_dir, env=env)
            self.run_cmd(['make', '-j4'], cwd=src_dir, env=env)
            self.run_cmd(['make', f'DESTDIR={self.rootfs_dir}', 'install'], cwd=src_dir, env=env)

            print(f"{name} built and installed successfully in {self.rootfs_dir}")
        except Exception as e:
            print(f"Error building {name}: {e}")

    def build_packages(self, packages):
        for pkg in packages:
            self.build_package(**pkg)
