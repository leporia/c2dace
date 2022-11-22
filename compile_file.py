import dace
from dace.sdfg import SDFG

sdfg = SDFG("func_hmac").from_file("tmp/func_hmac-opt.sdfg")

for codeobj in sdfg.generate_code():
    if codeobj.title == 'Frame':
        with open("tmp/ext_comp.cpp", 'w') as fp:
            fp.write(codeobj.clean_code)
