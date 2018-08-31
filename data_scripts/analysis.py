#!/usr/bin/env python3
import os, argparse
import multiprocessing
import tqdm
import matplotlib.pyplot as plt
import matplotlib_venn

def get_max_min_mean_median(values):
    svals = sorted(values)
    if len(values) % 2 == 0:
        median = svals[len(svals)//2]
    else:
        mid = len(svals)//2
        median = (svals[mid] + svals[mid+1])//2

    return round(max(svals), 1), round(min(svals), 1), round(sum(svals)/len(svals), 1), round(median, 1)

def get_max_min_mean_median_total(values):
    svals = sorted(values)
    if len(values) % 2 == 0:
        median = svals[len(svals)//2]
    else:
        mid = len(svals)//2
        median = (svals[mid] + svals[mid+1])//2

    return round(max(svals), 1), round(min(svals), 1), round(sum(svals)/len(svals), 1), round(median, 1), sum(svals)

def get_files_with_timeouts(fnames, tool, timeout):
    print("Applying time-limit of {} ms for {}".format(timeout, tool))
    c = 0
    fnames_new = []
    fname_map = {fname : 1 for fname in fnames}
    with open('accuracy_timing.{}.csv'.format(tool), 'r') as f:
        for line in f:
            if line.startswith("loc"):
                continue

            line = line.lstrip().rstrip()
            time = float(line.split(',')[12])
            fname = ",".join(line.split(',')[14:])[1:-1]

            if (fname in fname_map) and time < args.tlimit:
                fnames_new.append(fname)
            elif (fname in fname_map) and time > args.tlimit:
                c += 1

    print("Timed out on {} files".format(c))

    return fnames_new

def venn_process_line(line):
    if line.startswith("var_id"):
        return None

    line = line.lstrip().rstrip()
    if line == '': return None

    splits = line.split(',')
    var_id, var_name, b1, b2, b3 = splits[:5]
    fname = ",".join(splits[5:])

    fname = fname[1:-1]
    if fname in venn_process_line.fname_map:
        b1, b2, b3 = list(map(int, (b1,b2,b3)))
        if fname not in venn_process_line.f_jsnaughty_map:
            b3 = 0
        if fname not in venn_process_line.f_c2n_map:
            b1 = 0
        if fname not in venn_process_line.f_jsnice_map:
            b2 = 0
    else:
        return None

    return (b1, b2, b3)

def venn_stats(fnames, f_c2n, f_jsnice, f_jsnaughty):
    only_c2n = 0
    only_jsnice = 0
    only_jsnaughty = 0

    c2n_jsnice = 0
    c2n_jsnaughty = 0
    jsnice_jsnaughty = 0

    all_tools = 0
    total = 0

    def update_cnts(corr_map):
        nonlocal only_c2n, only_jsnice, only_jsnaughty, c2n_jsnice, c2n_jsnaughty, jsnice_jsnaughty, all_tools
        if corr_map == (0,0,0): return
        elif corr_map == (1,0,0): only_c2n += 1
        elif corr_map == (0,1,0): only_jsnice += 1
        elif corr_map == (0,0,1): only_jsnaughty += 1
        elif corr_map == (1,1,0): c2n_jsnice += 1
        elif corr_map == (1,0,1): c2n_jsnaughty += 1
        elif corr_map == (0,1,1): jsnice_jsnaughty += 1
        elif corr_map == (1,1,1): all_tools += 1

    venn_process_line.fname_map = {fname : 1 for fname in fnames}
    venn_process_line.f_c2n_map = {fname : 1 for fname in f_c2n}
    venn_process_line.f_jsnice_map = {fname : 1 for fname in f_jsnice}
    venn_process_line.f_jsnaughty_map = {fname : 1 for fname in f_jsnaughty}

    with open('name_stats.csv', 'r') as f, multiprocessing.Pool() as p:
        for res in tqdm.tqdm(p.imap_unordered(venn_process_line, f)):
            if res:
                total += 1
                b1, b2, b3 = res
                update_cnts((b1,b2,b3))

    nums = [
            round(only_c2n * 100/total, 2),
            round(only_jsnice * 100/total, 2),
            round(only_jsnaughty * 100/total, 2),
            round(c2n_jsnice * 100/total, 2),
            round(c2n_jsnaughty * 100/total, 2),
            round(jsnice_jsnaughty * 100/total, 2),
            round(all_tools * 100/total, 2)
            ]

    print()
    print("============")
    print("Venn Diagram Stats")
    print("==================")
    print()
    print("Only Context2Name : ", nums[0], '%')
    print("Only JSNice       : ", nums[1], '%')
    print("Only JSNaughty    : ", nums[2], '%')
    print()
    print("Only Context2Name & JSNice    : ", nums[3], '%')
    print("Only Context2Name & JSNaughty : ", nums[4], '%')
    print("Only JSNice & JSNaughty       : ", nums[5], '%')
    print()
    print("All three : ", nums[6], '%')
    print()
    print("============")
    print()

    if args.save_venn is not None:
        nums[2], nums[3] = nums[3], nums[2]
        fig = plt.figure()
        if args.venn_weighted:
            matplotlib_venn.venn3(subsets=nums, set_labels=('Context2Name', 'JSNice', 'JSNaughty'))
            matplotlib_venn.venn3_circles(subsets=nums, linestyle='solid', linewidth=0.3)
        else:
            matplotlib_venn.venn3_unweighted(subsets=nums, set_labels=('Context2Name', 'JSNice', 'JSNaughty'))
            matplotlib_venn.venn3_circles(subsets=nums, linestyle='solid', linewidth=0.3)

        fig.savefig(args.save_venn, bbox_inches='tight', dpi=1000)


def get_times(tool):
    times = []
    with open('accuracy_timing.{}.csv'.format(tool), 'r') as f:
        for line in f:
            if line.startswith("loc"):
                continue

            line = line.lstrip().rstrip()
            time = float(line.split(',')[12])
            times.append(time)

    return times

def timing_stats(fnames):
    c2n_times = get_times('c2n')
    jsnice_times = get_times('jsnice')
    jsnaughty_times = get_times('jsnaughty')

    # Get total number of unique local names
    t_l_s = 0
    with open('accuracy_timing.{}.csv'.format('c2n'), 'r') as f:
        for line in f:
            if line.startswith("loc"):
                continue

            line = line.lstrip().rstrip()
            splits = line.split(',')
            fname = ",".join(line.split(',')[14:])[1:-1]

            t_l_s += int(splits[1])

    print()
    print("============")
    print("Timing Stats (Per-File)")
    print("============")
    print()
    print("Context2Name (Max,Min,Mean,Median) : " + str(get_max_min_mean_median(c2n_times)))
    print("JSNice       (Max,Min,Mean,Median) : " + str(get_max_min_mean_median(jsnice_times)))
    print("JSNaughty    (Max,Min,Mean,Median) : " + str(get_max_min_mean_median(jsnaughty_times)))
    print()
    print("============")
    print()

    print()
    print("============")
    print("Timing Stats (Per-Name)")
    print("============")
    print()
    print("Context2Name : " + str(get_max_min_mean_median_total(c2n_times)[-1]/t_l_s))
    print("JSNice       : " + str(get_max_min_mean_median_total(jsnice_times)[-1]/t_l_s))
    print("JSNaughty    : " + str(get_max_min_mean_median_total(jsnaughty_times)[-1]/t_l_s))
    print()
    print("============")
    print()

def accuracy_stats(fnames, tools):
    fname_map = {fname : 1 for fname in fnames}
    for tool in tools:
        l_s = t_l_s = l_g_s = t_l_g_s = l_a = t_l_a = l_g_a = t_l_g_a = 0
        with open('accuracy_timing.{}.csv'.format(tool), 'r') as f:
            for line in f:
                if line.startswith("loc"):
                    continue

                line = line.lstrip().rstrip()
                splits = line.split(',')
                fname = ",".join(line.split(',')[14:])[1:-1]
                counted = (fname in fname_map)

                l_s += int(splits[0]) if counted else 0
                t_l_s += int(splits[1])

                l_g_s += int(splits[3]) if counted else 0
                t_l_g_s += int(splits[4])

                l_a += int(splits[6]) if counted else 0
                t_l_a += int(splits[7])

                l_g_a += int(splits[9]) if counted else 0
                t_l_g_a += int(splits[10])


            print()
            print("============")
            print("Accuracy Stats for {}".format(tool))
            print("============")
            print()
            print("Local, Single Occurrence : {} : Baseline : {}".format(round(l_s * 100/t_l_s, 1), 0.0))
            print("Local + Global, Single Occurrence : {} : Baseline : {}".format(round(l_g_s * 100/t_l_g_s, 1), round((l_g_s - l_s) * 100/t_l_g_s, 1)))
            print("Local, All Occurrences : {} : Baseline : {}".format(round(l_a * 100/t_l_a, 1), 0.0))
            print("Local + Global, All Occurrences : {} : Baseline : {}".format(round(l_g_a * 100/t_l_g_a, 1), round((l_g_a - l_a) * 100/t_l_g_a, 1)))
            print()
            print("============")

def file_stats(fnames):
    t_l_s = []
    t_l_g_s = []
    t_l_a = []
    t_l_g_a = []
    num_lines = []
    with open('accuracy_timing.c2n.csv', 'r') as f:
        for line in f:
            if line.startswith("loc"):
                continue

            line = line.lstrip().rstrip()
            splits = line.split(',')
            fname = ",".join(line.split(',')[14:])[1:-1]
            num_lines.append(int(splits[13]))
            t_l_s.append(int(splits[1]))
            t_l_g_s.append(int(splits[4]))
            t_l_a.append(int(splits[7]))
            t_l_g_a.append(int(splits[10]))

    print()
    print("============")
    print("File Stats")
    print("============")
    print()
    print("Number of Lines (excluding whitespace/comments) (Max,Min,Mean,Median) : " + str(get_max_min_mean_median(num_lines)))
    print("Local, Single Occurrence                        (Max,Min,Mean,Median,Total) : " + str(get_max_min_mean_median_total(t_l_s)))
    print("Local + Global, Single Occurrence               (Max,Min,Mean,Median,Total) : " + str(get_max_min_mean_median_total(t_l_g_s)))
    print("Local, All Occurrences                          (Max,Min,Mean,Median,Total) : " + str(get_max_min_mean_median_total(t_l_a)))
    print("Local + Global, All Occurrences                 (Max,Min,Mean,Median,Total) : " + str(get_max_min_mean_median_total(t_l_g_a)))
    print()
    print("============")
    print()





if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--venn", action="store_true", default=False, help="Compute Venn Diagram Stats")
    parser.add_argument("--venn_weighted", action="store_true", default=False, help="Compute Venn Diagram Stats")
    parser.add_argument("--save_venn", action="store", default=None, type=str, help="Save Venn Diagrams")
    parser.add_argument("--accuracies", action="store_true", default=False, help="Compute accuracies")
    parser.add_argument("--tlimit", action="store", type=float, default=None, help="Set time-limit for files (as a filter) (in ms) (Relevant only for accuracies)")
    parser.add_argument("--timing", action="store_true", default=False, help="Compute timing statistics")
    parser.add_argument("--filestats", action="store_true", default=False, help="Compute timing statistics")
    parser.add_argument("--tool", choices=['c2n', 'jsnice', 'jsnaughty', 'all'], default="all", help="Tool for which to compute the metrics (relevant only for accuracies)")
    parser.add_argument("inp", help="Input filelist")
    args = parser.parse_args()

    with open(args.inp, 'r') as f:
        fnames = [line.lstrip().rstrip() for line in f]

    if args.venn:
        if args.tlimit is not None:
            f_c2n = get_files_with_timeouts(fnames, 'c2n', args.tlimit)
            f_jsnice = get_files_with_timeouts(fnames, 'jsnice', args.tlimit)
            f_jsnaughty = get_files_with_timeouts(fnames, 'jsnaughty', args.tlimit)
            venn_stats(fnames, f_c2n, f_jsnice, f_jsnaughty)
        else:
            venn_stats(fnames, fnames, fnames, fnames)

    if args.timing:
        timing_stats(fnames)

    if args.tool == 'all':
        args.tool = ['c2n', 'jsnice', 'jsnaughty']

    if args.filestats:
        file_stats(fnames)

    for tool in args.tool:

        fnames_t = fnames[:]
        if args.tlimit is not None:
            fnames_t = get_files_with_timeouts(fnames, tool, args.tlimit)

        if args.accuracies:
            accuracy_stats(fnames_t, [tool])



