import os
import multiprocessing
from pathlib import Path

from utils.download import download_file, extract_archive
from utils.execute import run_command_live
from utils.load import load_config

def resolve_build_order(packages: dict) -> list[str]:
    visited, order = {}, []
    def visit(name: str):
        if name in visited:
            if visited[name] == "temp":
                raise RuntimeError(f"Zirkuläre Abhängigkeit entdeckt bei {name}")
            return
        visited[name] = "temp"
        for dep in packages[name].get("deps", []):
            if dep not in packages:
                raise RuntimeError(f"Unbekannte Abhängigkeit {dep} für Paket {name}")
            visit(dep)
        visited[name] = "perm"
        order.append(name)
    for pkg in packages:
        visit(pkg)
    return order

def load_all_packages(configs_dir: Path) -> dict:
    packages = {}
    for cfg_file in (configs_dir / "packages").glob("*.json"):
        conf = load_config(cfg_file)
        packages[conf["name"]] = conf
    return packages

def build_generic(args, conf, work_dir: Path, downloads_dir: Path, rootfs_dir: Path):
    version = conf["version"]
    src_dir_template = conf["src_dir"]
    src_dir = Path(src_dir_template.format(version=version))

    print(f"\n=== Baue Paket: {conf['name']} {version} ===")
    tarball = download_file(conf["urls"], downloads_dir)
    extract_archive(tarball, work_dir)
    print(f"Console > Quellverzeichnis: {src_dir}")

    # Cross-Compile Umgebung
    env = os.environ.copy()
    arch = args.arch if args.arch else "x86_64"
    host = "aarch64-linux-gnu" if arch in ("arm64", "aarch64") else "x86_64-linux-gnu"
    prefix = "aarch64-linux-gnu-" if host.startswith("aarch64") else ""
    env["CC"] = f"{prefix}gcc"
    env["CXX"] = f"{prefix}g++"

    # Configure-Phase
    if "configure" in conf:
        # Exakte Vorgaben aus JSON (z.B. OpenSSL: ["perl","Configure","linux-aarch64",...])
        cmd = conf["configure"]
        run_command_live(cmd, cwd=src_dir, env=env, desc=f"{conf['name']}: custom configure")
    else:
        configure_script = src_dir / "configure"
        if configure_script.exists():
            cmd = ["./configure", f"--host={host}", "--prefix=/usr"]
            run_command_live(cmd, cwd=src_dir, env=env, desc=f"{conf['name']}: configure")
        else:
            print(f"⚠️  Kein configure-Skript gefunden und keine Vorgaben in JSON – überspringe configure.")

    # Build & Install
    num_cores = multiprocessing.cpu_count()
    run_command_live(["make", f"-j{num_cores}"], cwd=src_dir, env=env, desc=f"{conf['name']}: build")
    run_command_live(["make", f"DESTDIR={rootfs_dir}", "install"], cwd=src_dir, env=env, desc=f"{conf['name']}: install")

    print(f"✅ {conf['name']} {version} erfolgreich installiert in {rootfs_dir}")



def build_all(args, configs_dir: Path, work_dir: Path, downloads_dir: Path, rootfs_dir: Path):
    packages = load_all_packages(configs_dir)
    build_order = resolve_build_order(packages)
    print(f"📦 Build-Reihenfolge: {', '.join(build_order)}")

    failed = []
    for name in build_order:
        conf = packages[name]
        try:
            build_generic(args, conf, work_dir, downloads_dir, rootfs_dir)
        except Exception as e:
            print(f"❌ Fehler beim Bauen von {name}: {e}")
            failed.append(name)
            if not getattr(args, "ignore_errors", False):
                raise
            else:
                print("➡️  Ignoriere Fehler und fahre mit dem nächsten Paket fort.")
                continue

    if failed:
        print("\n⚠️ Folgende Pakete konnten nicht gebaut werden:")
        for n in failed:
            print(f"  - {n}")
    else:
        print("\n✅ Alle Pakete erfolgreich gebaut!")
