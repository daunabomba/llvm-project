import subprocess
import os
import multiprocessing
from pathlib import Path

def tools_configure(install_dir: Path, arches=None):
    if arches is None:
        arches = ["x32"]
    
    print(f"LLVM-Tools: tools_configure (install_dir={install_dir}, arches={arches})")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / "build-tools"
    build_path.mkdir(parents=True, exist_ok=True)

    # Map our arch names to LLVM backend names
    arch_map = {
        "x32": "X86",
        "x86_64": "X86",
        "aarch64": "AArch64",
        "riscv64": "RISCV"
    }
    
    llvm_targets = set()
    for a in arches:
        if a in arch_map:
            llvm_targets.add(arch_map[a])
        else:
            print(f"Warning: Unknown architecture '{a}', skipping LLVM backend selection.")
    
    if not llvm_targets:
        llvm_targets.add("X86") # Fallback
        
    targets_str = ";".join(sorted(list(llvm_targets)))
    print(f"LLVM-Tools: Building backends: {targets_str}")

    cmd = [
        "cmake",
        "-G", "Ninja",
        "-S", "llvm", 
        "-B", str(build_path),
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DLLVM_ENABLE_PROJECTS=clang;lld",
        f"-DLLVM_TARGETS_TO_BUILD={targets_str}",
        "-DLLVM_INCLUDE_TESTS=OFF",
        "-DLLVM_ENABLE_RTTI=ON",
        "-DLLVM_ENABLE_LIBXML2=OFF",
    ]

    env = os.environ.copy()
    env["CC"] = "clang"
    env["CXX"] = "clang++"

    subprocess.run(cmd, cwd=repo_root, env=env, check=True)

def tools_build(install_dir: Path):
    print(f"LLVM-Tools: tools_build")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / "build-tools"
    
    env = os.environ.copy()
    env["CC"] = "clang"
    env["CXX"] = "clang++"
    
    make_jobs = multiprocessing.cpu_count()
    subprocess.run(["ninja", f"-j{make_jobs}"], cwd=build_path, env=env, check=True)

def tools_install(install_dir: Path):
    print(f"LLVM-Tools: tools_install")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / "build-tools"
    
    env = os.environ.copy()
    env["CC"] = "clang"
    env["CXX"] = "clang++"
    
    subprocess.run(["ninja", "install"], cwd=build_path, env=env, check=True)
