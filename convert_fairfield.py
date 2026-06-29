#!/usr/bin/env python3
"""
Convert Fairfield Nodal SEG-D (Z-Land/ZNode) to SEG-Y using ObsPy.

Usage:
    python convert_fairfield.py /data/*.SEGD -o /output/
    python convert_fairfield.py /data/FFID_101.SEGD -o /output/ --format su
"""

import sys, os, glob, argparse

try:
    from obspy import read
except ImportError as e:
    print(f"Error: {e}\nInstall: pip install obspy")
    sys.exit(1)


def convert_one(inpath, outpath):
    print(f"[+] Read: {inpath}")
    try:
        st = read(inpath, format='SEGD')
    except Exception as e:
        print(f"    FAILED: {e}")
        return False

    print(f"    Traces: {len(st)}, Samples/trace: {st[0].stats.npts}, "
          f"Rate: {st[0].stats.sampling_rate:.1f} Hz, Type: {st[0].data.dtype}")

    st.write(outpath, format='SEGY')
    print(f"[+] Write: {outpath}")
    return True


def main():
    p = argparse.ArgumentParser(description='Fairfield SEG-D → SEG-Y converter')
    p.add_argument('input', nargs='+', help='File(s) or glob')
    p.add_argument('-o', '--outdir', default='/output', help='Output dir')
    args = p.parse_args()

    files = []
    for pat in args.input:
        f = glob.glob(pat)
        files.extend(f if f else ([pat] if os.path.isfile(pat) else []))

    if not files:
        print("No input files found."); sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    ok = fail = 0
    for f in sorted(files):
        base = os.path.splitext(os.path.basename(f))[0]
        out = os.path.join(args.outdir, base + '.segy')
        (convert_one(f, out) and (ok := ok + 1)) or (fail := fail + 1)

    print(f"\nDone: {ok} OK, {fail} FAILED")


if __name__ == '__main__':
    main()
