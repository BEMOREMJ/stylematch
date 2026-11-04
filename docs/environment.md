# Accessible environment evidence

Observed 2026-11-04 at 14:43:50 Africa/Nairobi (11:43:50 UTC), using
`.venv\Scripts\python.exe scripts/inventory.py`. Availability values are snapshots.
At 001A this host's intended-machine status was unconfirmed. For 001B, the owner
**confirmed this inventoried Windows laptop as the intended initial inference
machine**. This confirmation does not establish a model execution budget.

| Field | Observed evidence |
| --- | --- |
| OS / architecture | Windows 11, build 10.0.22631, AMD64 |
| CPU | Intel Core i7-6600U @ 2.60 GHz, 4 logical processors |
| RAM | Total 17,054,662,656 bytes (15.88 GiB); available 2,301,517,824 bytes (2.14 GiB) |
| Graphics | Registry reports Intel HD Graphics 520 |
| VRAM | Unknown; reliable dedicated VRAM not measured; nvidia-smi not available |
| Workspace volume | Total 255,045,136,384 bytes; free 14,848,835,584 bytes (13.83 GiB) |
| Initially available Python | Default 3.14.2; launcher also lists 3.11; 3.12 initially absent |
| Project interpreter | uv-managed CPython 3.12.14, local ignored `.tools/python`, no PATH installation |
| uv | 0.12.9, x86_64-pc-windows-msvc |
| Validated dependencies | Pydantic 2.14.2 and pytest 9.2.0; exact transitives/hashes in `uv.lock` |

Initial CIM OS/CPU/GPU queries returned access denied. Read-only Windows
GlobalMemoryStatusEx, registry, platform and filesystem queries supplied the
available evidence. Registry graphics adapter memory is not accepted as reliable
dedicated VRAM, particularly for shared graphics. Physical core count is unknown.
The inventory script reports limitations instead of inventing values; it has
Windows-specific RAM/graphics discovery and degrades explicitly on other hosts.

The first sandboxed uv interpreter download failed with unreachable network
(Windows socket error 10051). Retrying through the permitted network escalation
succeeded. uv installed the small project interpreter/dependencies only; no
substantial system dependencies, weights or datasets were installed. The default
Python version was not silently substituted for the required Python 3.12.

The first test run had 68 passes and 2 setup errors because the sandbox could
not inspect an existing user-wide pytest temp directory. Pytest now uses the
ignored workspace `.pytest_cache/tmp`; the subsequent complete run passed. This
was a test-environment failure, not a model experiment or resource result.

No model RAM, latency, VRAM or throughput measurements were made. Device support,
background load, storage headroom and approved resource budgets remain to be
established before model experiments. The 001B owner confirmation resolves
intended-machine identity only. Pillow was added for preparation; exact current
dependencies remain in `uv.lock`.
