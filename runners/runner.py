import os
import sys
import subprocess
import json

PAPI_DIR = "/home/mafaldo/Downloads/papi/src/install"

def create_test_dace(data_size, n_threads):
    data = ""
    with open(".dacecache/_func_hmac/src/cpu/_func_hmac.cpp", 'r') as fp:
        data = fp.read()

    start_loc = data.find("unsigned char dace_result_0[")
    start_loc += len("unsigned char dace_result_0[")
    end_loc = data[start_loc:].find("]")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("for (auto tmp_for_1 = 0; tmp_for_1 < ")
    start_loc += len("for (auto tmp_for_1 = 0; tmp_for_1 < ")
    end_loc = data[start_loc:].find(";")

    data = data[:start_loc] + str(data_size-19) + data[start_loc + end_loc:]

    start_loc = data.find("for (i = 0; (i < ")
    start_loc += len("for (i = 0; (i < ")
    end_loc = data[start_loc:].find(")")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("omp_set_num_threads(")
    start_loc += len("omp_set_num_threads(")
    end_loc = data[start_loc:].find(")")

    data = data[:start_loc] + str(n_threads) + data[start_loc + end_loc:]

    with open(".dacecache/_func_hmac/src/cpu/_func_hmac.cpp", 'w') as fp:
        fp.write(data)

    os.system("LD_LIBRARY_PATH=" + PAPI_DIR + "/lib:$LD_LIBRARY_PATH gcc .dacecache/_func_hmac/sample/_func_hmac_main.cpp .dacecache/_func_hmac/src/cpu/_func_hmac.cpp -I ~/.local/lib/python3.10/site-packages/dace/runtime/include -lstdc++ -lm -lcrypto -O3 -fopenmp -I/home/mafaldo/Downloads/papi/src/install/include -L/home/mafaldo/Downloads/papi/src/install/lib")

def create_test_serial(data_size):
    data = ""
    with open("pbkdf2/func_hmac_papi.c", 'r') as fp:
        data = fp.read()

    start_loc = data.find("long key_length = ")
    start_loc += len("long key_length = ")
    end_loc = data[start_loc:].find(";")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("unsigned char result[")
    start_loc += len("unsigned char result[")
    end_loc = data[start_loc:].find("]")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    with open("pbkdf2/func_hmac_papi.c", 'w') as fp:
        fp.write(data)

    os.system("LD_LIBRARY_PATH=" + PAPI_DIR + "/lib:$LD_LIBRARY_PATH gcc pbkdf2/func_hmac_papi.c -lstdc++ -lm -lcrypto -O3 -I/home/mafaldo/Downloads/papi/src/install/include -L/home/mafaldo/Downloads/papi/src/install/lib")

def create_test_parallel(data_size, n_threads):
    data = ""
    with open("pbkdf2/func_hmac_parallel.c", 'r') as fp:
        data = fp.read()

    start_loc = data.find("long key_length = ")
    start_loc += len("long key_length = ")
    end_loc = data[start_loc:].find(";")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("unsigned char result[")
    start_loc += len("unsigned char result[")
    end_loc = data[start_loc:].find("]")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("omp_set_num_threads(")
    start_loc += len("omp_set_num_threads(")
    end_loc = data[start_loc:].find(")")

    data = data[:start_loc] + str(n_threads) + data[start_loc + end_loc:]

    with open("pbkdf2/func_hmac_parallel.c", 'w') as fp:
        fp.write(data)

    os.system("LD_LIBRARY_PATH=" + PAPI_DIR + "/lib:$LD_LIBRARY_PATH gcc pbkdf2/func_hmac_parallel.c -lstdc++ -lm -lcrypto -O3 -fopenmp -I/home/mafaldo/Downloads/papi/src/install/include -L/home/mafaldo/Downloads/papi/src/install/lib")

def create_test_fast(data_size, n_threads):
    data = ""
    with open("pbkdf2/fastpbkdf2.c", 'r') as fp:
        data = fp.read()

    start_loc = data.find("long key_length = ")
    start_loc += len("long key_length = ")
    end_loc = data[start_loc:].find(";")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("unsigned char result[")
    start_loc += len("unsigned char result[")
    end_loc = data[start_loc:].find("]")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("omp_set_num_threads(")
    start_loc += len("omp_set_num_threads(")
    end_loc = data[start_loc:].find(")")

    data = data[:start_loc] + str(n_threads) + data[start_loc + end_loc:]

    with open("pbkdf2/fastpbkdf2.c", 'w') as fp:
        fp.write(data)

    os.system("LD_LIBRARY_PATH=" + PAPI_DIR + "/lib:$LD_LIBRARY_PATH gcc pbkdf2/fastpbkdf2.c -lstdc++ -lm -lcrypto -O3 -fopenmp -I/home/mafaldo/Downloads/papi/src/install/include -L/home/mafaldo/Downloads/papi/src/install/lib")

def create_test_polly(data_size, n_threads):
    data = ""
    with open("pbkdf2/func_hmac_polly.c", 'r') as fp:
        data = fp.read()

    start_loc = data.find("long key_length = ")
    start_loc += len("long key_length = ")
    end_loc = data[start_loc:].find(";")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("unsigned char result[")
    start_loc += len("unsigned char result[")
    end_loc = data[start_loc:].find("]")

    data = data[:start_loc] + str(data_size) + data[start_loc + end_loc:]

    start_loc = data.find("omp_set_num_threads(")
    start_loc += len("omp_set_num_threads(")
    end_loc = data[start_loc:].find(")")

    data = data[:start_loc] + str(n_threads) + data[start_loc + end_loc:]

    with open("pbkdf2/func_hmac_polly.c", 'w') as fp:
        fp.write(data)

    os.system("~/Downloads/clang_source/clang/bin/clang-15 pbkdf2/func_hmac_polly.c -mllvm -polly -mllvm -polly-parallel -lgomp -lstdc++ -lm -lcrypto -O3 -fopenmp -I/home/mafaldo/Downloads/papi/src/install/include -L/home/mafaldo/Downloads/papi/src/install/lib")

def run_tests(n_runs, dace_times, serial_times):
    for i in range(n_runs):
        p = subprocess.Popen(["/usr/bin/time", "-f", "%e", "./a.out"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time_output = p.stderr.readlines()

        time_taken = time_output[0].decode("utf-8")[:4]
        dace_times.append(time_taken)

        p = subprocess.Popen(["/usr/bin/time", "-f", "%e", "./pbkdf2/func_hmac"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time_output = p.stderr.readlines()

        time_taken = time_output[0].decode("utf-8")[:4]
        serial_times.append(time_taken)

n_runs = 10
data_sizes = [1, 2, 4]

data = {}
data["serial"] = {}
data["dace"] = {}
data["parallel"] = {}
data["polly"] = {}
data["fastpbkdf2"] = {}

for i in data_sizes:
    create_test_serial(20*i)

    data["serial"][i] = []
    print("Running serial with " + str(20*i) + " data size")
    for j in range(n_runs):
        p = subprocess.Popen(["/usr/bin/time", "-f", "%e", "./a.out"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time_output = p.stderr.readlines()

        time_taken = time_output[0].decode("utf-8")[:4]
        data["serial"][i].append(time_taken)

    data["parallel"][i] = {}
    for j in range(1, i+1):
        data["parallel"][i][j] = []
        if i % j != 0:
            continue
        print("Running parallel with " + str(j) + " threads and " + str(20*i) + " data size")
        create_test_parallel(20*i, j)
        for k in range(n_runs):
            p = subprocess.Popen(["/usr/bin/time", "-f", "%e", "./a.out"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time_output = p.stderr.readlines()

            time_taken = time_output[0].decode("utf-8")[:4]
            data["parallel"][i][j].append(time_taken)

    data["dace"][i] = {}
    for j in range(1, i+1):
        data["dace"][i][j] = []
        if i % j != 0:
            continue
        print("Running DaCe with " + str(j) + " threads and " + str(20*i) + " data size")
        create_test_dace(20*i, j)
        for k in range(n_runs):
            p = subprocess.Popen(["/usr/bin/time", "-f", "%e", "./a.out"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time_output = p.stderr.readlines()

            time_taken = time_output[0].decode("utf-8")[:4]
            data["dace"][i][j].append(time_taken)

    data["polly"][i] = {}
    for j in range(1, i+1):
        data["polly"][i][j] = []
        if i % j != 0:
            continue
        print("Running Polly with " + str(j) + " threads and " + str(20*i) + " data size")
        create_test_polly(20*i, j)
        for k in range(n_runs):
            p = subprocess.Popen(["/usr/bin/time", "-f", "%e", "./a.out"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time_output = p.stderr.readlines()

            time_taken = time_output[0].decode("utf-8")[:4]
            data["polly"][i][j].append(time_taken)

    data["fastpbkdf2"][i] = {}
    for j in range(1, i+1):
        data["fastpbkdf2"][i][j] = []
        if i % j != 0:
            continue
        print("Running fastpbkdf2 with " + str(j) + " threads and " + str(20*i) + " data size")
        create_test_fast(20*i, j)
        for k in range(n_runs):
            p = subprocess.Popen(["/usr/bin/time", "-f", "%e", "./a.out"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time_output = p.stderr.readlines()

            time_taken = time_output[0].decode("utf-8")[:4]
            data["fastpbkdf2"][i][j].append(time_taken)

with open("data.json", 'w') as fp:
    json.dump(data, fp)

'''
for i in data_sizes:
    create_test_serial(20*i)
    old_output = ""

    print("Running serial with " + str(20*i) + " data size")
    for j in range(n_runs):
        serial_output = os.popen("PAPI_EVENTS=\"PAPI_TOT_INS,PAPI_TOT_CYC\" PAPI_OUTPUT_DIRECTORY=\"papi_out\" ./a.out").read()
        if old_output == "":
            old_output = serial_output

        if old_output != serial_output:
            print("ERROR: Serial output not consistent")
            sys.exit(1)
    
    os.rename("papi_out/papi_hl_output", "papi_out/serial_" + str(i))

    for j in range(1, i+1):
        if i % j != 0:
            continue
        print("Running Polly with " + str(j) + " threads and " + str(20*i) + " data size")
        create_test_polly(20*i, j)
        for k in range(n_runs):
            polly_output = os.popen("PAPI_EVENTS=\"PAPI_TOT_INS,PAPI_TOT_CYC\" PAPI_OUTPUT_DIRECTORY=\"papi_out\" OMP_NUM_THREADS=" + str(j) + " ./a.out").read()

            if old_output != polly_output:
                print("ERROR: Polly output not consistent")
                sys.exit(1)

        os.rename("papi_out/papi_hl_output", "papi_out/polly_" + str(i) + "_" + str(j))

    for j in range(1, i+1):
        if i % j != 0:
            continue
        print("Running parallel with " + str(j) + " threads and " + str(20*i) + " data size")
        create_test_parallel(20*i, j)
        for k in range(n_runs):
            parallel_output = os.popen("PAPI_EVENTS=\"PAPI_TOT_INS,PAPI_TOT_CYC\" PAPI_OUTPUT_DIRECTORY=\"papi_out\" OMP_NUM_THREADS=" + str(j) + " ./a.out").read()

            if old_output != parallel_output:
                print("ERROR: Parallel output not consistent")
                sys.exit(1)
        
        os.rename("papi_out/papi_hl_output", "papi_out/parallel_" + str(i) + "_" + str(j))

    for j in range(1, i+1):
        if i % j != 0:
            continue
        print("Running DACE with " + str(j) + " threads and " + str(20*i) + " data size")
        create_test_dace(20*i, j)
        for k in range(n_runs):
            dace_output = os.popen("PAPI_EVENTS=\"PAPI_TOT_INS,PAPI_TOT_CYC\" PAPI_OUTPUT_DIRECTORY=\"papi_out\" OMP_NUM_THREADS=" + str(j) + " ./a.out").read()

            if old_output != dace_output:
                print("ERROR: DACE output not consistent")
                sys.exit(1)

        os.rename("papi_out/papi_hl_output", "papi_out/dace_" + str(i) + "_" + str(j))
'''