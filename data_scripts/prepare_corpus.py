#!/usr/bin/env python3
import argparse
import tqdm
import multiprocessing
import os

MINIFER='~/node_modules/uglify-js/bin/uglifyjs'

def minify_file(fpath):
    if not fpath.endswith('.js'):
        return False, fpath

    out_file = fpath[:-3] + (".min.js" if not args.no_mangle else ".normalized.js")
    if not args.force and os.path.exists(out_file):
        return True, fpath

    options = "-m" if not args.no_mangle else ""
    cmd = "{} \"{}\" {} -o \"{}\" 2>/dev/null".format(MINIFER, fpath, options, out_file)
    return os.system(cmd) == 0, fpath


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("inp_filelist", type=str, help='Path to file containing filenames')
    parser.add_argument("--minify", default=False, action='store_true', help='Minify the files')
    parser.add_argument("--no-mangle", default=False, action='store_true', help='Mangle names?')
    parser.add_argument("--force", default=False, action='store_true', help='Force recomputation')
    args = parser.parse_args()

    with open(args.inp_filelist, 'r') as f:
        inpfiles = [line.lstrip().rstrip() for line in f]

    if args.minify:
        with multiprocessing.Pool() as p:
            success = []
            failed = []
            for res in tqdm.tqdm(p.imap_unordered(minify_file, inpfiles), total=len(inpfiles)):
                if res[0]:
                    success.append(res[1])
                else:
                    failed.append(res[1])

            with open('success.txt', 'w') as f:
                f.write("\n".join(success))

            with open('failed.txt', 'w') as f:
                f.write("\n".join(failed))
        




