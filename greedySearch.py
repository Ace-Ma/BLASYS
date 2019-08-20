import regex as re
import sys
import random
import os
import numpy as np
import subprocess
import multiprocessing as mp
import shutil
import argparse
import time
from utils import assess_HD, gen_truth, create_wh, synth_design, approximate


def evaluate_design(k_stream, list_num_input, list_num_output, toplevel, args, approx_created, app_path, num_iter, num_design):

    print('Evaluating Design ', k_stream)

    num_part = len(k_stream)
    # area = 0

    tmp_verilog = os.path.join(args.output, 'approx_design', 'iter'+str(num_iter)+'design'+str(num_design)+'.v')
    toplevel_file = os.path.join(args.output, 'partition', toplevel + '.v')
    os.system('cat ' + toplevel_file + ' > ' + tmp_verilog)

    for i in range(num_part):

        approx_degree = k_stream[i]

        if approx_degree == -1:
            continue

        if approx_degree == list_num_output[i]:
            part_verilog = os.path.join(args.output, 'partition', toplevel + '_' + str(i) + '.v')
            os.system('cat ' + part_verilog + ' >> ' + tmp_verilog)
            # area += approx_area[i][approx_degree]
            continue
        
        part_verilog = os.path.join(args.output, toplevel + '_' + str(i), toplevel + '_' + str(i) + '_approx_k=' + str(approx_degree) + '.v')
        if approx_created[i][approx_degree] == 1:
            os.system('cat ' + part_verilog + ' >> ' + tmp_verilog)
            # area += approx_area[i][approx_degree]
        else:
            print('----- Approximating part ' + str(i) + ' to degree ' + str(approx_degree))

            directory = os.path.join(args.output, toplevel + '_' + str(i), toplevel + '_' + str(i))
            approximate(directory, approx_degree, list_num_input[i], list_num_output[i], args.liberty, toplevel + '_' + str(i), app_path, args.output)
            os.system('cat ' + part_verilog + ' >> ' + tmp_verilog)
            # part_area = synth_design(part_verilog, part_verilog[:-2]+'_syn', config['liberty_file'], True)
            approx_created[i][approx_degree] = 1
            # area += part_area

    truth_dir = os.path.join(args.output, 'truthtable', 'iter'+str(num_iter)+'design'+str(num_design)+'.truth')
    os.system('iverilog -o ' + truth_dir[:-5] + 'iv ' + tmp_verilog + ' ' + args.testbench)
    os.system('vvp ' + truth_dir[:-5] + 'iv > ' + truth_dir)
    os.system('rm ' + truth_dir[:-5] + 'iv')

    ground_truth = os.path.join(args.output, toplevel + '.truth')
    
    area  = synth_design(tmp_verilog, tmp_verilog[:-2] + '_syn', library, args.output)

    t, h, f = assess_HD(ground_truth, truth_dir)
    print('Simulation error: ' + str(f) + '\tCircuit area: ' + str(area))
    return f, area



def evaluate_iter(curr_k_stream, list_num_input, list_num_output, toplevel, args, approx_created, app_path, num_iter):
    
    k_lists = []

    for i in range(len(curr_k_stream)):
        new_k_stream = list(curr_k_stream)
        new_k_stream[i] = new_k_stream[i] - 1
        if new_k_stream[i] > 1:
            k_lists.append(new_k_stream)
    
    if len(k_lists) == 0:
        return False, 0, 0

    num_list = len(k_lists)
    err_list = []
    area_list = []

    for i in range(num_list):
        # Evaluate each list
        print('======== Design number ' + str(i))
        k_stream = k_lists[i]
        err, area = evaluate_design(k_stream, list_num_input, list_num_output, toplevel, args, approx_created, app_path, num_iter, i)
        err_list.append(err)
        area_list.append(area)

    if np.min(err_list) > args.threshold:
        return False, 0, 0


    idx = optimization(err_list, area_list, args.threshold)
    return k_lists[idx], err_list[idx], area_list[idx]


def optimization(err_list, area_list, threshold):
    np_area = np.array(area_list)
    order = np.argsort(np_area)

    for i in order:
        if err_list[i] > threshold:
            continue
        return i


def print_banner():
    print('/----------------------------------------------------------------------------\\')
    print('|                                                                            |')
    print('|  BLASYS -- Approximate Logic Synthesis Using Boolean Matrix Factorization  |')
    print('|  Version: 0.2.0                                                            |')
    print('|                                                                            |')
    print('|  Copyright (C) 2019  SCALE Lab, Brown University                           |')
    print('|                                                                            |')
    print('|  Permission to use, copy, modify, and/or distribute this software for any  |')
    print('|  purpose with or without fee is hereby granted, provided that the above    |')
    print('|  copyright notice and this permission notice appear in all copies.         |')
    print('|                                                                            |')
    print('|  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES  |')
    print('|  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF          |')
    print('|  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR   |')
    print('|  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES    |')
    print('|  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN     |')
    print('|  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF   |')
    print('|  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.            |')
    print('|                                                                            |')
    print('\\----------------------------------------------------------------------------/')



######################
#        MAIN        #
######################

app_path = os.path.dirname(sys.argv[0])

parser = argparse.ArgumentParser(description='BLASYS -- Approximate Logic Synthesis Using Boolean Matrix Factorization')
parser.add_argument('-i', help='Input verilog file', required=True, dest='input')
parser.add_argument('-tb', help='Testbench verilog file', required=True, dest='testbench')
parser.add_argument('-n', help='Number of partitions', required=True, type=int, dest='npart')
parser.add_argument('-o', help='Output directory', default='output', dest='output')
parser.add_argument('-ts', help='Threshold on error', default=0.5, type=int, dest='threshold')
parser.add_argument('-lib', help='Liberty file name', default=os.path.join(app_path, 'asap7.lib'), dest='liberty')
parser.add_argument('--lsoracle', help='Path to LSOracle tool', default='lstools', dest='lsoracle')
parser.add_argument('--yosys', help='Path to YOSYS', default='yosys', dest='yosys')
parser.add_argument('--vvp', help='Path to vvp', default='vvp', dest='vvp')
parser.add_argument('--iverilog', help='Path to iVerilog', default='iverilog', dest='iverilog')

args = parser.parse_args()

print_banner()


# Create temporary output directory
output_dir_path = args.output
if os.path.isdir(output_dir_path):
    shutil.rmtree(output_dir_path)
os.mkdir(output_dir_path)

os.mkdir(os.path.join(output_dir_path, 'approx_design'))
os.mkdir(os.path.join(output_dir_path, 'truthtable'))

# Parse information from yaml file
input_file = args.input
testbench = args.testbench
lsoracle = args.lsoracle
yosys = args.yosys
iverilog = args.iverilog
vvp = args.vvp
library = args.liberty
num_parts = args.npart
toplevel = ''
with open(input_file) as file:
    line = file.readline()
    while line:
        tokens = re.split('[ (]', line)
        for i in range(len(tokens)):
            if tokens[i] == 'module':
                toplevel = tokens[i+1]
                break
        if toplevel != '':
            break
        line = file.readline()

# Evaluate input circuit
print('Simulating truth table on input design...')
os.system(iverilog + ' -o '+ toplevel + '.iv ' + input_file + ' ' + testbench )
output_truth = os.path.join(output_dir_path, toplevel+'.truth')
os.system(vvp + ' ' + toplevel + '.iv > ' + output_truth)
os.system('rm ' + toplevel + '.iv')

# Write abc script
with open(os.path.join(output_dir_path, 'abc.script'), 'w') as file:
    file.write('strash;fraig;refactor;rewrite -z;scorr;map')

# Partitioning circuit
print('Partitioning input circuit...')
part_dir = os.path.join(output_dir_path, 'partition')
lsoracle_command = 'read_verilog ' + input_file + '; ' \
        'partitioning ' + str(num_parts) + '; ' \
        'get_all_partitions ' + part_dir
log_partition = os.path.join(output_dir_path, 'lsoracle.log')
with open(log_partition, 'w') as file_handler:
    file_handler.write(lsoracle_command)
    subprocess.call([lsoracle, '-c', lsoracle_command], stderr=file_handler, stdout=file_handler)

print('Synthesizing input design with original partitions...')
input_synth = os.path.join(output_dir_path, toplevel + '_parts.v')
parts = os.path.join(part_dir, '*.v')
os.system('cat ' + parts + ' >> ' + input_synth)
output_synth = os.path.join(output_dir_path, toplevel+'_syn')
input_area = synth_design(input_synth, output_synth, library, args.output)
print('Original design area ', str(input_area))


# Generate truth table for each partitions
approx_created = []
list_num_input = []
list_num_output = []
for i in range(num_parts):
    modulename = toplevel + '_' + str(i)
    file_path = os.path.join(part_dir, modulename)
    if not os.path.exists(file_path + '.v'):
        print('Submodule ' + str(i) + ' is empty')
        approx_created.append(-1)
        list_num_input.append(-1)
        list_num_output.append(-1)
        continue

    # Create testbench for partition
    print('Create testbench for partition '+str(i))
    n, m = gen_truth(file_path, modulename)
    list_num_input.append( n )
    list_num_output.append( m )

    # Generate truthtable
    print('Generate truth table for partition '+str(i))
    part_output_dir = os.path.join(output_dir_path, modulename)
    os.mkdir(part_output_dir)
    os.system(iverilog + ' -o ' + file_path + '.iv ' + file_path + '.v ' + file_path + '_tb.v')
    truth_dir = os.path.join(part_output_dir, modulename + '.truth')
    os.system(vvp + ' ' + file_path + '.iv > ' + truth_dir)

    # Evaluate partition area
    #print('Evaluate partition area ' + str(i))
    #part_synth = os.path.join(part_output_dir, modulename + '_syn')
    #part_area = synth_design(file_path + '.v', part_synth, library, True)
    #print('Partition area ' + str(part_area))
    approx_created.append([0] * m + [1])

print('==================== Starting Approximation by Greedy Search  ====================')

count_iter = 1
curr_stream = []

while True:
    if count_iter == 1:
        curr_stream = list_num_output

    print('--------------- Iteration ' + str(count_iter) + ' ---------------')
    before = time.time()
    tmp, err, area = evaluate_iter(curr_stream, list_num_input, list_num_output, toplevel, args, approx_created, app_path, count_iter )
    after = time.time()

    time_used = after - before

    print('--------------- Finishing Iteration' + str(count_iter) + '---------------')
    print('Previous k_stream: ' + str(curr_stream))
    print('Chosen k_stream:   ' + str(tmp))
    for i in range(len(curr_stream)):
        pre = curr_stream[i]
        aft = tmp[i]
        if pre != aft:
            print('Design number ' + str(i) + ' is chosen.')
            print('Approximated partition ' + str(i) + ' from ' + str(pre) + ' to ' + str(aft))
            break
    print('Approximated HD error:  ' + str(100*err) + '%')
    print('Area percentage:        ' + str(100 * (area / input_area)) + '%')
    print('Time used:              ' + str(time_used))

    msg = 'Approximated HD error: {:.6f}%\tArea percentage: {:.6f}%\tTime used: {:.6f} sec\n'.format(100*err, 100*(area/input_area), time_used)
    print(msg)
    with open(os.path.join(output_dir_path, 'log'), 'a') as log_file:
        log_file.write(str(tmp))
        log_file.write('\n')
        log_file.write(msg)

    curr_stream = tmp

    if tmp == False:
        break

    count_iter += 1

