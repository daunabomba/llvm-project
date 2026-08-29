import subprocess
import os
import multiprocessing
import shutil
from pathlib import Path
from mods.utils import get_target_triple
from mods.build import get_build_env, SubprocessRunner



# Module-level runner, initialized when needed
_runner = None

def _get_runner(trace_file=None):
    """Get or create the subprocess runner."""
    global _runner
    if _runner is None:
        _runner = SubprocessRunner(trace_file)
    return _runner

def set_trace_file(trace_file):
    """Set the trace file for subprocess logging."""
    global _runner
    _runner = SubprocessRunner(trace_file)

def target_configure(staging_dir: Path, target_dir: Path, arch="x32"):
    print(f"LLVM-Compiler-RT: target_configure for {arch}")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / f"build-compiler-rt-{arch}"
    build_path.mkdir(parents=True, exist_ok=True)

    target = get_target_triple(arch)

    # Undefine __linux__ so that builtins (like clear_cache.c) don't attempt to include 
    # Linux-specific libc headers (like assert.h or sys/auxv.h) during this baremetal build.

    mxflags  = "-mx32" if arch == "x32" else ""
    asmflags = f"{os.environ.get('CFLAGS', '')} {mxflags} -ffreestanding -U__linux__"
    cflags = f"{os.environ.get('CFLAGS', '')} {mxflags} -ffreestanding -U__linux__"
    cxxflags = f"{os.environ.get('CFLAGS', '')} {mxflags} -ffreestanding -U__linux__"

    cmd = [
        "cmake",
        "-G",
        "Ninja",
        "-S",
        "compiler-rt/lib/builtins",
        "-B",
        str(build_path),
        "-DCMAKE_INSTALL_PREFIX=/usr",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_C_COMPILER=clang",
        "-DCMAKE_CXX_COMPILER=clang++",
        # Using C toolchain config to avoid circular dependency during bootstrap
        f"-DCMAKE_ASM_FLAGS={asmflags}",
        f"-DCMAKE_C_FLAGS={cflags}",
        f"-DCMAKE_CXX_FLAGS={cxxflags}",
        f"-DCMAKE_C_COMPILER_TARGET={target}",
        f"-DCMAKE_CXX_COMPILER_TARGET={target}",
        f"-DLLVM_MAIN_SRC_DIR={repo_root.parent}/llvm",
        "-DCOMPILER_RT_DEFAULT_TARGET_ONLY=ON",
        "-DCOMPILER_RT_SHARED_LIB=ON",
        f"-DCMAKE_C_COMPILER_TARGET={target}",
        "-DCOMPILER_RT_BAREMETAL_BUILD=ON",
    ]

    _get_runner().run(cmd, cwd=repo_root, env=get_build_env(), check=True)


def target_headers_install(staging_dir: Path, target_dir: Path, arch="x32"):
    pass


def target_build(staging_dir: Path, target_dir: Path, arch="x32"):
    print(f"LLVM-Compiler-RT: target_build ({arch})")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / f"build-compiler-rt-{arch}"

    make_jobs = multiprocessing.cpu_count()
    _get_runner().run(
        ["ninja", "-v", f"-j{make_jobs}"], cwd=build_path, env=get_build_env(), check=True
    )


def target_install(staging_dir: Path, target_dir: Path, arch="x32"):
    print(f"LLVM-Compiler-RT: target_install ({arch})")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / f"build-compiler-rt-{arch}"

    print(f"Installing compiler-rt to staging: {staging_dir}")
    _get_runner().run(
        ["env", f"DESTDIR={staging_dir}", "ninja", "install"],
        cwd=build_path,
        env=get_build_env(),
        check=True,
    )

    # Rename libclang_rt.builtins-<arch>.a to libclang_rt.builtins-<arch>-bmf.a
    _get_runner().run(f"find {staging_dir} -name 'libclang_rt.builtins-*.a' ! -name '*-bmf*' | while read f; do mv \"$f\" \"${{f%.a}}-bmf.a\"; done", shell=True)
    if arch == "x32":
        # Override the x86_64-bmf.a -> x32-bmf.a
        for lib_path in Path(staging_dir).rglob("libclang_rt.builtins-x86_64-bmf.a"):
            new_path = lib_path.with_name("libclang_rt.builtins-x32-bmf.a")
            lib_path.rename(new_path)
            print(f"Renamed {lib_path} -> {new_path}")
