import dace
from dace.sdfg import SDFG
from dace import registry
from dace import dtypes
from dace.codegen.targets.framecode import DaCeCodeGenerator
from dace.codegen.dispatcher import DefinedType
from dace.codegen.targets.cpu import CPUCodeGen
from dace.codegen.targets import cpp
from dace.codegen import cppunparse
from dace.sdfg import nodes
from dace.properties import CodeBlock

dace.StorageType.register("ThreadLocal_with_init")

@registry.autoregister_params(name="thread_init")
class ThreadInit_Alloc(CPUCodeGen):
    def __init__(self, frame_codegen: DaCeCodeGenerator, sdfg: dace.SDFG):
        self._frame = frame_codegen
        self._dispatcher = frame_codegen.dispatcher
        self._dispatcher.register_array_dispatcher(dace.StorageType.ThreadLocal_with_init, self)
        self._locals = cppunparse.CPPLocals()
        self._ldepth = 0
        self._toplevel_schedule = None

        cpu_storage = [dtypes.StorageType.CPU_Heap, dtypes.StorageType.CPU_ThreadLocal, dtypes.StorageType.Register]
        for storage in cpu_storage:
            self._dispatcher.register_copy_dispatcher(storage, dace.StorageType.ThreadLocal_with_init, None, self)
            self._dispatcher.register_copy_dispatcher(dace.StorageType.ThreadLocal_with_init, storage, None, self)

    def allocate_array(self, sdfg, dfg, state_id, node, nodedesc, function_stream, declaration_stream, allocation_stream):
        tasklet = None
        edge = None
        for n in dfg.nodes():
            if tasklet is not None:
                break

            for e in dfg.out_edges(n):
                if e.dst == node:
                    tasklet = e.src
                    edge = e
                    break

        if tasklet is None:
            raise ValueError("Could not find tasklet")

        code = tasklet.code.code
        tasklet_name = edge.src_conn

        alloc_name = cpp.ptr(node.data, nodedesc, sdfg, self._frame)
        name = alloc_name

        declared = self._dispatcher.declared_arrays.has(alloc_name)

        arrsize = nodedesc.total_size

        if not declared:
            function_stream.write(
                "{ctype} *{name};\n#pragma omp threadprivate({name})".format(ctype=nodedesc.dtype.ctype, name=name),
                sdfg,
                state_id,
                node,
            )
            self._dispatcher.declared_arrays.add_global(name, DefinedType.Pointer, '%s *' % nodedesc.dtype.ctype)

        # Allocate in each OpenMP thread
        allocation_stream.write(
            """
            #pragma omp parallel
            {{
                {name} = new {ctype} DACE_ALIGN(64)[{arrsize}];""".format(ctype=nodedesc.dtype.ctype,
                                                                            name=alloc_name,
                                                                            arrsize=cpp.sym2cpp(arrsize)),
            sdfg,
            state_id,
            node,
        )

        super(ThreadInit_Alloc, self)._generate_Tasklet(sdfg, dfg, state_id, tasklet, function_stream, allocation_stream)

        # Close OpenMP parallel section
        allocation_stream.write('}')
        self._dispatcher.defined_vars.add_global(name, DefinedType.Pointer, '%s *' % nodedesc.dtype.ctype)

    def declare_array(self, sdfg, dfg, state_id, node, nodedesc, function_stream, declaration_stream):
        nodedesc.storage = dtypes.StorageType.CPU_ThreadLocal
        super(ThreadInit_Alloc, self).deallocate_array(sdfg, dfg, state_id, node, nodedesc, function_stream, declaration_stream)

    def deallocate_array(self, sdfg, dfg, state_id, node, nodedesc, function_stream, callsite_stream):
        nodedesc.storage = dtypes.StorageType.CPU_ThreadLocal
        super(ThreadInit_Alloc, self).deallocate_array(sdfg, dfg, state_id, node, nodedesc, function_stream, callsite_stream)


sdfg = SDFG("func_hmac").from_file("tmp/func_hmac-opt.sdfg")

for codeobj in sdfg.generate_code():
    if codeobj.title == 'Frame':
        with open("tmp/ext_comp.cpp", 'w') as fp:
            fp.write(codeobj.clean_code)
