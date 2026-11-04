"""Read-only inventory; does not benchmark models or establish execution intent."""

import ctypes
from datetime import datetime, timezone
import json
import os
import platform
import shutil
import subprocess
import sys


def inventory():
    report = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "intended_inference_machine": "unconfirmed; accessible execution host only",
        "os": platform.platform(), "architecture": platform.machine(),
        "logical_processors": os.cpu_count(), "python": sys.version,
        "disk_bytes": shutil.disk_usage(".")._asdict(),
        "cpu": platform.processor(), "ram_bytes": None, "gpu_names": [],
        "vram_bytes": None, "limitations": [],
    }
    if sys.platform == "win32":
        import winreg

        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in (
                    "total_physical", "available_physical", "total_page", "available_page",
                    "total_virtual", "available_virtual", "available_extended",
                )
            ]

        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            report["ram_bytes"] = {"total": memory.total_physical, "available": memory.available_physical}
        else:
            report["limitations"].append("GlobalMemoryStatusEx failed")
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                report["cpu"] = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Video") as video:
                for index in range(winreg.QueryInfoKey(video)[0]):
                    try:
                        with winreg.OpenKey(video, winreg.EnumKey(video, index) + r"\0000") as adapter:
                            name = winreg.QueryValueEx(adapter, "DriverDesc")[0]
                            if name not in report["gpu_names"]:
                                report["gpu_names"].append(name)
                    except OSError:
                        continue
        except OSError as exc:
            report["limitations"].append(f"registry inventory incomplete: {exc}")
    else:
        report["limitations"].append("RAM/GPU discovery implemented for Windows only")
    report["limitations"].append("Reliable dedicated VRAM not measured; registry AdapterRAM is not sufficient")
    report["nvidia_smi_available"] = shutil.which("nvidia-smi") is not None
    try:
        report["uv"] = subprocess.run(["uv", "--version"], check=True, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        report["uv"] = None
        report["limitations"].append(f"uv version unavailable: {exc}")
    return report


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2))
