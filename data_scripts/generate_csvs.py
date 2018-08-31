#!/usr/bin/env python3
import os, sys, tqdm
import multiprocessing
import re

# Timing etc.
C2N_STATS = ".c2n.timing.stats"
JSNICE_STATS = ".jsnice.timing.stats"
JSNAUGHTY_STATS = ".jsnaughty.timing.stats"

# Name stats
NAME_C2N = ".c2n.naming.stats"
NAME_JSNICE = ".jsnice.naming.stats"
NAME_JSNAUGHTY = ".jsnaughty.naming.stats"

def extract_time(fname, mode='ms'):
    with open(fname, 'r') as f:
        line = f.readline().lstrip().rstrip()
        time = float(line.split(' : ')[1])

    if mode == 's':
        time = time * 1000

    return time # in milliseconds

def get_time_stats_for_file(fname):
    # C2N
    t_c2n = extract_time(fname[:-3] + C2N_STATS)
    # JSNice
    t_jsnice = extract_time(fname[:-3] + JSNICE_STATS)
    # JSNaughty
    t_jsnaughty = extract_time(fname[:-3] + JSNAUGHTY_STATS, mode='s') 
    
    return [fname, t_c2n, t_jsnice, t_jsnaughty]

def extract_correct_name_sets(fname):
    res = set([])
    fail = set([])
    try:
        with open(fname, 'r') as f:
            lines = [line.lstrip().rstrip() for line in f]
    except:
        return res, 0

    n2id = {}
    for line in lines:
        num, name, result = line.split(' : ')[-3:]

        if not name in n2id: n2id[name] = 0
        curid = n2id[name] + 1
        n2id[name] = curid

        filename = '.'.join(fname.split('.')[:-3]) + '.js'
        if result == "true":
            res.add((filename, curid, name))
        else:
            fail.add((filename, curid, name))

    return res, fail, len(lines)

def get_venn_stats_for_file(fname, generate_csv=True):
    # C2N
    s_c2n, f_c2n, l1 = extract_correct_name_sets(fname[:-3] + NAME_C2N)
    # JSNice
    s_jsnice, f_jsnice, l2 = extract_correct_name_sets(fname[:-3] + NAME_JSNICE)
    # JSNaughty
    s_jsnaughty, f_jsnaughty, l3 = extract_correct_name_sets(fname[:-3] + NAME_JSNAUGHTY)

    csv_str = ""
    if generate_csv:
        for i in (s_c2n - s_jsnice - s_jsnaughty):
            csv_str += "{},{},1,0,0,{}\n".format(i[1], i[2], '"' + i[0] + '"')
        for i in (s_jsnice - s_c2n - s_jsnaughty):
            csv_str += "{},{},0,1,0,{}\n".format(i[1], i[2], '"' + i[0] + '"')
        for i in (s_jsnaughty - s_c2n - s_jsnice):
            csv_str += "{},{},0,0,1,{}\n".format(i[1], i[2], '"' + i[0] + '"')
        for i in ((s_c2n & s_jsnice) - s_jsnaughty):
            csv_str += "{},{},1,1,0,{}\n".format(i[1], i[2], '"' + i[0] + '"')
        for i in ((s_c2n & s_jsnaughty) - s_jsnice):
            csv_str += "{},{},1,0,1,{}\n".format(i[1], i[2], '"' + i[0] + '"')
        for i in ((s_jsnaughty & s_jsnice) - s_c2n):
            csv_str += "{},{},0,1,1,{}\n".format(i[1], i[2], '"' + i[0] + '"')
        for i in (s_c2n & s_jsnaughty & s_jsnice):
            csv_str += "{},{},1,1,1,{}\n".format(i[1], i[2], '"' + i[0] + '"')
        for i in (f_c2n & f_jsnaughty & f_jsnice):
            csv_str += "{},{},0,0,0,{}\n".format(i[1], i[2], '"' + i[0] + '"')


    return [len(s_c2n - s_jsnice - s_jsnaughty), 
            len(s_jsnice - s_c2n - s_jsnaughty),
            len(s_jsnaughty - s_c2n - s_jsnice),
            len((s_c2n & s_jsnice) - s_jsnaughty),
            len((s_c2n & s_jsnaughty) - s_jsnice),
            len((s_jsnaughty & s_jsnice) - s_c2n),
            len((s_c2n & s_jsnaughty & s_jsnice))], max(l1, l2, l3), csv_str

def get_venn_stats(fnames):
    result = [0] * 7
    l = len(result)
    total = 0

    with multiprocessing.Pool(4) as p, open('name_stats.csv', 'w') as f:
        f.write("var_id,var_name,c2n,jsnice,jsnaughty,filename\n")
        for res in tqdm.tqdm(p.imap_unordered(get_venn_stats_for_file, fnames), total=len(fnames)):
            result = [result[i] + res[0][i] for i in range(l)]
            total += res[1]
            f.write(res[2])

def convert_logs2csv(fnames):
    with open('accuracy_timing.c2n.csv', 'w') as w:
        w.write("local_single_correct,local_single_total,local_single_acc,local_global_single_correct,local_global_single_total,local_global_acc,local_all_correct,local_all_total,local_all_acc,local_global_all_correct,local_global_all_total,local_global_all_acc,time_ms,num_lines,filename\n")
        with open('log_analysis.c2n', 'r') as f:
            for line in f:
                line = line.lstrip().rstrip()
                if line.startswith(">>>> Errors:") and line.endswith(".js"):
                    fname = line.split('-- ')[-1]
                    with open(fname[:-3] + '.c2n.js', 'r') as z:
                        num_lines = sum(1 for line in z if line.lstrip().rstrip())
                    ok = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'OK=\s*[0-9]*', line)))[:4]
                    diff = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'DIFF=\s*[0-9]*', line)))[:4]
                    total = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'TOTAL=\s*[0-9]*', line)))
                    d += total[3]

                    loc_glob_all = "{},{},{}".format(ok[0], total[0], round(ok[0]/total[0], 2) if total[0] > 0 else 0.00)
                    loc_all = "{},{},{}".format(ok[1], total[1], round(ok[1]/total[1], 2) if total[1] > 0 else 0.00)
                    loc_glob_sing = "{},{},{}".format(ok[2], total[2], round(ok[2]/total[2], 2) if total[2] > 0 else 0.00)
                    loc_sing = "{},{},{}".format(ok[3], total[3], round(ok[3]/total[3], 2) if total[3] > 0 else 0.00)
                    time = round(get_time_stats_for_file(fname)[1], 2)
                    fname = os.path.relpath(line.split('-- ')[-1].replace('.normalized.js', '.js'), os.getcwd())
                    w.write("{},{},{},{},{},{},\"{}\"\n".format(loc_sing, loc_glob_sing, loc_all, loc_glob_all, time, num_lines, fname))

    print("Finished accuracy_timing csv for Context2Name")

    with open('accuracy_timing.jsnice.csv', 'w') as w:
        w.write("local_single_correct,local_single_total,local_single_acc,local_global_single_correct,local_global_single_total,local_global_acc,local_all_correct,local_all_total,local_all_acc,local_global_all_correct,local_global_all_total,local_global_all_acc,time_ms,num_lines,filename\n")
        with open('log_analysis.jsnice', 'r') as f:
            for line in f:
                line = line.lstrip().rstrip()
                if line.startswith(">>>> Errors:") and line.endswith(".js"):
                    fname = line.split('-- ')[-1]
                    with open(fname[:-3] + '.c2n.js', 'r') as z:
                        num_lines = sum(1 for line in z if line.lstrip().rstrip())
                    ok = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'OK=\s*[0-9]*', line)))[:4]
                    diff = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'DIFF=\s*[0-9]*', line)))[:4]
                    total = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'TOTAL=\s*[0-9]*', line)))
                    d += total[3]

                    loc_glob_all = "{},{},{}".format(ok[0], total[0], round(ok[0]/total[0], 2) if total[0] > 0 else 0.00)
                    loc_all = "{},{},{}".format(ok[1], total[1], round(ok[1]/total[1], 2) if total[1] > 0 else 0.00)
                    loc_glob_sing = "{},{},{}".format(ok[2], total[2], round(ok[2]/total[2], 2) if total[2] > 0 else 0.00)
                    loc_sing = "{},{},{}".format(ok[3], total[3], round(ok[3]/total[3], 2) if total[3] > 0 else 0.00)
                    time = round(get_time_stats_for_file(fname)[2], 2)
                    fname = os.path.relpath(line.split('-- ')[-1].replace('.normalized.js', '.js'), os.getcwd())
                    w.write("{},{},{},{},{},{},\"{}\"\n".format(loc_sing, loc_glob_sing, loc_all, loc_glob_all, time, num_lines, fname))

    print("Finished accuracy_timing csv for JSNice")

    with open('accuracy_timing.jsnaughty.csv', 'w') as w:
        w.write("local_single_correct,local_single_total,local_single_acc,local_global_single_correct,local_global_single_total,local_global_acc,local_all_correct,local_all_total,local_all_acc,local_global_all_correct,local_global_all_total,local_global_all_acc,time_ms,num_lines,filename\n")
        with open('log_analysis.jsnaughty', 'r') as f:
            for line in f:
                line = line.lstrip().rstrip()
                if line.startswith(">>>> Errors:") and line.endswith(".js"):
                    fname = line.split('-- ')[-1]
                    with open(fname[:-3] + '.c2n.js', 'r') as z:
                        num_lines = sum(1 for line in z if line.lstrip().rstrip())
                    ok = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'OK=\s*[0-9]*', line)))[:4]
                    diff = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'DIFF=\s*[0-9]*', line)))[:4]
                    total = list(map(lambda x : int(x.split('=')[-1]), re.findall(r'TOTAL=\s*[0-9]*', line)))
                    d += total[3]

                    loc_glob_all = "{},{},{}".format(ok[0], total[0], round(ok[0]/total[0], 2) if total[0] > 0 else 0.00)
                    loc_all = "{},{},{}".format(ok[1], total[1], round(ok[1]/total[1], 2) if total[1] > 0 else 0.00)
                    loc_glob_sing = "{},{},{}".format(ok[2], total[2], round(ok[2]/total[2], 2) if total[2] > 0 else 0.00)
                    loc_sing = "{},{},{}".format(ok[3], total[3], round(ok[3]/total[3], 2) if total[3] > 0 else 0.00)
                    time = round(get_time_stats_for_file(fname)[3], 2)
                    fname = os.path.relpath(line.split('-- ')[-1].replace('.normalized.js', '.js'), os.getcwd())
                    w.write("{},{},{},{},{},{},\"{}\"\n".format(loc_sing, loc_glob_sing, loc_all, loc_glob_all, time, num_lines, fname))

    print("Finished accuracy_timing csv for JSNaughty")

if __name__ == "__main__":

    filelist = sys.argv[1]
    with open(filelist, 'r') as f:
        fnames = [line.lstrip().rstrip() for line in f]

    get_venn_stats(fnames)
    convert_logs2csv(fnames)

    
