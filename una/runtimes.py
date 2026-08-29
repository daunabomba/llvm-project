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
    print(f"LLVM-Runtime: target_configure (libcxx, libcxxabi, libunwind) for {arch}")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / f"build-runtime-{arch}"
    build_path.mkdir(parents=True, exist_ok=True)
    
    project_root = repo_root.parent.parent
    musl_cfg = project_root / "bld" / f"musl_{arch}.cfg"

    target = get_target_triple(arch)

    narrowing_flag = " -Wno-narrowing" if arch == "x32" else ""
    cpp_narrowing_flag = " -Wno-c++11-narrowing" if arch == "x32" else ""

    cmd = [
        "cmake",
        "-G", "Ninja",
        "-S", "runtimes", 
        "-B", str(build_path),
        f"-DCMAKE_INSTALL_PREFIX=/usr",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DLLVM_ENABLE_RUNTIMES=libcxx;libcxxabi;libunwind",
        
        # Cross-compilation settings
        "-DCMAKE_C_COMPILER=clang",
        "-DCMAKE_CXX_COMPILER=clang++",
        
        # Using C toolchain config to avoid circular dependency during bootstrap
        f"-DCMAKE_ASM_FLAGS={os.environ.get('CFLAGS', '')}{narrowing_flag}",
        f"-DCMAKE_C_FLAGS={os.environ.get('CFLAGS', '')}{narrowing_flag}",
        f"-DCMAKE_CXX_FLAGS={os.environ.get('CFLAGS', '')}{cpp_narrowing_flag}",
        
        f"-DLLVM_DEFAULT_TARGET_TRIPLE={target}",
        
        "-DLIBUNWIND_ENABLE_SHARED=ON",
        "-DLIBUNWIND_ENABLE_STATIC=ON",
        
        "-DLIBCXX_HAS_MUSL_LIBC=ON",
        "-DLIBCXX_ENABLE_SHARED=ON",
        "-DLIBCXX_ENABLE_STATIC=ON",
        "-DLIBCXX_CXX_ABI=libcxxabi",
        
        "-DLIBCXXABI_USE_LLVM_UNWINDER=ON",
        "-DLIBCXXABI_ENABLE_SHARED=ON",
        "-DLIBCXXABI_ENABLE_STATIC=ON",
        "-DLIBCXXABI_USE_COMPILER_RT=ON",
        
        "-DCOMPILER_RT_DEFAULT_TARGET_ONLY=ON",
        f"-DCMAKE_C_COMPILER_TARGET={target}",
    ]

    _get_runner().run(cmd, cwd=repo_root, env=get_build_env(), check=True)

def target_headers_install(staging_dir: Path, target_dir: Path, arch="x32"):
    pass

def target_build(staging_dir: Path, target_dir: Path, arch="x32"):
    print(f"LLVM-Runtime: target_build ({arch})")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / f"build-runtime-{arch}"
    
    make_jobs = multiprocessing.cpu_count()
    _get_runner().run(["ninja", "-v", f"-j{make_jobs}"], cwd=build_path, env=get_build_env(), check=True)

def target_install(staging_dir: Path, target_dir: Path, arch="x32"):
    print(f"LLVM-Runtime: target_install ({arch})")
    repo_root = Path(__file__).parent.parent
    build_path = repo_root / f"build-runtime-{arch}"
    
    # 1. Install EVERYTHING to staging (Headers and Libs)
    print(f"Installing all runtime components to staging: {staging_dir}")
    _get_runner().run(["env", f"DESTDIR={staging_dir}", "ninja", "install"], cwd=build_path, env=get_build_env(), check=True)
    
    # 2. Install ONLY LIBRARIES to target
    print(f"Installing libraries to target: {target_dir}")
    _get_runner().run(["env", f"DESTDIR={target_dir}", "ninja", "install"], cwd=build_path, env=get_build_env(), check=True)
    
    # Cleanup header files from unwind/abi in target
    target_usr_include = target_dir / "usr" / "include"
    print(f"Purging C++/Runtime headers from target to keep image lean: {target_usr_include}")
    
    _get_runner().run(f"rm -rf {target_usr_include}/c++ {target_usr_include}/compiler-rt", shell=True, check=False)
    _get_runner().run(f"rm -f {target_usr_include}/*unwind* {target_usr_include}/cxxabi.h", shell=True, check=False)

    # Optional: cleanup static libs in target
    _get_runner().run(f"rm -f {target_dir}/usr/lib/*.a", shell=True, check=False)
