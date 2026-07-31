#!/usr/bin/env python3
"""Fast LP API probe: which PPA has a Published SOURCE for a package?

Used by gadget.in/Makefile pull_pkg BEFORE pull-ppa-debs, so packages that
only live in k3 (grub2, spacemit-ec-firmware are NOT in k3-preview) skip the
5x k3-preview retry loop entirely. ~2s vs 5x pull-ppa-debs (150s+ of 503s).

Args: <source_package_name> [series]
Prints: k3-preview | k3 | none
  - k3-preview: source Published in k3-preview (5x retry there)
  - k3:         not in k3-preview, Published in k3 (pull k3 directly)
  - none:       not in either (caller falls back to k3-preview anyway)

NOTE: checks SOURCE published, not binary-built. The k3-preview buildd-stuck
edge case (source Published, riscv64 binary not built) still falls through to
5x retry -> k3 fallback, but that's rare for the main BSP set (u-boot/linux/
opensbi/edk2/esos all have binaries built in k3-preview as of 1.0.5).
"""
import sys
import json
import urllib.request


def has_published_source(ppa, pkg):
    url = (
        f"https://api.launchpad.net/devel/~spacemit/+archive/ubuntu/{ppa}"
        f"?ws.op=getPublishedSources&source_name={pkg}&exact_match=true"
    )
    try:
        d = json.load(urllib.request.urlopen(url, timeout=15))
        return any(e.get("status") == "Published" for e in d.get("entries", []))
    except Exception:
        return None  # API error -> unknown, don't trust


def main():
    pkg = sys.argv[1]
    preview = has_published_source("k3-preview", pkg)
    if preview:
        print("k3-preview")
        return
    if preview is None:
        # API failed — default to k3-preview, let pull-ppa-debs decide (safe).
        print("k3-preview")
        return
    k3 = has_published_source("k3", pkg)
    print("k3" if k3 else "none")


if __name__ == "__main__":
    main()
