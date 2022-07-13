#DACE_INCLUDE = ~/.local/lib/python3.9/site-packages/dace/runtime/include
DACE_INCLUDE = /home/mafaldo/.local/lib/python3.9/site-packages/dace/runtime/include

FILENAME := matrix_init
#FILE := HPCCG_preprocessed/$(FILENAME).c
#FILE := bots_preprocessed/$(FILENAME).c
FILE := simple_tests/$(FILENAME).c
FILENAME2 := _$(FILENAME)

run:
	python3 c2dace/c2d.py -f $(FILE)

clean:
	rm -Rf tmp/* .dacecache _dacegraphs a.out orig

compile:
	gcc .dacecache/$(FILENAME2)/sample/$(FILENAME2)_main.cpp .dacecache/$(FILENAME2)/src/cpu/$(FILENAME2).cpp -I $(DACE_INCLUDE) -lstdc++ -lm -march=native -O3

test:
	python3 testing/harness.py
