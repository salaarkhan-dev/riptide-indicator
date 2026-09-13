#!/usr/bin/env python3
"""
Riptide scanner — entry point.

The implementation lives in the `riptide` package alongside this file; this
stays a thin launcher so the systemd unit's ExecStart never has to change.

Alerts only. No exchange key, no order path.
"""

import asyncio
import sys

from riptide.app import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
