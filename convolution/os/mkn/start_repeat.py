# encoding: utf-8
from __future__ import division
from __future__ import print_function
import transform_unit_repeat as t
import transform_unit_repeat_last as tlast
import img2col_coordinate as ic
import functions as f
import csv
import numpy as np
import sys


# 超参数
architecture_parameters = open('data/architecture_parameters.csv', 'r')
dataflow_parameters = open('data/dataflow_parameters.csv', 'r')
workload_parameters = open('data/workload_parameters.csv', 'r')
freader_architecture_parameters = csv.reader(architecture_parameters, delimiter=',')
freader_dataflow_parameters = csv.reader(dataflow_parameters, delimiter=',')
freader_workload_parameters = csv.reader(workload_parameters, delimiter=',')
variable_header_architecture_parameters = next(freader_architecture_parameters)
variable_header_dataflow_parameters = next(freader_dataflow_parameters)
variable_header_workload_parameters = next(freader_workload_parameters)
intermediate_variables = open('data/intermediate_variables.txt',mode='r')
level_num_tracking = intermediate_variables.readlines()
intermediate_variables.close()
level_num = int(level_num_tracking[0])
tracking = int(level_num_tracking[1])
for i in range(level_num):
    variable_architecture_parameters = next(freader_architecture_parameters)
    variable_dataflow_parameters = next(freader_dataflow_parameters)
    variable_workload_parameters = next(freader_workload_parameters)
architecture_parameters.close()
dataflow_parameters.close()
workload_parameters.close()
if tracking == 1:
    output_file = open('./data/output/track_file_%d.csv'%(level_num), 'w')
    fieldnames = ['cycle','G_B0_ptw', 'G_B1_ptw','G_B0_ptr','G_B1_ptr','G_A0_ptw','G_A1_ptw','G_A0_ptr',\
    'G_A1_ptr','G_C0_ptr','G_C1_ptr','G_C0_ptw','G_C1_ptw']
    writer = csv.DictWriter(output_file, fieldnames=fieldnames)
    writer.writeheader()
IX, IY, FW, FH = int(variable_workload_parameters[1]), int(variable_workload_parameters[2]), int(variable_workload_parameters[3]), int(variable_workload_parameters[4])
C_channel, K_channel, Batchsize = int(variable_workload_parameters[5]), int(variable_workload_parameters[6]), int(variable_workload_parameters[7])
stride, padding = int(variable_workload_parameters[8]), str(variable_workload_parameters[9])
m, k, n = int(variable_dataflow_parameters[0]), int(variable_dataflow_parameters[1]), int(variable_dataflow_parameters[2])
dataflow, loops = str(variable_dataflow_parameters[3]), str(variable_dataflow_parameters[4])
dataflow_M, dataflow_K = str(variable_dataflow_parameters[5]), str(variable_dataflow_parameters[6])
bandwidth_B, data_precision, compute_pipeline = int(variable_architecture_parameters[0]), int(variable_architecture_parameters[1]), int(variable_architecture_parameters[2])
Array_i, Array_j = int(variable_architecture_parameters[3]), int(variable_architecture_parameters[4])
bandwidth = bandwidth_B * 8 / data_precision

if padding == 'valid':
    OX, OY = (IX - FW) // stride + 1, (IY - FH) // stride + 1
else: # padding == 'same'
    OX, OY = (IX - 1) // stride + 1, (IY - 1) // stride + 1
M, K, N = OX * OY * Batchsize, FH * FW * C_channel, K_channel
m, k, n = min(M, m), min(K, k), min(N, n)


# 参数初始化
cycle = 0
communication_cycle = 0
communication_A_cycle, communication_B_cycle = 0, 0
communication_C_cycle, communication_Y_cycle = 0, 0
communication = 0
on_chip_alter = 0
G_A_in_use, G_B_in_use = 0, 0
G_A0_ready, G_A1_ready = 0, 0
G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw = 0, 0, 0, 0
a_loops, b_loops, c_loops = 1, 1, 1
G_B0_ready, G_B1_ready = 0, 0
G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw = 0, 0, 0, 0
C_SA_load = 0
G_C0_ready, G_C1_ready = 0, 0
G_C0_ptw, G_C0_ptr, G_C1_ptw, G_C1_ptr = 0, 0, 0, 0
G_Cw_in_use, G_Cr_in_use = 0, 0
bw_in_use = 'C'
C_compute_in_SA = 0
A_interval_work, A_interval_spare = 0, 0
G_C_ptr_add, G_C_ptw_add = 0, -2 * Array_i
counter_A_read = 0
m_loop_times, n_loop_times, k_loop_times = f.roundup(M,m), f.roundup(N,n), f.roundup(K,k)
m_coordinate, k_coordinate, n_coordinate = 0, 0, 0
# (IY, IX, C_channel, Batchsize)
ifmap_img2col0_old = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
ifmap_img2col1_old = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
partial_sum = [[0 for i in range(n_loop_times)] for j in range(m_loop_times)]
ifmap_transmission_on_chip = 0
communication_off_chip = 0
communication_on_chip = 0
communication_interval = 0
communication_internal = 0
# 初始化，将A与B的数据从HBM读到GSM
B_buf_tile_trans = f.ceil(k * n, bandwidth)
while(G_B0_ptw!=B_buf_tile_trans):
    G_B0_ptw += bandwidth
    cycle += 1
    communication_B_cycle += 1
    if tracking == 1:
        writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
        'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
        'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
communication_off_chip += f.ceil(k * n, bandwidth)

# 记录A_buf0中的原始矩阵
ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, 0, 0, m, k, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, 1, Batchsize, dataflow_M, dataflow_K)
for ii in range(m):
    for jj in range(k):
        ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
ifmap_transmission_on_chip += transmission_on_chip
A_buf_tile_trans = f.ceil(m * k - transmission_zero - transmission_local, bandwidth)
while(G_A0_ptw!=A_buf_tile_trans):
    G_A0_ptw += bandwidth
    cycle += 1
    communication_A_cycle += 1
    if tracking == 1:
        writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
        'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
        'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
partial_sum[0][0] = 1
G_A0_ptw, G_B0_ptw, G_C0_ptw = 0, 0, 0
G_A0_ready, G_B0_ready, G_C0_ready = 1, 1, 1
# 一开始不需要将部分和读入，因为没有部分和
G_C_ptr_add += Array_i
G_C_ptw_add += Array_i
m_loops = f.roundup(m, Array_i)
n_loops = f.roundup(n, Array_j)
while(G_C_ptr_add != 0):
    G_C0_ptr += Array_j
    # c在读最后一列
    if c_loops % n_loops == 0 and c_loops != n_loops * m_loops:
        # Array_j个数据从C_buf读出与写回C_buf
        communication_on_chip += 2 * (n + Array_j - f.expansion(n, Array_j))
        # Array_j个数在PE间传递的次数不同，从1到Array_i-1，为了简化计算同时不失正确性，这里用平均数
        communication_interval += (Array_i - 1) * (n + Array_j - f.expansion(n, Array_j))
    # c在读最后一行
    elif c_loops - (m_loops - 1) * n_loops > 0 and c_loops != n_loops * m_loops:
        # Array_j个数据从c_buf读出
        communication_on_chip += 2 * (Array_j * (m + Array_i - f.expansion(m, Array_i)) / Array_i)
        # Array_j个数在PE间传递的次数不同，从1到Array_i-1，为了简化计算同时不失正确性，这里用平均数
        communication_interval += (Array_i - 1) * (Array_j * (m + Array_i - f.expansion(m, Array_i)) / Array_i)
    # c在读最后一块
    elif c_loops == n_loops * m_loops:
        # Array_j个数据从C_buf读出与写回C_buf
        communication_on_chip += 2 * ((n + Array_j - f.expansion(n, Array_j)) * (m + Array_i - f.expansion(m, Array_i)) / Array_i)
        # Array_j个数在PE间传递的次数不同，从1到Array_i-1，为了简化计算同时不失正确性，这里用平均数
        communication_interval += (Array_i - 1) * ((n + Array_j - f.expansion(n, Array_j)) * (m + Array_i - f.expansion(m, Array_i)) / Array_i)
    else:
        # Array_j个数据从C_buf读出与写回C_buf
        communication_on_chip += 2 * Array_j
        # Array_j个数在PE间传递的次数不同，从1到Array_i-1，为了简化计算同时不失正确性，这里用平均数
        communication_interval += (Array_i - 1) * Array_j
    G_C_ptr_add -= 1
    cycle += 1
    if tracking == 1:
        writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
        'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
        'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
C_SA_load += 1
C_compute_in_SA += 1
c_loops += 1
G_C_ptr_add += Array_i
G_C_ptw_add += Array_i
A_interval_work, A_interval_spare = Array_i + Array_i + Array_j + k * compute_pipeline + 1, (Array_i + Array_i + Array_j + k * compute_pipeline + 1)*10
counter, counter_total = 0, m_loop_times * k_loop_times * n_loop_times
#################################################################计算部分开始#################################################
#############################################################################################################################
#############################################################################################################################
if m_loop_times == 1 and k_loop_times == 1 and n_loop_times >= 2:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times == 1 and k_loop_times >= 2 and n_loop_times == 1:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 最后一个
                if m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times == 1 and k_loop_times == 2 and n_loop_times >= 2:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial==0 and k_serial==0 and n_serial!=0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial==0 and k_serial==k_loop_times-1 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times == 1 and k_loop_times >= 3 and n_loop_times == 2:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial==0 and k_serial!=0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times == 1 and k_loop_times >= 3 and n_loop_times >= 3:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial==0 and k_serial!=k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times == 1 and n_loop_times == 1:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 1, 0, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 0, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 1, 0, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 0, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times == 1 and n_loop_times == 2:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial!=m_loop_times-1 and k_serial==0 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 0, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 0, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times == 1 and n_loop_times >= 3:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial!=m_loop_times-1 and k_serial==0 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times == 2 and n_loop_times == 1:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial==0 and k_serial==k_loop_times-1 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 1, 0, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 0, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial!=0 and m_serial!=m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 1, 0, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 0, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 1, 0, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 0, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times == 2 and n_loop_times == 2:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif k_serial==0 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif k_serial==k_loop_times-1 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial!=m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times == 2 and n_loop_times >= 3:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1) and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times >= 3 and n_loop_times == 1:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial==0 and k_serial==k_loop_times-1 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial!=0 and m_serial!=m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times >= 3 and n_loop_times == 2:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial!=0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif m_serial!=m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif k_serial!=k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 0, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 0, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
if m_loop_times >= 2 and k_loop_times >= 3 and n_loop_times >= 3:
    for m_serial in range(0,m_loop_times):
        for k_serial in range(0,k_loop_times):
            for n_serial in range(0,n_loop_times):
                counter += 1
                # 计算本次片上的mkn规模大小
                m_num, k_num, n_num = f.mkn_num(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_serial_next, k_serial_next, n_serial_next = f.next_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_serial_before, k_serial_before, n_serial_before = f.before_num_mkn(m_serial, k_serial, n_serial, m_loop_times, k_loop_times, n_loop_times)
                m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_num_before, k_num_before, n_num_before = f.mkn_num(m_serial_before, k_serial_before, n_serial_before, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
                m_coordinate, k_coordinate, n_coordinate = m_serial_next * m, k_serial_next * k, n_serial_next * n
                # 比较A_buf的ifmap在片上是否有可重复使用的数据
                if not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1):
                    if G_A_in_use == 0:
                        ifmap_img2col1_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    else:
                        ifmap_img2col0_new = [[(-1,-1,-1,-1) for i in range(k)] for j in range(m)]
                    ifmap_img2col0_new, ifmap_img2col1_new, transmission_zero, transmission_local, transmission_on_chip = \
                    f.transmission_ifmap(FH, FW, OX, OY, IX, IY, stride, m_coordinate, k_coordinate, m_num_next, k_num_next, m, k, ifmap_img2col0_new, ifmap_img2col1_new, ifmap_img2col0_old, ifmap_img2col1_old, C_channel, G_A_in_use, Batchsize, dataflow_M, dataflow_K)
                    for ii in range(m):
                        for jj in range(k):
                            ifmap_img2col1_old[ii][jj] = ifmap_img2col1_new[ii][jj]
                            ifmap_img2col0_old[ii][jj] = ifmap_img2col0_new[ii][jj]
                else:
                    transmission_zero, transmission_local, transmission_on_chip = 0, 0, 0
                A_buf_tile_trans = f.ceil(m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip, bandwidth)
                B_buf_tile_trans = f.ceil(k_num_next * n_num_next, bandwidth)
                # 判断C是否要从片外读入，第一次是不需要读入的
                if partial_sum[m_serial_next][n_serial_next] == 0:
                    C_buf_tile_trans = 0
                else:
                    C_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
                Y_buf_tile_trans = f.ceil(m_num_before * n_num_before, bandwidth)
                on_chip_alter = 0

                # 第一个
                if m_serial==0 and k_serial==0 and n_serial==0:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 0
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 0
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 最后一个
                elif m_serial==m_loop_times-1 and k_serial==k_loop_times-1 and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 0, 0, 0, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 0, 0, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr,\
                        G_C1_ready, G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, b_loops,\
                        on_chip_alter, bw_in_use, communication_Y_cycle, G_C_ptr_add, C_compute_in_SA, communication_on_chip,\
                        communication_interval, communication_internal, counter_A_read, G_C_ptw_add, c_loops = tlast.buf_process(
                                                        G_A_in_use,
                                                        G_A0_ready,
                                                        G_A1_ready,
                                                        G_A0_ptr,
                                                        G_A0_ptw,
                                                        G_A1_ptr,
                                                        G_A1_ptw,
                                                        a_loops,
                                                        G_B0_ready,
                                                        G_B1_ready,
                                                        G_B0_ptr,
                                                        G_B0_ptw,
                                                        G_B1_ptr,
                                                        G_B1_ptw,
                                                        G_B_in_use,
                                                        C_SA_load,
                                                        A_interval_work,
                                                        A_interval_spare,
                                                        G_C0_ready,
                                                        G_C0_ptw,
                                                        G_C0_ptr,
                                                        G_C1_ready,
                                                        G_C1_ptw,
                                                        G_C1_ptr,
                                                        G_Cw_in_use,
                                                        G_Cr_in_use,
                                                        b_loops,
                                                        Array_i,
                                                        Array_j,
                                                        m_num,
                                                        n_num,
                                                        k_num,
                                                        m_num_before,
                                                        n_num_before,
                                                        m_num_next,
                                                        n_num_next,
                                                        bandwidth,
                                                        compute_pipeline,
                                                        on_chip_alter,
                                                        A_buf_tile_trans,
                                                        B_buf_tile_trans,
                                                        C_buf_tile_trans,
                                                        Y_buf_tile_trans,
                                                        bw_in_use,
                                                        communication_Y_cycle,
                                                        C_load_out,
                                                        G_C_ptr_add,
                                                        G_C_ptw_add,
                                                        C_compute_in_SA,
                                                        communication_on_chip,
                                                        communication_interval,
                                                        communication_internal,
                                                        counter_A_read,
                                                        c_loops
                                                        )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                elif not(m_serial==m_loop_times-1 and k_serial==k_loop_times-1) and n_serial==n_loop_times-1:
                    A_load, B_load, C_load_in, C_load_out = 1, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 1, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                else:
                    A_load, B_load, C_load_in, C_load_out = 0, 1, 1, 1
                    A_load0, B_load0, C_load_in0, C_load_out0 = 0, 1, 1, 1
                    while(on_chip_alter == 0):
                        G_A_in_use, G_A0_ready, G_A1_ready, G_A0_ptr, G_A0_ptw, G_A1_ptr, G_A1_ptw, a_loops,\
                        G_B0_ready, G_B1_ready, G_B0_ptr, G_B0_ptw, G_B1_ptr, G_B1_ptw, G_B_in_use, b_loops,\
                        C_SA_load, A_interval_work, A_interval_spare, G_C0_ready, G_C0_ptw, G_C0_ptr, G_C1_ready,\
                        G_C1_ptw, G_C1_ptr, G_Cw_in_use, G_Cr_in_use, on_chip_alter, bw_in_use,\
                        communication_A_cycle, communication_B_cycle, communication_C_cycle, communication_Y_cycle,\
                        G_C_ptr_add, C_compute_in_SA, communication_on_chip, communication_interval, communication_internal,\
                        counter_A_read, G_C_ptw_add, c_loops = t.buf_process(
                                                            G_A_in_use,
                                                            G_A0_ready,
                                                            G_A1_ready,
                                                            G_A0_ptr,
                                                            G_A0_ptw,
                                                            G_A1_ptr,
                                                            G_A1_ptw,
                                                            a_loops,
                                                            G_B0_ready,
                                                            G_B1_ready,
                                                            G_B0_ptr,
                                                            G_B0_ptw,
                                                            G_B1_ptr,
                                                            G_B1_ptw,
                                                            G_B_in_use,
                                                            b_loops,
                                                            C_SA_load,
                                                            A_interval_work,
                                                            A_interval_spare,
                                                            G_C0_ready,
                                                            G_C0_ptw,
                                                            G_C0_ptr,
                                                            G_C1_ready,
                                                            G_C1_ptw,
                                                            G_C1_ptr,
                                                            G_Cw_in_use,
                                                            G_Cr_in_use,
                                                            Array_i,
                                                            Array_j,
                                                            m_num,
                                                            n_num,
                                                            k_num,
                                                            m_num_before,
                                                            n_num_before,
                                                            m_num_next,
                                                            n_num_next,
                                                            bandwidth,
                                                            compute_pipeline,
                                                            on_chip_alter,
                                                            A_buf_tile_trans,
                                                            B_buf_tile_trans,
                                                            C_buf_tile_trans,
                                                            Y_buf_tile_trans,
                                                            bw_in_use,
                                                            communication_A_cycle,
                                                            communication_B_cycle,
                                                            communication_C_cycle,
                                                            communication_Y_cycle,
                                                            A_load,
                                                            B_load,
                                                            C_load_in,
                                                            C_load_out,
                                                            G_C_ptr_add,
                                                            G_C_ptw_add,
                                                            C_compute_in_SA,
                                                            communication_on_chip,
                                                            communication_interval,
                                                            communication_internal,
                                                            counter_A_read,
                                                            c_loops
                                                            )
                        cycle += 1
                        if tracking == 1:
                            writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
                            'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
                            'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
                # 记录片外的部分和状态，“读入”到片上一次后，下次读取处于存在部分和的状态
                if A_load == 1:
                    ifmap_transmission_on_chip += transmission_on_chip
                communication_off_chip += A_load0 * f.ceil((m_num_next * k_num_next - transmission_zero - transmission_local - transmission_on_chip), bandwidth)\
                + B_load0 * f.ceil(k_num_next * n_num_next, bandwidth) + C_load_in0 * partial_sum[m_serial_next][n_serial_next] * f.ceil(m_num_next * n_num_next, bandwidth)\
                + C_load_out0 * f.ceil(m_num_before * n_num_before, bandwidth)
                if C_load_in == 1:
                    partial_sum[m_serial_next][n_serial_next] = 1
                print("\r", end="")
                print("Simulation progress: {}%: ".format(int(counter/counter_total * 100)), end="")
                sys.stdout.flush()
#############################################################################################################################
#############################################################################################################################
#############################################################################################################################
# 将C_buf中的数据写回HBM
# write_back_flag意义(0表示C_buf还在写入,1表示C_buf写回HBM,2表示写回完成)
m_num_next, k_num_next, n_num_next = f.mkn_num(m_serial_next, k_serial_next, n_serial_next, m_loop_times, k_loop_times, n_loop_times, M, K, N, m, k, n)
C_buf_tile_w = f.expansion(m_num, Array_i) * f.expansion(n_num, Array_j)
Y_buf_tile_trans = f.ceil(m_num_next * n_num_next, bandwidth)
write_back_flag = 0
while(write_back_flag != 2):
    cycle += 1
    write_back_flag, G_Cr_in_use, G_Cw_in_use, G_C0_ptr, G_C0_ptw, G_C1_ptr, G_C1_ptw,\
    communication_Y_cycle, C_compute_in_SA, A_interval_work, A_interval_spare, G_C_ptw_add = \
    t.write_back(write_back_flag,
                    G_Cr_in_use,
                    G_Cw_in_use,
                    G_C0_ptr,
                    G_C0_ptw,
                    G_C1_ptr,
                    G_C1_ptw,
                    Array_i,
                    Array_j,
                    compute_pipeline,
                    C_buf_tile_w,
                    bandwidth,
                    Y_buf_tile_trans,
                    communication_Y_cycle,
                    C_compute_in_SA,
                    A_interval_work,
                    A_interval_spare,
                    G_C_ptw_add)
    if tracking == 1:
        writer.writerow({'cycle':str(cycle),'G_B0_ptw':str(G_B0_ptw),'G_B1_ptw':str(G_B1_ptw),'G_B0_ptr':str(G_B0_ptr),'G_B1_ptr':str(G_B1_ptr),\
        'G_A0_ptw':str(G_A0_ptw),'G_A1_ptw':str(G_A1_ptw),'G_A0_ptr':str(G_A0_ptr),'G_A1_ptr':str(G_A1_ptr),\
        'G_C0_ptr':str(G_C0_ptr),'G_C1_ptr':str(G_C1_ptr),'G_C0_ptw':str(G_C0_ptw),'G_C1_ptw':str(G_C1_ptw)})
communication_off_chip += f.ceil(m_num_next * n_num_next, bandwidth)
if tracking == 1:
    output_file.close()

# 统计结果
communication_cycle = communication_cycle + communication_A_cycle + communication_B_cycle + communication_C_cycle + communication_Y_cycle
communication_on_chip += ifmap_transmission_on_chip
PE_utility = M * K * N / (Array_i * Array_j * cycle)
throughput = M * K * N / cycle
energy_cost_communication = communication_off_chip * 200 + communication_on_chip * 6 + communication_interval * 2 + communication_internal
energy_cost_computation = communication_internal // 3
computation_cycle = Array_i * compute_pipeline + N * f.roundup(M, Array_j) * f.roundup(K, Array_i) + Array_j
output_file = open('./data/output/output_%d.csv'%(level_num), 'w')
fieldnames = ['cycle','communication_cycle','communication_A_cycle','communication_B_cycle','communication_C_cycle',\
'communication_Y_cycle','PE_utility','throughput','communication_off_chip','communication_on_chip','communication_interval',\
'communication_internal','energy_cost_communication','energy_cost_computation']
writer = csv.DictWriter(output_file, fieldnames=fieldnames)
writer.writeheader()
writer.writerow({'cycle':str(cycle),'communication_cycle':str(communication_cycle),'communication_A_cycle':str(communication_A_cycle),\
'communication_B_cycle':str(communication_B_cycle),'communication_C_cycle':str(communication_C_cycle),\
'communication_Y_cycle':str(communication_Y_cycle),'PE_utility':str(PE_utility),'throughput':str(throughput),\
'communication_off_chip':str(int(communication_off_chip)),'communication_on_chip':str(int(communication_on_chip)),\
'communication_interval':str(int(communication_interval)),'communication_internal':str(int(communication_internal)),\
'energy_cost_communication':str(int(energy_cost_communication)),'energy_cost_computation':str(int(energy_cost_computation))})
output_file.close()
