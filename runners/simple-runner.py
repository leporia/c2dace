import os

n_runs = 10
threads = [1, 2, 4, 6, 8, 12]
mask = ["0x1", "0x5", "0x55", "0x555", "0x55F", "0xFFF"]

runners = [
    #("dace.out", True),
    ("gcc.out", False),
    #("polly.out", True),
    #("clang.out", False),
    ("gcc_twin.out", False),
    #("clang_twin.out", False),
    #("polly_twin.out", True),
]

os.mkdir('simple_results')

for run in runners:
    name, parallel = run
    os.mkdir("simple_results/" + name)

    acc_threads = threads
    acc_mask = mask
    if not parallel:
        acc_threads = [1]
        acc_mask = ["0x1"]
    
    for t, m in zip(acc_threads, acc_mask):
        print("Running " + name + " with " + str(t) + " threads")
        os.mkdir("simple_results/" + name + "/thr" + str(t))
        for i in range(n_runs):
            if not parallel:
                os.system("taskset " + m + " ./" + name + " 12 600000")
            else:
                os.system("OMP_NUM_THREADS=" + str(t) + " taskset " + m + " ./" + name + " 12 600000")

        for dir in os.listdir("./"):
            if not dir.startswith("papi_hl_output"):
                continue
            for f in os.listdir(dir):
                os.rename(dir + "/" + f, "simple_results/" + name + "/thr" + str(t) + "/" + f)
            os.rmdir(dir)
