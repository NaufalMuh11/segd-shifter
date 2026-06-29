#!/usr/bin/env python3
"""
Convert Fairfield Nodal SEG-D (Z-Land/ZNode) to SEG-Y.

Pure Python — no ObsPy needed. Reads raw SEG-D byte stream with Fairfield
quirks (scan_type/chan_set in demux header are raw binary, not BCD).

Usage:
    python convert_fairfield.py /data/*.SEGD -o /output/
    python convert_fairfield.py data/FFID_101.SEGD -o output/ -v
"""

import os
import re
import sys
import struct
import argparse
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────

def _rd_be16(buf, off=0):
    """Read big-endian uint16."""
    return (buf[off] << 8) | buf[off + 1]


def _rd_be32(buf, off=0):
    """Read big-endian uint32."""
    return (_rd_be16(buf, off) << 16) | _rd_be16(buf, off + 2)


def _bcd_nibbles(raw, start_nib, n):
    """Nibble-based BCD decode. nibble_index = byte*2 + 0(high)/1(low)."""
    val = 0
    for i in range(n):
        nib = start_nib + i
        b = raw[nib // 2]
        shift = 4 * (1 - (nib & 1))
        val = val * 10 + ((b >> shift) & 0x0F)
    return val


# ── SEG-Y writer ───────────────────────────────────────────────────────────

def _pack_be16(buf, off, v):
    buf[off:off+2] = struct.pack('>H', v)


def _pack_be32(buf, off, v):
    buf[off:off+4] = struct.pack('>I', v)


def _pack_fl32(v):
    return struct.pack('>f', v)


def _make_segy_text_header(inpath: str) -> bytes:
    from datetime import datetime
    now = datetime.now()
    txt = f"Fairfield SEG-D -> SEG-Y  Input: {inpath}  {now:%Y-%m-%d %H:%M:%S}"
    return txt.encode().ljust(3200, b' ')


def _make_segy_bin_header(ns: int, dt_us: int) -> bytes:
    buf = bytearray(400)
    _pack_be16(buf, 16, dt_us)     # sample interval μs
    _pack_be16(buf, 18, dt_us)     # original sample interval
    _pack_be16(buf, 20, ns)        # samples/trace
    _pack_be16(buf, 22, ns)        # original samples/trace
    _pack_be16(buf, 24, 5)         # data format: IEEE float
    _pack_be16(buf, 300, 0x0100)  # SEG-Y Rev 1
    _pack_be16(buf, 302, 1)        # fixed trace length
    return bytes(buf)


def _make_segy_trh(tracl, fldr, tracf, ep, trid, ns, dt, delrt,
                   yr, day, h, m, s) -> bytes:
    buf = bytearray(240)
    _pack_be32(buf, 0, tracl)
    _pack_be32(buf, 8, fldr)
    _pack_be32(buf, 12, tracf)
    _pack_be32(buf, 16, ep)
    _pack_be16(buf, 28, trid)
    _pack_be16(buf, 108, delrt)
    _pack_be16(buf, 114, ns)
    _pack_be16(buf, 116, dt)
    _pack_be16(buf, 156, yr)
    _pack_be16(buf, 158, day)
    _pack_be16(buf, 160, h)
    _pack_be16(buf, 162, m)
    _pack_be16(buf, 164, s)
    return bytes(buf)


# ── SEG-D reader ───────────────────────────────────────────────────────────

SEGD_BLOCK = 32
DEMUX_TRH_SIZE = 20


def _read_block(fin) -> bytes | None:
    blk = fin.read(SEGD_BLOCK)
    return blk if len(blk) == SEGD_BLOCK else None


def _decode_8015(buf: bytes, ns: int) -> list[float]:
    """Decode Format 8015: 10 bytes → 4 IEEE floats."""
    samples = [0.0] * ns
    off = 0
    i = 0
    while i < ns:
        ep = _rd_be16(buf, off)
        for c in range(4):
            expo = ((ep >> (4 * (3 - c))) & 0x0F) - 15
            frac = struct.unpack('>h', buf[off + 2 + 2 * c: off + 4 + 2 * c])[0]
            if i + c < ns:
                samples[i + c] = float(frac) * (2.0 ** expo)
        off += 10
        i += 4
    return samples


def read_segd(path: str, verbose: bool = False, gain: bool = False,
              ns_override: int = 0, ffid_override: int = 0):
    """Read Fairfield SEG-D file, yield trace dicts.

    Yields dicts with keys: trid, tracf, ep, data (list[float]), and
    timing fields (year, day, hour, minute, second, delrt).
    """

    import math

    fin = open(path, 'rb')
    try:
        blk = _read_block(fin)
        if blk is None:
            raise ValueError("Can't read General Header #1")

        # ── GH1 ────────────────────────────────────────────────────────
        file_num = _bcd_nibbles(blk, 0, 4)        # bytes 0-1
        fmt_code = _rd_be16(blk, 2)                # bytes 2-3
        yr_bcd = _bcd_nibbles(blk, 20, 2)          # byte 10
        n_gh = blk[11] >> 4                        # byte 11 hi nibble
        day = ((blk[11] & 0x0F) * 100
               + (blk[12] >> 4) * 10
               + (blk[12] & 0x0F))                 # bytes 11-12
        hour = _bcd_nibbles(blk, 26, 2)            # byte 13
        minute = _bcd_nibbles(blk, 28, 2)          # byte 14
        second = _bcd_nibbles(blk, 30, 2)          # byte 15
        mfg_code = blk[16]                         # byte 16
        hdr1_i = blk[22]                           # byte 22
        rec_len = _bcd_nibbles(blk, 51, 3)         # byte 25 lo + byte 26
        n_str = _bcd_nibbles(blk, 54, 2)           # byte 27
        n_cs = _bcd_nibbles(blk, 56, 2)            # byte 28
        n_sk = _bcd_nibbles(blk, 58, 2)            # byte 29
        n_ec = _bcd_nibbles(blk, 60, 2)            # byte 30
        n_ex = _bcd_nibbles(blk, 62, 2)            # byte 31

        year = yr_bcd + (2000 if yr_bcd < 30 else 1900)

        # ns from GH1
        ns = 0
        if rec_len != 999 and rec_len > 0 and hdr1_i > 0:
            r = rec_len * 2
            ns = (r * 512 * 16) // (10 * hdr1_i) + 1

        # sample interval μs
        dt_us = (hdr1_i * 1000) >> 4
        if dt_us < 100:
            dt_us = 2000

        if verbose:
            print(f"FFID={file_num}  Format={fmt_code:04X}  Mfg={mfg_code:02X}  "
                  f"Date={year}-{day:03d} {hour:02d}:{minute:02d}:{second:02d}",
                  file=sys.stderr)
            print(f"n_gh={n_gh}  rec_len={rec_len}  i={hdr1_i}  "
                  f"str={n_str}  cs={n_cs}  sk={n_sk}  ec={n_ec}  ex={n_ex}",
                  file=sys.stderr)
            print(f"ns(GH1)={ns}  dt={dt_us}us", file=sys.stderr)

        # ── GH2..N ─────────────────────────────────────────────────────
        n_gt = 0
        ep_val = 0
        for i in range(n_gh):
            blk = _read_block(fin)
            if blk is None:
                break
            if i == 0:
                n_gt = _rd_be16(blk, 14)
                if verbose:
                    print(f"GH2: rev={blk[10]:02x}{blk[11]:02x}  n_gt={n_gt}",
                          file=sys.stderr)
            elif i == 1:
                ep_val = _bcd_nibbles(blk, 16, 5)
                if verbose:
                    print(f"GH3: SP={ep_val}", file=sys.stderr)

        # ── Channel Set Headers ────────────────────────────────────────
        csh_data = []
        n_chan = 0
        if n_str > 0 and n_cs > 0:
            for s in range(n_str):
                for c in range(n_cs):
                    blk = _read_block(fin)
                    if blk is None:
                        break
                    cs = list(blk)
                    n_chan += _bcd_nibbles(blk, 0, 4)
                    csh_data.append(cs)
                for _ in range(n_sk):
                    _read_block(fin)

        if verbose and csh_data:
            for idx, cs in enumerate(csh_data):
                chcnt = _bcd_nibbles(cs, 0, 4)
                print(f"  CS[{idx // n_cs}][{idx % n_cs}]: "
                      f"chans={chcnt} type={cs[8]:02x} "
                      f"tf={_rd_be16(cs, 4)} te={_rd_be16(cs, 6)} "
                      f"mp={cs[10]:02x}{cs[11]:02x}",
                      file=sys.stderr)

        if verbose:
            print(f"Total channels: {n_chan}", file=sys.stderr)

        # Fallback ns from channel set
        if (ns == 0 or ns > 100000) and csh_data and hdr1_i > 0:
            cs = csh_data[0]
            te = _rd_be16(cs, 6)
            tf = _rd_be16(cs, 4)
            if te > tf:
                ns = 2 * (te - tf) * (16 << (cs[9] >> 4)) // hdr1_i + 1

        if ns_override > 0:
            ns = ns_override
        if ns <= 0 or ns > 100000:
            ns = 4000

        if verbose:
            print(f"ns={ns}  dt={dt_us}us  n_chan={n_chan}  "
                  f"n_gt={n_gt}  SP={ep_val}", file=sys.stderr)

        # ── Skip extended & external headers ───────────────────────────
        for _ in range(n_ec):
            _read_block(fin)
        for _ in range(n_ex):
            _read_block(fin)

        # ── Trace loop ─────────────────────────────────────────────────
        nbytes = ((ns + 3) // 4) * 10
        use_ffid = ffid_override if ffid_override else file_num
        nwritten = 0
        tif = 0

        while True:
            dth = fin.read(DEMUX_TRH_SIZE)
            if len(dth) != DEMUX_TRH_SIZE:
                if verbose:
                    print(f"  EOF at trace {nwritten}/{n_chan}",
                          file=sys.stderr)
                break

            scan_raw = dth[2]        # scan type — RAW on Fairfield
            chan_raw = dth[3]        # chan set — RAW on Fairfield
            trace_nr = _bcd_nibbles(dth, 8, 4)
            the = dth[9]             # trace header ext count

            for _ in range(the):
                _read_block(fin)

            # trace type
            trid = 1
            si = scan_raw if scan_raw < n_str else 0
            ci = chan_raw if chan_raw < n_cs else 0
            if csh_data:
                idx = si * n_cs + ci
                if idx < len(csh_data):
                    cs = csh_data[idx]
                    t = cs[8]
                    if t == 0x10:   trid = 1
                    elif t == 0x20: trid = 3   # time break
                    elif t == 0x30: trid = 4   # uphole
                    elif t == 0x40: trid = 9   # water break
                    else:           trid = 2   # dead/aux

            raw = fin.read(nbytes)
            if len(raw) < nbytes:
                raw = raw.ljust(nbytes, b'\x00')
            samples = _decode_8015(raw, ns) if raw else [0.0] * ns

            # gain
            if gain and csh_data:
                idx = si * n_cs + ci
                if idx < len(csh_data):
                    cs = csh_data[idx]
                    mp_raw = ((cs[11] & 0x7F) << 8) | cs[10]
                    mp = mp_raw / 1024.0
                    if cs[11] >> 7:
                        mp = -mp
                    g = 2.0 ** mp
                    if g != 1.0:
                        samples = [s * g for s in samples]

            tif += 1
            if trace_nr == 0:
                trace_nr = tif

            # delay
            delrt = 0
            if csh_data:
                delrt = _rd_be16(csh_data[0], 4) * 2

            yield {
                'trid': trid,
                'tracf': trace_nr,
                'ep': ep_val,
                'data': samples,
                'ns': ns,
                'dt_us': dt_us,
                'delrt': delrt,
                'year': year,
                'day': day,
                'hour': hour,
                'minute': minute,
                'second': second,
                'tracl': nwritten + 1,
                'fldr': use_ffid,
            }
            nwritten += 1
            if verbose and nwritten % 100 == 0:
                print(f"  {nwritten} traces", file=sys.stderr)

        # skip general trailer
        for _ in range(n_gt):
            _read_block(fin)

        if verbose:
            print(f"Done: {nwritten} traces", file=sys.stderr)

    finally:
        fin.close()


# ── CLI ────────────────────────────────────────────────────────────────────

def convert_one(inpath: str, outpath: str, verbose: bool = False,
                gain: bool = False, ns_override: int = 0,
                ffid_override: int = 0) -> bool:
    print(f"[+] Read: {inpath}")
    try:
        traces = list(read_segd(inpath, verbose=verbose, gain=gain,
                                ns_override=ns_override,
                                ffid_override=ffid_override))
    except Exception as e:
        print(f"    FAILED: {e}")
        return False

    if not traces:
        print("    No traces read.")
        return False

    ns = traces[0]['ns']
    dt_us = traces[0]['dt_us']
    first = traces[0]
    print(f"    Traces: {len(traces)}, Samples/trace: {ns}, "
          f"Rate: {1_000_000 / dt_us:.1f} Hz")

    with open(outpath, 'wb') as fout:
        # text header
        fout.write(_make_segy_text_header(inpath))
        # binary header
        fout.write(_make_segy_bin_header(ns, dt_us))
        # traces
        for tr in traces:
            trh = _make_segy_trh(
                tr['tracl'], tr['fldr'], tr['tracf'], tr['ep'],
                tr['trid'], ns, dt_us, tr['delrt'],
                tr['year'], tr['day'], tr['hour'], tr['minute'], tr['second'])
            fout.write(trh)
            for v in tr['data']:
                fout.write(_pack_fl32(v))

    print(f"[+] Write: {outpath}")
    return True


def main():
    p = argparse.ArgumentParser(
        description='Fairfield SEG-D → SEG-Y converter (pure Python)')
    p.add_argument('input', nargs='+', help='SEG-D file(s) or glob pattern')
    p.add_argument('-o', '--outdir', default='/output',
                   help='Output dir (default: /output)')
    p.add_argument('-v', '--verbose', action='store_true',
                   help='Verbose output')
    p.add_argument('--gain', action='store_true',
                   help='Apply gain')
    p.add_argument('--ns', type=int, default=0,
                   help='Override sample count')
    p.add_argument('--ffid', type=int, default=0,
                   help='Override FFID')
    args = p.parse_args()

    import glob as gb
    files = []
    for pat in args.input:
        f = gb.glob(pat)
        files.extend(f if f else ([pat] if os.path.isfile(pat) else []))

    if not files:
        print("No input files found.")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    ok = fail = 0
    for f in sorted(files):
        base = os.path.splitext(os.path.basename(f))[0]
        out = os.path.join(args.outdir, base + '.sgy')
        if convert_one(f, out, verbose=args.verbose, gain=args.gain,
                       ns_override=args.ns, ffid_override=args.ffid):
            ok += 1
        else:
            fail += 1

    print(f"\nDone: {ok} OK, {fail} FAILED")


if __name__ == '__main__':
    main()
