#!/usr/bin/env python3
"""
image_flash.py - K3 image extraction and fastboot flash executor

Usage:
  # Extract all partition files from a GPT image into ./temp
  python image_flash.py --img card_boot.img --partition partition_universal.json

  # Compressed images (.zst) are also supported
  python image_flash.py --img card_boot.img.zst --partition partition_universal.json

  # Pack titan flasher format directory and compress to .tar.gz
  python image_flash.py --titan --titan-name MyImage --uboot-dir workdir/scratch/gadget/install/u-boot-spacemit

  # Extract files from image, and do image flash operation through fastboot
  python image_flash.py --img card_boot.img --partition partition_universal.json \
      --fastboot fastboot.yaml
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_size(s: str) -> int:
    """Convert size string ('640K', '4M', '1536K') to bytes. '-' returns -1."""
    if s == '-':
        return -1
    s = s.strip()
    if s.endswith('K'):
        return int(s[:-1]) * 1024
    if s.endswith('M'):
        return int(s[:-1]) * 1024 * 1024
    if s.endswith('G'):
        return int(s[:-1]) * 1024 * 1024 * 1024
    return int(s)


def load_json(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_yaml(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


_PROGRESS_THRESHOLD = 64 * 1024 * 1024   # show progress for partitions >= 64 MB
_COPY_CHUNK = 4 * 1024 * 1024            # 4 MB per read/write

def _copy_with_progress(src_f, dst_path: Path, size: int, label: str):
    """Copy `size` bytes from current position of src_f to dst_path, with progress for large parts."""
    show = size >= _PROGRESS_THRESHOLD
    written = 0
    with open(dst_path, 'wb') as dst:
        remaining = size
        while remaining > 0:
            chunk = src_f.read(min(_COPY_CHUNK, remaining))
            if not chunk:
                break
            dst.write(chunk)
            written += len(chunk)
            remaining -= len(chunk)
            if show:
                pct = written * 100 // size
                print(f"\r  [{label}] {written / (1024**2):.0f} / {size / (1024**2):.0f} MB  ({pct}%)",
                      end='', flush=True)
    if show:
        print()  # newline after progress line


def _decompress_stream(img_path: str):
    """Return a context manager yielding (stream, img_size_or_None).

    For plain images the file is opened directly (seekable, size known).
    For .zst images a zstd subprocess pipe is used (streaming, no temp file).
    """
    return _ImageSource(img_path)


class _ImageSource:
    """Context manager that provides either a seekable file or a zstd pipe."""

    def __init__(self, img_path: str):
        self.img_path = img_path
        self.streaming = img_path.endswith('.zst')
        self._proc = None
        self._f = None

    def __enter__(self):
        if self.streaming:
            cmd = ['zstd', '-d', '-T0', '-c', self.img_path]
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            self._f = self._proc.stdout
            self.size = None
        else:
            self._f = open(self.img_path, 'rb')
            self.size = os.path.getsize(self.img_path)
        return self

    def __exit__(self, *_):
        if self._f:
            self._f.close()
        if self._proc:
            self._proc.wait()
            if self._proc.returncode not in (0, None):
                sys.exit(f"ERROR: zstd exited with {self._proc.returncode}")

    def read(self, n):
        return self._f.read(n)

    def seek(self, offset):
        """Seek (seekable) or discard bytes to reach offset (streaming)."""
        if not self.streaming:
            self._f.seek(offset)
        else:
            # pos is tracked externally by the caller
            raise RuntimeError("seek() must not be called on streaming source")


# ---------------------------------------------------------------------------
# Feature 1: Extract partition files from a GPT image
# ---------------------------------------------------------------------------

TEMP_DIR = Path('./temp')
# These bootinfo files are not embedded in the image; they reside in the current directory.
_CURRENT_DIR_FILES = {'bootinfo_block.bin', 'bootinfo_spinand.bin'}
K3_FSBL_MAX_BYTE_SIZE = 464 * 1024

def _file_path(image: str) -> str:
    """Return the path to use in fastboot commands for a given image field."""
    name = Path(image).name
    if name in _CURRENT_DIR_FILES:
        return name
    return str(TEMP_DIR / name)


def extract_partitions(img_path: str, partition_json: str,
                       only: set = None, skip: set = None):
    """Extract each partition from the image into ./temp.

    Supports plain images (random access) and .zst compressed images
    (streamed via zstd pipe, no temporary file required).
    """
    config = load_json(partition_json)
    partitions = config.get('partitions', [])
    TEMP_DIR.mkdir(exist_ok=True)

    # Filter and prepare the list of partitions to extract.
    to_extract = []
    for part in partitions:
        name = part.get('name', '')
        image_rel = part.get('image', '')
        if not image_rel:
            print(f"  [{name}] no 'image' field, skipped")
            continue
        if only and name not in only:
            print(f"  [{name}] skipped (not in --only list)")
            continue
        if skip and name in skip:
            print(f"  [{name}] skipped (in --skip list)")
            continue
        if Path(image_rel).name in _CURRENT_DIR_FILES:
            print(f"  [{name}] current-dir file, skipped extraction")
            continue
        to_extract.append(part)

    with _decompress_stream(img_path) as src:
        img_size = src.size  # None for streaming
        size_label = f'{img_size:,} bytes' if img_size else 'streaming'
        print(f"[extract] image    : {img_path}  ({size_label})")
        print(f"[extract] partition: {partition_json}")
        print(f"[extract] output   : {TEMP_DIR}")
        print()

        if src.streaming:
            # Must read forward-only: sort by offset (size==-1 partitions last)
            to_extract.sort(key=lambda p: (
                parse_size(str(p.get('size', '-'))) == -1,
                parse_size(str(p.get('offset', '0'))),
            ))
            pos = 0  # bytes consumed from the stream so far
            for part in to_extract:
                name = part.get('name', '')
                image_rel = part.get('image', '')
                offset = parse_size(str(part.get('offset', '0')))
                size = parse_size(str(part.get('size', '-')))

                # Discard bytes up to the partition offset
                if offset > pos:
                    skip_bytes = offset - pos
                    _discard(src, skip_bytes)
                    pos += skip_bytes

                if size == -1:
                    # Read until stream ends
                    out_path = TEMP_DIR / Path(image_rel).name
                    written = _copy_stream_to_file(src, out_path, name)
                    pos += written
                else:
                    if name == 'fsbl':
                        size = min(size, K3_FSBL_MAX_BYTE_SIZE)
                    out_path = TEMP_DIR / Path(image_rel).name
                    _copy_with_progress(src, out_path, size, name)
                    pos += size

                print(f"  [{name}] offset=0x{offset:08X}  size={size:,}  -> {out_path}")
        else:
            for part in to_extract:
                name = part.get('name', '')
                image_rel = part.get('image', '')
                offset = parse_size(str(part.get('offset', '0')))
                size = parse_size(str(part.get('size', '-')))

                if size == -1:
                    size = img_size - offset
                if name == 'fsbl':
                    size = min(size, K3_FSBL_MAX_BYTE_SIZE)
                if offset + size > img_size:
                    print(f"  [{name}] WARNING: offset+size exceeds image, truncating")
                    size = img_size - offset

                src.seek(offset)
                out_path = TEMP_DIR / Path(image_rel).name
                _copy_with_progress(src, out_path, size, name)
                print(f"  [{name}] offset=0x{offset:08X}  size={size:,}  -> {out_path}")

    print()
    print("[extract] done")


def _discard(src, n: int):
    """Read and discard n bytes from src."""
    CHUNK = 4 * 1024 * 1024
    remaining = n
    while remaining > 0:
        chunk = src.read(min(CHUNK, remaining))
        if not chunk:
            break
        remaining -= len(chunk)


def _copy_stream_to_file(src, dst_path: Path, label: str) -> int:
    """Copy src until EOF into dst_path, showing progress. Returns bytes written."""
    CHUNK = 4 * 1024 * 1024
    written = 0
    with open(dst_path, 'wb') as dst:
        while True:
            chunk = src.read(CHUNK)
            if not chunk:
                break
            dst.write(chunk)
            written += len(chunk)
            print(f"\r  [{label}] {written / (1024**2):.0f} MB written", end='', flush=True)
    print()
    return written


# ---------------------------------------------------------------------------
# Feature 2: Parse fastboot.yaml and execute fastboot commands directly
# ---------------------------------------------------------------------------

def _run(cmd: list, retry: int = 1):
    """Run a fastboot command, retrying up to `retry` times on failure."""
    print(f"  $ {' '.join(cmd)}")
    for attempt in range(1, retry + 1):
        result = subprocess.run(cmd)
        if result.returncode == 0:
            return
        if attempt < retry:
            print(f"  [retry {attempt}/{retry}] command failed, retrying...")
    sys.exit(f"ERROR: command failed after {retry} attempt(s): {' '.join(cmd)}")


def _getvar(var: str) -> str:
    """Run 'fastboot getvar <var>' and return the value string, or '' on failure."""
    result = subprocess.run(
        ['fastboot', 'getvar', var],
        capture_output=True, text=True
    )
    # fastboot prints getvar output to stderr in the form "<var>: <value>"
    for line in (result.stdout + result.stderr).splitlines():
        if line.startswith(var + ':'):
            return line.split(':', 1)[1].strip()
    return ''


def _resolve_partition_file(size_str: str) -> str:
    """Find matched partition file."""
    import re
    candidate = f'partition_{size_str}.json'
    if os.path.exists(candidate):
        return candidate

    # Find partition_<N>M.json by halving N until a file is found.
    m = re.fullmatch(r'(\d+)M', size_str.strip())
    if not m:
        return ''
    size_mb = int(m.group(1))
    while size_mb >= 1:
        candidate = f'partition_{size_mb}M.json'
        if os.path.exists(candidate):
            return candidate
        size_mb //= 2
    sys.exit("ERROR: no matching partition table found for mtd-size")


def _flash_partition_table(var: str, retry: int, log: list,
                           only: set = None, skip: set = None):
    """Query <var> from device, resolve matching partition file, and flash all partitions."""
    print(f"[flash] querying {var} from device...")
    size_str = _getvar(var)
    print(f"[flash] {var} = {size_str!r}")

    if not size_str or size_str.lower() == 'null':
        print(f"[flash] {var} is null, skipping")
        return

    partition_file = _resolve_partition_file(size_str)
    part_config = load_json(partition_file)
    fmt = part_config.get('format', '')
    print(f"[flash] using partition file: {partition_file}  (format: {fmt})")

    # When --only is active and none of the requested partitions exist in this
    # partition file, skip the entire phase (table flash + partition flash).
    # Example: --only esp has no targets in partition_4M.json (MTD), so the MTD
    # table flash is skipped entirely and the device stays in GPT context.
    if only:
        available = {p['name'] for p in part_config.get('partitions', []) if p.get('image')}
        if not available & only:
            print(f"[flash] --only: no target partitions in {partition_file}, skipping phase")
            return

    cmd = ['fastboot', 'flash', fmt, partition_file]
    log.append(' '.join(cmd))
    _run(cmd, retry)

    for part in part_config.get('partitions', []):
        if not part.get('image'):
            continue
        pname = part['name']
        if only and pname not in only:
            print(f"  [{pname}] skipped (not in --only list)")
            continue
        if skip and pname in skip:
            print(f"  [{pname}] skipped (in --skip list)")
            continue
        part_size = parse_size(str(part.get('size', '-')))
        file_path = _file_path(part['image'])
        if part_size > 0 and os.path.exists(file_path):
            actual = os.path.getsize(file_path)
            if actual > part_size:
                print(f"  [{pname}] truncating {actual:,} -> {part_size:,} bytes")
                data = Path(file_path).read_bytes()[:part_size]
                Path(file_path).write_bytes(data)
        cmd = ['fastboot', 'flash', pname, file_path]
        log.append(' '.join(cmd))
        _run(cmd, retry)


def _execute_actions(actions: list, log: list,
                     only: set = None, skip: set = None):
    """Execute fastboot.yaml actions sequentially, branching dynamically on device responses."""
    for action in actions:
        if 'getvar' in action:
            cfg = action['getvar']
            cmd = ['fastboot', 'getvar', cfg['args']]
            log.append(' '.join(cmd))
            _run(cmd, cfg.get('retry', 1))

        elif 'stage' in action:
            cfg = action['stage']
            cmd = ['fastboot', 'stage', str(TEMP_DIR / Path(cfg['file']).name)]
            log.append(' '.join(cmd))
            _run(cmd, cfg.get('retry', 1))

        elif 'continue' in action:
            cmd = ['fastboot', 'continue']
            log.append(' '.join(cmd))
            _run(cmd)
            time.sleep(10)  # wait for device to reboot and re-enumerate

        elif 'oem' in action:
            cfg = action['oem']
            cmd = ['fastboot', 'oem'] + cfg['args'].split()
            log.append(' '.join(cmd))
            _run(cmd, cfg.get('retry', 1))

        elif 'multi_flash' in action:
            cfg = action['multi_flash'] or {}
            retry = cfg.get('retry', 1)
            _flash_partition_table('mtd-size', retry, log, only=only, skip=skip)
            _flash_partition_table('blk-size', retry, log, only=only, skip=skip)


def _save_log(log: list):
    """Save executed commands to temp/flash.txt for inspection."""
    TEMP_DIR.mkdir(exist_ok=True)
    out = TEMP_DIR / 'flash.txt'
    out.write_text('\n'.join(log) + '\n', encoding='utf-8')
    print(f"[flash] log saved: {out}")


def run_flash(fastboot_yaml: str, only: set = None, skip: set = None):
    """Parse fastboot.yaml and execute all fastboot commands directly."""
    config = load_yaml(fastboot_yaml)
    log = []
    _execute_actions(config.get('actions', []), log, only=only, skip=skip)
    _save_log(log)
    print()
    print("[flash] done")


# ---------------------------------------------------------------------------
# Feature 3: Pack titan flasher format directory + compress to .tar.gz
# ---------------------------------------------------------------------------

# Files to exclude when copying from temp/ into the titan directory.
_TITAN_EXCLUDE = {'flash.txt'}

# Rename map applied to files copied from temp/.
_TITAN_RENAME = {}

# Files copied from the uboot install dir into titan/factory/.
_FACTORY_FILES = ('FSBL.bin', 'bootinfo_block.bin', 'bootinfo_spinand.bin', 'bootinfo_spinor.bin')

# Files copied from the uboot install dir into titan/ root.
_UBOOT_ROOT_FILES = ('u-boot.itb',)


def _truncate_titan_files(titan_dir: Path):
    """Truncate partition image files to fit the tightest partition size constraint.

    Scans all partition_*.json files inside titan_dir, builds a map of
    filename -> minimum partition size across all tables, then truncates any
    file that is larger than its allowed size.  This is needed because files
    are extracted from a GPT image where partitions are larger (e.g. esos=3M)
    than on MTD devices (e.g. esos=1M in partition_4M.json).
    """
    # Build filename -> minimum size map from all partition tables in titan_dir.
    size_map: dict = {}  # basename -> min allowed bytes
    for cfg_path in sorted(titan_dir.glob('partition_*.json')):
        config = load_json(str(cfg_path))
        for part in config.get('partitions', []):
            image = part.get('image', '')
            if not image:
                continue
            size = parse_size(str(part.get('size', '-')))
            if size <= 0:
                continue
            fname = Path(image).name
            if fname not in size_map or size < size_map[fname]:
                size_map[fname] = size

    # Truncate files that exceed their tightest constraint.
    for fname, max_size in sorted(size_map.items()):
        for candidate in (titan_dir / fname, titan_dir / 'factory' / fname):
            if not candidate.exists():
                continue
            actual = candidate.stat().st_size
            if actual > max_size:
                rel = candidate.relative_to(titan_dir)
                print(f"  truncate {rel}  {actual / 1024:.0f}K -> {max_size / 1024:.0f}K")
                data = candidate.read_bytes()[:max_size]
                candidate.write_bytes(data)


def pack_titan(temp_dir: Path, uboot_dir: Path, name: str, out_dir: Path):
    """Pack extracted partitions into a titan flasher directory and compress.

    Directory layout produced:
      <out_dir>/<name>/
        env.bin, esos.itb, esp.vfat, fw_dynamic.itb, edk2.itb, rootfs.ext4 ...
        factory/
          FSBL.bin, bootinfo_block.bin, bootinfo_spinand.bin, bootinfo_spinor.bin
        u-boot.itb
        fastboot.yaml
        partition_*.json
      <out_dir>/<name>.tar.gz  (parallel-compressed with pigz when available)
    """
    import shutil

    titan_dir = out_dir / name
    print(f"[titan] output dir : {titan_dir}")
    titan_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. Copy partition files from temp/ --------------------------------
    print(f"[titan] copying partitions from {temp_dir} ...")
    for src in sorted(temp_dir.iterdir()):
        if src.name in _TITAN_EXCLUDE:
            print(f"  skip  {src.name}")
            continue
        dst_name = _TITAN_RENAME.get(src.name, src.name)
        dst = titan_dir / dst_name
        if src.is_file():
            print(f"  copy  {src.name}" + (f"  ->  {dst_name}" if dst_name != src.name else ""))
            shutil.copy2(src, dst)
        elif src.is_dir():
            print(f"  copy  {src.name}/  ->  {dst_name}/")
            shutil.copytree(src, dst, dirs_exist_ok=True)

    # ---- 2. Add files from the uboot install directory ---------------------
    factory_dir = titan_dir / 'factory'
    factory_dir.mkdir(exist_ok=True)

    print(f"[titan] copying u-boot files from {uboot_dir} ...")
    for fname in _UBOOT_ROOT_FILES:
        src = uboot_dir / fname
        dst = titan_dir / fname
        if src.exists():
            print(f"  copy  {fname}")
            shutil.copy2(src, dst)
        else:
            print(f"  WARN  {fname} not found in {uboot_dir}, skipped")

    for fname in _FACTORY_FILES:
        src = uboot_dir / fname
        dst = factory_dir / fname
        if src.exists():
            print(f"  copy  factory/{fname}")
            shutil.copy2(src, dst)
        else:
            print(f"  WARN  factory/{fname} not found in {uboot_dir}, skipped")

    # ---- 3. Copy workspace config files ------------------------------------
    print(f"[titan] copying config files ...")
    config_sources = sorted(Path('.').glob('partition_*.json')) + [Path('fastboot.yaml')]
    for cfg in config_sources:
        if cfg.exists():
            print(f"  copy  {cfg.name}")
            shutil.copy2(cfg, titan_dir / cfg.name)

    # ---- 4. Truncate files to fit the smallest partition size ---------------
    # Some files are extracted from a large GPT partition slot (e.g. esos 3M)
    # but must fit into a smaller MTD partition (e.g. esos 1M).  Scan every
    # partition_*.json that was just copied into the titan dir and truncate any
    # file that exceeds its tightest size constraint.
    print(f"[titan] checking partition size constraints ...")
    _truncate_titan_files(titan_dir)

    print(f"\n[titan] directory ready: {titan_dir}")

    # ---- 5. Compress in parallel -------------------------------------------
    archive = out_dir / f"{name}.tar.gz"
    print(f"[titan] compressing -> {archive}")

    pigz_bin = shutil.which('pigz')
    if pigz_bin:
        cmd = ['tar', '-I', pigz_bin, '-cf', str(archive), '-C', str(titan_dir), '.']
    else:
        cmd = ['tar', '-czf', str(archive), '-C', str(titan_dir), '.']
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"ERROR: compression failed (exit {result.returncode})")

    print(f"[titan] archive  : {archive}")
    print(f"[titan] done")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Default path to the u-boot gadget install directory (override with --uboot-dir).
GADGET_INSTALL_DEFAULT = 'workdir/scratch/gadget/install/u-boot-spacemit'


def main():
    parser = argparse.ArgumentParser(
        description='K3 image extraction and fastboot flash script generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--img', help='GPT image file, e.g. card_boot.img')
    parser.add_argument('--partition', help='Partition table JSON for the image, e.g. partition_universal.json')
    parser.add_argument('--fastboot', help='Flash flow control file, e.g. fastboot.yaml')
    parser.add_argument('--only', metavar='PART[,PART...]',
                        help='Only flash these comma-separated partition names, e.g. --only esp')
    parser.add_argument('--skip', metavar='PART[,PART...]',
                        help='Skip these comma-separated partition names, e.g. --skip writable')

    # titan flasher pack options
    parser.add_argument('--titan', action='store_true',
                        help='Pack titan flasher format directory and compress to .tar.gz')
    parser.add_argument('--titan-name', default='',
                        help='Base name for the titan output directory/archive '
                             '(default: derived from --img basename)')
    parser.add_argument('--uboot-dir', default=GADGET_INSTALL_DEFAULT,
                        help='Path to the u-boot install directory containing '
                             'u-boot.itb, FSBL.bin, bootinfo_*.bin '
                             f'(default: {GADGET_INSTALL_DEFAULT})')
    parser.add_argument('--titan-out', default='.',
                        help='Output directory for the titan archive (default: .)')
    parser.add_argument('--titan-temp', default=str(TEMP_DIR),
                        help=f'Temp directory with extracted partition files (default: {TEMP_DIR})')

    args = parser.parse_args()

    only = set(args.only.split(',')) if args.only else None
    skip = set(args.skip.split(',')) if args.skip else None
    if only and skip:
        parser.error('--only and --skip are mutually exclusive')

    did_something = False

    if args.img or args.partition:
        if not args.img:
            parser.error('--partition requires --img')
        if not args.partition:
            parser.error('--img requires --partition')
        extract_partitions(args.img, args.partition, only=only, skip=skip)
        did_something = True

    if args.fastboot:
        run_flash(args.fastboot, only=only, skip=skip)
        did_something = True

    if args.titan:
        titan_name = args.titan_name
        if not titan_name:
            if args.img:
                stem = Path(args.img).name
                for ext in ('.zst', '.img'):
                    if stem.endswith(ext):
                        stem = stem[:-len(ext)]
                titan_name = stem
            else:
                parser.error('--titan requires either --titan-name or --img to derive a name')
        pack_titan(
            temp_dir=Path(args.titan_temp),
            uboot_dir=Path(args.uboot_dir),
            name=titan_name,
            out_dir=Path(args.titan_out),
        )
        did_something = True

    if not did_something:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
