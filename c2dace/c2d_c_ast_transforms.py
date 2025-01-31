from c2d_clang2c_ast import *
from typing import List, Dict, Set
import copy


class UnaryExtractorNodeLister(NodeVisitor):
    def __init__(self):
        self.nodes: List[UnOp] = []

    def visit_UnOp(self, node: UnOp):
        if node.op in ["++", "--"]:
            self.nodes.append(node)
        return self.generic_visit(node)

    def visit_ForStmt(self, node: ForStmt):
        return self.generic_visit(node.body[0])

    def visit_BasicBlock(self, node: BasicBlock):
        return


class UnaryExtractor(NodeTransformer):
    def __init__(self, count=0):
        self.count = count

    def visit_ForStmt(self, node: ForStmt):
        return ForStmt(init=node.init,
                       body=self.visit(node.body[0]),
                       cond=node.cond,
                       iter=node.iter)

    def visit_UnOp(self, node: UnOp):
        if node.op in ["++", "--"]:
            self.count = self.count + 1
            return DeclRefExpr(name="tmp_unop_result" + str(self.count - 1))
        else:
            return node

    def visit_BasicBlock(self, node: BasicBlock):
        newbody = []
        for child in node.body:
            if isinstance(child, ForStmt):
                newbody.append(self.visit(child))
                continue

            lister = UnaryExtractorNodeLister()
            lister.visit(child)
            res = lister.nodes
            post = []
            tmp_count = self.count
            if res is not None:
                for i in range(0, len(res)):
                    if res[i] in node.body:
                        #print("SKIPPING!")
                        continue
                    tmp_name = "tmp_unop_result" + str(tmp_count)
                    newbody.append(
                        DeclStmt(vardecl=[
                            VarDecl(
                                name=tmp_name, type=Int(), init=res[i].lvalue)
                        ]))
                    if res[i].postfix:
                        post.append(res[i])
                    else:
                        newbody.append(
                            BinOp(op="=",
                                  lvalue=DeclRefExpr(name=tmp_name),
                                  rvalue=res[i]))
                    tmp_count = tmp_count + 1
            if isinstance(child, UnOp):
                newbody.append(
                    UnOp(op=child.op, lvalue=self.visit(child.lvalue), postfix=child.postfix))
            else:
                newbody.append(self.visit(child))
            for i in post:
                newbody.append(i)
        return BasicBlock(body=newbody)


class IndicesExtractorNodeLister(NodeVisitor):
    def __init__(self):
        self.nodes: List[ArraySubscriptExpr] = []

    def visit_ArraySubscriptExpr(self, node: ArraySubscriptExpr):
        #if not isinstance(node.index,IntLiteral):
        self.nodes.append(node)
        return self.generic_visit(node)

    def visit_BasicBlock(self, node: BasicBlock):
        return

class ParenExprRemover(NodeTransformer):
    def visit_ArraySubscriptExpr(self, node: ArraySubscriptExpr):
        if isinstance(node.unprocessed_name, ArraySubscriptExpr):
            node.unprocessed_name = self.visit(node.unprocessed_name)
            return node
            
        tmp = node.unprocessed_name
        while isinstance(tmp, ParenExpr):
            tmp = tmp.expr

        node.unprocessed_name = tmp
        return node

class IndicesExtractor(NodeTransformer):
    def __init__(self, count=0):
        self.count = count

    def visit_ArraySubscriptExpr(self, node: ArraySubscriptExpr):

        #if isinstance(node.index,IntLiteral):
        #    return node
        if not hasattr(self, "count"):
            self.count = 0
        else:
            self.count = self.count + 1
        tmp = self.count
        return ArraySubscriptExpr(
            name=node.name,
            indices=node.indices,
            type=node.type,
            unprocessed_name=self.visit(node.unprocessed_name),
            index=DeclRefExpr(name="tmp_index_" + str(tmp - 1), type=Int()))

    def visit_BasicBlock(self, node: BasicBlock):
        newbody = []

        for child in node.body:
            # res = [node for node in Node.walk(child) if isinstance(node, ArraySubscriptExpr)]
            lister = IndicesExtractorNodeLister()
            lister.visit(child)
            res = lister.nodes
            temp = self.count
            if res is not None:
                for i in range(0, len(res)):
                    tmp_name = "tmp_index_" + str(temp)
                    temp = temp + 1
                    newbody.append(
                        DeclStmt(vardecl=[VarDecl(name=tmp_name, type=Int())]))
                    newbody.append(
                        BinOp(op="=",
                              lvalue=DeclRefExpr(name=tmp_name),
                              rvalue=res[i].index))
            newbody.append(self.visit(child))
        return BasicBlock(body=newbody)


class AliasLoopIterator(NodeTransformer):
    def visit_BasicBlock(self, node: BasicBlock):
        new_body = []
        name_type_mapping = dict()
        for child in node.body:
            if isinstance(child, DeclStmt):
                for vardecl in child.vardecl:
                    name_type_mapping[vardecl.name] = vardecl.type
                new_body.append(self.visit(child))
            elif isinstance(child, VarDecl):
                name_type_mapping[child.name] = child.type
                new_body.append(self.visit(child))
            elif isinstance(child, ForStmt):
                candidates = self.find_used(child)
                if len(candidates) == 0:
                    new_body.append(child)
                else:
                    var_mapping = dict()
                    for i, c in enumerate(candidates):
                        c_type = name_type_mapping.get(c)

                        if c_type is None:
                            raise Exception(c, "was not declared")

                        new_name = c+"_old_"+str(i)
                        var_mapping[c] = new_name
                        new_body.append(DeclStmt(vardecl=[VarDecl(name=new_name, type=c_type)]))
                        new_body.append(BinOp(op="=", lvalue=DeclRefExpr(name=new_name), rvalue=DeclRefExpr(name=c)))

                    after_body = []
                    new_body.append(self.modify_for(child, var_mapping, after_body))
                    new_body += after_body
            else:
                new_body.append(self.visit(child))

        return BasicBlock(body=new_body)

    def find_used(self, node: ForStmt):
        if not isinstance(node.iter[0], BinOp) or not isinstance(node.iter[0].rvalue, BinOp) or not isinstance(node.iter[0].rvalue.rvalue, DeclRefExpr):
            return set()

        if not isinstance(node.init[0], DeclStmt):
            return set()

        for_blk = node.body if isinstance(node.body, BasicBlock) else node.body[0]

        candidate_vars = set()
        invalid_vars = set()
        counter = 0
        incr_point = -1
        for child in for_blk.body:
            counter += 1
            if not isinstance(child, BinOp) or not isinstance(child.lvalue, DeclRefExpr):
                continue

            is_invalid = True
            if child.lvalue.name not in invalid_vars:
                is_invalid = False
                invalid_vars.add(child.lvalue.name)

            if not isinstance(child.rvalue, BinOp) or not isinstance(child.rvalue.lvalue, DeclRefExpr):
                continue

            if child.lvalue.name != child.rvalue.lvalue.name:
                continue

            var_name = child.lvalue.name

            if var_name in candidate_vars:
                invalid_vars.add(var_name)
                continue

            if incr_point == -1:
                incr_point = counter
            elif incr_point+1 == counter:
                incr_point = counter 

            if not is_invalid:
                invalid_vars.remove(var_name)
            candidate_vars.add(var_name)

        if incr_point != len(for_blk.body):
            return set()

        return candidate_vars - invalid_vars

    def modify_for(self, node: ForStmt, candidate_vars: Dict[str, str], after_body: List[Node]):
        for_blk = node.body if isinstance(node.body, BasicBlock) else node.body[0]
        incr_name = node.iter[0].rvalue.rvalue.name
        iter_name = node.init[0].vardecl[0].name

        top_body = []
        new_body = []
        for child in for_blk.body:
            if isinstance(child, BinOp) and isinstance(child.lvalue, DeclRefExpr) and child.lvalue.name in candidate_vars:
                if isinstance(child.rvalue.rvalue, DeclRefExpr):
                    if child.rvalue.rvalue.name != incr_name:
                        print("WARNING: aliasing loop iterator with non-incrementing variable")
                    else:
                        top_body.append(
                            BinOp(
                                op="=",
                                lvalue=DeclRefExpr(name=child.lvalue.name),
                                rvalue=BinOp(
                                    op="+",
                                    lvalue=DeclRefExpr(name=iter_name),
                                    rvalue=DeclRefExpr(name=candidate_vars.get(child.lvalue.name))
                                )
                            )
                        )
                        after_body.append(
                            BinOp(
                                op="=",
                                lvalue=DeclRefExpr(name=child.lvalue.name),
                                rvalue=BinOp(
                                    op="+",
                                    lvalue=DeclRefExpr(name=child.lvalue.name),
                                    rvalue=DeclRefExpr(name=incr_name)
                                )
                            )
                        )

                elif isinstance(child.rvalue.rvalue, IntLiteral):
                    top_body.append(
                        BinOp(
                            op="=",
                            lvalue=DeclRefExpr(name=child.lvalue.name),
                            rvalue=BinOp(
                                op="+",
                                lvalue=BinOp(
                                    op="*",
                                    lvalue=BinOp(
                                        op="/",
                                        lvalue=DeclRefExpr(name=iter_name),
                                        rvalue=DeclRefExpr(name=incr_name)
                                    ),
                                    rvalue=child.rvalue.rvalue
                                ),
                                rvalue=DeclRefExpr(name=candidate_vars.get(child.lvalue.name))
                            )
                        )
                    )

                    after_body.append(
                        BinOp(
                            op="=",
                            lvalue=DeclRefExpr(name=child.lvalue.name),
                            rvalue=BinOp(
                                op="+",
                                lvalue=DeclRefExpr(name=child.lvalue.name),
                                rvalue=copy.deepcopy(child.rvalue.rvalue)
                            )
                        )
                    )

                else:
                    print("WARNING: Unsupported iterator aliasing", child.rvalue.rvalue)
                    new_body.append(self.visit(child))
            else:
                new_body.append(self.visit(child))

        node.body = [BasicBlock(body=top_body+new_body)]
        return node


class InvertForLoop(NodeTransformer):
    def visit_ForStmt(self, node: ForStmt):
        if not isinstance(node.init[0], BinOp):
            return self.generic_visit(node)
        
        if not isinstance(node.iter[0], BinOp) or node.iter[0].op != "=" or not isinstance(node.iter[0].rvalue, BinOp):
            return self.generic_visit(node)

        if node.iter[0].rvalue.op != "-":
            return self.generic_visit(node)

        if not isinstance(node.iter[0].rvalue.rvalue, DeclRefExpr):
            return self.generic_visit(node)

        iter_name = node.iter[0].lvalue.name
        init_val = node.init[0].rvalue
        incr_name = node.iter[0].rvalue.rvalue.name

        # check if iterator is used inside the body
        if len([x for x in walk(node.body[0]) if isinstance(x, DeclRefExpr) and x.name == iter_name]) > 0:
            return self.generic_visit(node)

        print("Notice: inverting loop with iter: " + str(iter_name) + " and incr_name: " + str(incr_name))

        node.iter[0].rvalue.op = "+"

        if node.cond[0].op == "<":
            node.cond[0].op = ">"
        elif node.cond[0].op == ">":
            node.cond[0].op = "<"
        elif node.cond[0].op == "<=":
            node.cond[0].op = ">="
        elif node.cond[0].op == ">=":
            node.cond[0].op = "<="

        node.cond[0].rvalue = BinOp(op="-", lvalue=init_val, rvalue=node.cond[0].rvalue)
        node.init[0].rvalue = IntLiteral(value="0")

        return self.generic_visit(node)


class ConditionalIncrementUnroller(NodeTransformer):
    def __init__(self):
        self.add_data = None
        self.incr_var = None
        self.init_var = None
        self.for_body = None
        
    def visit_BasicBlock(self, node: BasicBlock):
        new_body = []
        for child in node.body:
            if isinstance(child, ForStmt):
                self.add_data = None
                self.incr_var = None
                self.init_var = None
                self.for_body = None

                if_stmt = None
                new_node = self.visit(child)
                if self.add_data is not None:
                    new_body += self.add_data

                if self.for_body is not None:
                    remainder = BinOp(op="%", lvalue=copy.deepcopy(self.init_var), rvalue=DeclRefExpr(name=self.incr_var))
                    if_stmt = IfStmt(
                        cond=[BinOp(op="!=", rvalue=IntLiteral(value="0"), lvalue=copy.deepcopy(remainder))],
                        body_if=[BasicBlock(body=[
                            BinOp(op="=", lvalue=DeclRefExpr(name=self.incr_var), rvalue=remainder),
                        ] + self.for_body)],
                    )

                new_body.append(self.generic_visit(new_node))
                if if_stmt is not None:
                    new_body.append(if_stmt)

                continue

            new_body.append(self.visit(child))

        return BasicBlock(body=new_body)

    def visit_ForStmt(self, node: ForStmt):
        if len(node.init) != 1 or len(node.iter) != 1:
            return self.generic_visit(node)

        if not isinstance(node.body[0].body[0], IfStmt):
            return self.generic_visit(node)

        if_stmt = node.body[0].body[0]

        iter_name = None
        if isinstance(node.init[0], BinOp) and isinstance(node.init[0].lvalue, DeclRefExpr):
            iter_name = node.init[0].lvalue.name
            self.init_var = node.init[0].rvalue
        elif isinstance(node.init[0], DeclStmt):
            iter_name = node.init[0].vardecl[0].name
            self.init_var = node.init[0].vardecl[0].init
        else:
            return self.generic_visit(node)

        incr_name = None
        incr_name_type = None
        if isinstance(node.iter[0], BinOp) and isinstance(node.iter[0].rvalue, BinOp) and node.iter[0].rvalue.op in ['-', '+'] and isinstance(node.iter[0].rvalue.rvalue, DeclRefExpr):
            incr_name = node.iter[0].rvalue.rvalue.name
            incr_name_type = node.iter[0].rvalue.rvalue.type
        else:
            return self.generic_visit(node)

        if iter_name not in [x.name for x in walk(if_stmt.cond[0]) if isinstance(x, DeclRefExpr)]:
            return self.generic_visit(node)

        branch_single_iteration = None
        for child in if_stmt.body_if[0].body:
            if not isinstance(child, BinOp) or child.op != "=":
                continue

            if not isinstance(child.lvalue, DeclRefExpr) or not isinstance(child.rvalue, DeclRefExpr):
                continue

            if child.lvalue.name == incr_name and child.rvalue.name == iter_name:
                branch_single_iteration = True

        for child in if_stmt.body_else[0].body:
            if not isinstance(child, BinOp) or child.op != "=":
                continue

            if not isinstance(child.lvalue, DeclRefExpr) or not isinstance(child.rvalue, DeclRefExpr):
                continue

            if child.lvalue.name == incr_name and child.rvalue.name == iter_name:
                branch_single_iteration = False

        if branch_single_iteration is None:
            return self.generic_visit(node)

        if branch_single_iteration == True:
            self.add_data = copy.deepcopy(if_stmt.body_else[0].body)
        elif branch_single_iteration == False:
            self.add_data = copy.deepcopy(if_stmt.body_if[0].body)

        for_cond = node.cond[0]
        if isinstance(for_cond, BinOp):
            found = False
            if isinstance(for_cond.lvalue, DeclRefExpr) and for_cond.lvalue.name == iter_name:
                # bound is on rval
                for_cond.rvalue = DeclRefExpr(name=incr_name, type=incr_name_type)
                found = True
            elif isinstance(for_cond.lvalue, DeclRefExpr) and for_cond.rvalue.name == iter_name:
                # bound is on lval
                for_cond.lvalue = DeclRefExpr(name=incr_name, type=incr_name_type)
                found = True

            if found:
                if for_cond.op == "<":
                    for_cond.op = "<="
                elif for_cond.op == ">":
                    for_cond.op = ">="

        node.body[0].body = node.body[0].body[1:]

        self.incr_var = incr_name
        self.for_body = copy.deepcopy(node.body[0].body)

        return ForStmt(
            init=node.init,
            cond=[for_cond],
            iter=node.iter,
            body=node.body
        )


class BlockWhileToForLoop(NodeTransformer):
    def __init__(self):
        self.while_vars = dict()
        self.to_init = dict()
        self.global_init = set()

    def visit_BasicBlock(self, node: BasicBlock):
        for child in node.body:
            self.visit(child)

        for child in node.body:
            if isinstance(child, BinOp) and child.op == "=" and isinstance(child.lvalue, DeclRefExpr) and child.lvalue.name in self.global_init:
                self.global_init.remove(child.lvalue.name)

            self.visit(child)
        
        newbody = []
        for child in node.body:
            if isinstance(child, BinOp) and child.op == "=" and isinstance(child.lvalue, DeclRefExpr) and child.lvalue.name in self.while_vars:
                self.while_vars[child.lvalue.name] = child
                for i in self.to_init[child.lvalue.name]:
                    if i not in self.global_init:
                        continue

                    newbody.append(BinOp(op="=",
                                         lvalue=DeclRefExpr(name=i),
                                         rvalue=IntLiteral(value="0")))

                continue

            newbody.append(self.visit(child))

        return BasicBlock(body=newbody)

    def visit_WhileStmt(self, node: WhileStmt):
        if len(node.cond) != 1:
            return node

        if not isinstance(node.cond[0], DeclRefExpr):
            return node

        cond_name = node.cond[0].name

        if not isinstance(node.body, list) or len(node.body) != 1:
            return node

        if not isinstance(node.body[0], BasicBlock):
            return node

        incrementer = None
        is_decrementing = True
        new_body = []
        for i in node.body[0].body:
            if not isinstance(i, BinOp) or not isinstance(i.lvalue, DeclRefExpr):
                new_body.append(i)
                continue

            if not isinstance(i.rvalue, BinOp):
                new_body.append(i)
                continue

            var_name = i.lvalue.name
            if var_name != cond_name:
                new_body.append(i)
                continue

            incrementer = i

            if i.rvalue.op == "-":
                is_decrementing = True
            elif i.rvalue.op == "+":
                is_decrementing = False
            else:
                print("WARNING: Unknown operator in while loop")

            if isinstance(i.rvalue.rvalue, DeclRefExpr) and i.rvalue.rvalue.name != cond_name:
                if cond_name not in self.to_init:
                    self.to_init[cond_name] = set()
                self.to_init[cond_name].add(i.rvalue.rvalue.name)
                self.global_init.add(i.rvalue.rvalue.name)

            print("Transforming while loop with incrementer:", var_name)

        if incrementer is None:
            return node

        if is_decrementing:
            new_cond = BinOp(op=">", lvalue=DeclRefExpr(name=cond_name), rvalue=IntLiteral(value="0"))
        else:
            new_cond = BinOp(op="<", lvalue=DeclRefExpr(name=cond_name), rvalue=IntLiteral(value="0"))

        if cond_name not in self.while_vars:
            self.while_vars[cond_name] = None
            init=DeclStmt(vardecl=[VarDecl(name="dummy_var", type=Int(), init=IntLiteral(value="0"))])
        elif self.while_vars[cond_name] is not None:
            init = self.while_vars[cond_name]
        else:
            init=DeclStmt(vardecl=[VarDecl(name="dummy_var", type=Int(), init=IntLiteral(value="0"))])

        return ForStmt(
            init=[init],
            cond=[new_cond],
            iter=[incrementer],
            body=[BasicBlock(body=new_body)],
        )

class CompoundArgumentsExtractor(NodeTransformer):
    def __init__(self):
        self.count = 0

    def compute_patch(self, node: CallExpr):
        if node.name.name in ["malloc", "expf", "powf", "sqrt", "cbrt", "printf"]:
            return []

        inits = []
        for i in range(len(node.args)):
            if not isinstance(node.args[i], UnOp) and not isinstance(node.args[i], BinOp):
                continue

            var_name = "tmp_arg_" + str(self.count)
            self.count += 1

            var = DeclRefExpr(name=var_name, type=node.args[i].type)
            init_var = DeclStmt(vardecl=[VarDecl(name=var_name, type=node.args[i].type, init=node.args[i])])

            node.args[i] = var
            inits.append(init_var)
        
        return inits

    def visit_BasicBlock(self, node: BasicBlock):
        newbody = []
        for child in node.body:
            self.visit(child)
            if isinstance(child, CallExpr):
                newbody += self.compute_patch(child)

            if isinstance(child, BinOp) and isinstance(child.rvalue, CallExpr):
                newbody += self.compute_patch(child.rvalue)

            newbody.append(child)

        return BasicBlock(body=newbody)


class Calloc2Malloc(NodeTransformer):
    def visit_CallExpr(self, node: CallExpr):
        if node.name.name == "calloc":
            node.name = DeclRefExpr(name="malloc")
            node.args[0] = BinOp(op="*", lvalue=copy.deepcopy(node.args[0]), rvalue=copy.deepcopy(node.args[1]))
            del node.args[1]

        return node

class MallocForceInitializer(NodeTransformer):
    def __init__(self):
        self.mallocs = dict()
        self.first_scan = True

    def visit_BasicBlock(self, node: BasicBlock):
        if self.first_scan:
            for child in node.body:
                self.visit(child)
                if isinstance(child, BinOp) and isinstance(child.rvalue, CallExpr) and isinstance(child.rvalue.name, DeclRefExpr) and child.rvalue.name.name == "malloc":
                    tmp = child.lvalue

                    while isinstance(tmp, ParenExpr) or isinstance(tmp, ArraySubscriptExpr):
                        if isinstance(tmp, ParenExpr):
                            tmp = tmp.expr
                        elif isinstance(tmp, ArraySubscriptExpr):
                            tmp = tmp.unprocessed_name

                    if not isinstance(tmp, DeclRefExpr):
                        print("WARNING cannot identify ", tmp)

                    self.mallocs[tmp.name] = child
            
            return node

        else:
            newbody = []
            for child in node.body:
                self.visit(child)
                newbody.append(child)
                if child in self.mallocs.values():
                    newbody.append(
                        BinOp(
                                op="=",
                                lvalue=ArraySubscriptExpr(
                                    name="",
                                    indices="UNDEF",
                                    type=Double(),
                                    unprocessed_name=child.lvalue,
                                    index=IntLiteral(value="0"),
                                ),
                                rvalue=IntLiteral(value="0")
                            )
                    )

            node.body = newbody
            return node
    
    def visit_FuncDecl(self, node: FuncDecl):
        self.mallocs = dict()
        self.first_scan = True

        self.visit(node.body)

        self.first_scan = False
        self.visit(node.body)

        return node

class FindPtrAliases(NodeVisitor):
    def __init__(self, ptr_aliases):
        self.global_aliases = ptr_aliases
        self.ptr_aliases = dict()

    def visit_BinOp(self, node: BinOp):
        if node.op != "=":
            return

        if not isinstance(node.lvalue, DeclRefExpr) or not isinstance(node.rvalue, DeclRefExpr):
            return

        if not isinstance(node.lvalue.type, Pointer) or not isinstance(node.rvalue.type, Pointer):
            return

        if node.lvalue.type != node.rvalue.type:
            return

        self.ptr_aliases[node.lvalue.name] = node.rvalue.name

        return

    def visit_FuncDecl(self, node: FuncDecl):
        self.ptr_aliases = dict()

        self.generic_visit(node)
        self.global_aliases[node.name] = self.ptr_aliases

        return

class FindIgnoreValues(NodeVisitor):
    def __init__(self, ext_calls, ignore_values):
        self.global_ignore = ignore_values
        self.ignore_values = set()
        self.all_values = set()
        self.ext_calls = ext_calls
    
    def visit_DeclRefExpr(self, node: DeclRefExpr):
        self.all_values.add(node.name)
        return

    def visit_BinOp(self, node: BinOp):
        if not isinstance(node.rvalue, CallExpr):
            return self.generic_visit(node)

        if node.rvalue.name.name not in self.ext_calls:
            return self.generic_visit(node)

        return

    def visit_CallExpr(self, node: CallExpr):
        if node.name.name not in self.ext_calls:
            return self.generic_visit(node)

        self.ignore_values |= set([arg.name for arg in filter(lambda x: isinstance(x, DeclRefExpr), node.args)])
        return

    def visit_FuncDecl(self, node: FuncDecl):
        self.ignore_values = set()
        self.all_values = set()

        self.generic_visit(node)
        self.global_ignore[node.name] = self.ignore_values - self.all_values

        return node

class ArrayPointerExtractorNodeLister(NodeVisitor):
    def __init__(self):
        self.nodes: List[DeclRefExpr] = []

    def visit_DeclRefExpr(self, node: DeclRefExpr):
        #if not isinstance(node.index,IntLiteral):
        self.nodes.append(node)
        return self.generic_visit(node)

    def visit_BasicBlock(self, node: BasicBlock):
        return

class ArrayPointerExtractor(NodeTransformer):
    def __init__(self, global_array_map, ext_calls, global_ignore_values):
        self.array_map = dict()
        self.ignore_values = set()
        self.global_array_map = global_array_map
        self.count = 0
        self.ext_calls = ext_calls
        self.global_ignore_values = global_ignore_values

    def pointer_increment(self, node: BinOp):
        name = node.lvalue.name

        if name not in self.array_map:
            #print("Warning undeclared array in ArrayPointerExtractor: " + name)
            return self.generic_visit(node)

        if not isinstance(node.rvalue, BinOp):
            return self.generic_visit(node)

        rval = node.rvalue.rvalue
        lval = node.rvalue.lvalue
        op = node.rvalue.op

        if not isinstance(lval, DeclRefExpr):
            return self.generic_visit(node)

        start_ptr_name = self.array_map[name]
        start_ptr = DeclRefExpr(name=start_ptr_name, type=Int())
        binop = BinOp(op=op, lvalue=copy.deepcopy(start_ptr), rvalue=rval)

        return BinOp(op="=", lvalue=start_ptr, rvalue=binop)

    def pointer_assignment(self, node: BinOp):
        if not hasattr(node.lvalue, "type") or not hasattr(node.rvalue, "type"):
            return self.generic_visit(node)

        ltype = node.lvalue.type
        rtype = node.rvalue.type

        if not isinstance(ltype, Pointer) or ltype != rtype:
            return self.generic_visit(node)

        lval = self.visit(node.lvalue)
        rval = self.visit(node.rvalue)

        start_ptr_name = self.array_map.get(rval.name)
        if start_ptr_name is None:
            #print("Warning undeclared array in ArrayPointerExtractor: " + rval.name + ", ", rval)
            return self.generic_visit(node)

        start_ptr = DeclRefExpr(name=start_ptr_name, type=Int())
        pointer_binop = BinOp(op="+", lvalue=rval, rvalue=start_ptr)
        binop = BinOp(op="=", lvalue=lval, rvalue=pointer_binop)

        return binop
    
    def memcpy_transform(self, node: CallExpr):
        args = node.args
        iterator_name = "memcpy_iterator_" + str(self.count)
        self.count += 1
        lval_ptr = self.array_map.get(args[0].name)
        rval_ptr = self.array_map.get(args[1].name)

        if lval_ptr is None:
            lval_index = DeclRefExpr(name=iterator_name, type=Int())
        else:
            lval_index = BinOp(op="+", lvalue=DeclRefExpr(name=iterator_name, type=Int()), rvalue=DeclRefExpr(name=lval_ptr, type=Int()))

        if rval_ptr is None:
            rval_index = DeclRefExpr(name=iterator_name, type=Int())
        else:
            rval_index = BinOp(op="+", lvalue=DeclRefExpr(name=iterator_name, type=Int()), rvalue=DeclRefExpr(name=rval_ptr, type=Int()))

        lval = ArraySubscriptExpr(
            name=args[0].name,
            indices=None,
            type=args[0].type,
            unprocessed_name=args[0],
            index=lval_index
        )

        rval = ArraySubscriptExpr(
            name=args[1].name,
            indices=None,
            type=args[1].type,
            unprocessed_name=args[1],
            index=rval_index
        )

        body = [BinOp(op="=", lvalue=lval, rvalue=rval)]
        body = [BasicBlock(body=body)]
        incr = [BinOp(op="=", lvalue=DeclRefExpr(name=iterator_name, type=Int()), rvalue=BinOp(op="+", lvalue=DeclRefExpr(name=iterator_name, type=Int()), rvalue=IntLiteral(value="1")))]
        cond = [BinOp(op="<", lvalue=DeclRefExpr(name=iterator_name, type=Int()), rvalue=args[2])]
        init = [DeclStmt(vardecl=[VarDecl(name=iterator_name, type=Int(), init=IntLiteral(value="0"))])]

        return ForStmt(init=init, cond=cond, body=body, iter=incr)

    def visit_ArraySubscriptExpr(self, node: ArraySubscriptExpr):
        if isinstance(node.unprocessed_name, ParenExpr):
            node.unprocessed_name = node.unprocessed_name.expr
            return self.visit(node)

        if isinstance(node.unprocessed_name, CCastExpr):
            node.unprocessed_name = node.unprocessed_name.expr
            return self.visit(node)

        if isinstance(node.unprocessed_name, ArraySubscriptExpr):
            return ArraySubscriptExpr(
                name=node.name,
                indices=node.indices,
                type=node.type,
                unprocessed_name=self.visit(node.unprocessed_name),
                index=node.index)

        name = node.unprocessed_name.name

        ptr_name = self.array_map.get(name)
        if ptr_name is None:
            #print("Warning undeclared array in ArrayPointerExtractor: " + node.name)
            return node

        ptr_index = DeclRefExpr(name=ptr_name, type=Int())
        binop = BinOp(op="+", lvalue=node.index, rvalue=ptr_index)
        return ArraySubscriptExpr(
            name=node.name,
            indices=node.indices,
            type=node.type,
            unprocessed_name=self.visit(node.unprocessed_name),
            index=binop)

    def pointer_diff(self, node: BinOp):
        ptr_binop = node.rvalue
        if not hasattr(ptr_binop.lvalue, "type") or not hasattr(ptr_binop.rvalue, "type"):
            return None

        if not isinstance(ptr_binop.lvalue, DeclRefExpr) or not isinstance(ptr_binop.rvalue, DeclRefExpr):
            return None

        if not isinstance(ptr_binop.lvalue.type, Pointer) or not isinstance(ptr_binop.rvalue.type, Pointer):
            return None

        op1_name = self.array_map.get(ptr_binop.lvalue.name)
        op2_name = self.array_map.get(ptr_binop.rvalue.name)
        if op1_name is None or op2_name is None:
            return None

        print("twin transform for binop on", node.lvalue.name)
        op1 = DeclRefExpr(name=op1_name, type=Int())
        op2 = DeclRefExpr(name=op2_name, type=Int())
        binop = BinOp(op=ptr_binop.op, lvalue=op1, rvalue=op2) 
        lval = self.visit(node.lvalue)
        return BinOp(op="=", lvalue=lval, rvalue=binop)

    def visit_BinOp(self, node: BinOp):
        if node.op != "=" :
            return self.generic_visit(node)

        lval = node.lvalue
        while isinstance(lval, ParenExpr):
            lval = lval.expr

        node.lvalue = lval

        if isinstance(node.rvalue, BinOp):
            # a = b - c
            res = self.pointer_diff(node)
            if res is not None:
                return res

        # a[i] = something
        if isinstance(lval, ArraySubscriptExpr):
            return self.pointer_assignment(node)

        # unknown lvalue
        if not isinstance(lval, DeclRefExpr):
            return self.generic_visit(node)

        # a = b
        if isinstance(node.rvalue, DeclRefExpr):
            return self.pointer_assignment(node)

        return self.pointer_increment(node)

    def visit_CallExpr(self, node: CallExpr):
        if node.name.name == "memcpy":
            return self.memcpy_transform(node)

        if node.name.name not in self.ext_calls:
            return self.generic_visit(node)

        args = node.args
        in_out = self.ext_calls[node.name.name]

        for i in range(len(in_out)):
            if not isinstance(args[i], DeclRefExpr):
                self.generic_visit(args[i])
                continue

            arg_name = args[i].name

            if not arg_name in self.array_map:
                self.generic_visit(args[i])
                continue

            ptr_name = self.array_map[arg_name]
            new_arg = ArraySubscriptExpr(
                    name=args[i].name,
                    indices=None,
                    type=args[i].type,
                    unprocessed_name=args[i],
                    index=DeclRefExpr(name=ptr_name, type=Int()))
            args[i] = UnOp(op="&", lvalue=new_arg, postfix=False, name=args[i].name)

        node.args = args
        return node

    def visit_BasicBlock(self, node: BasicBlock):
        newbody = []

        for child in node.body:
            newbody.append(self.visit(child))
            if isinstance(child, BinOp) and child.op == "=" and isinstance(child.lvalue, DeclRefExpr) and isinstance(child.rvalue, DeclRefExpr):
                # a = b
                lname = self.array_map.get(child.lvalue.name)
                rname = self.array_map.get(child.rvalue.name)
                if lname and rname:
                    twin_assign = BinOp(op="=", lvalue=DeclRefExpr(name=lname, type=Int()), rvalue=DeclRefExpr(name=rname, type=Int()))
                    newbody.append(twin_assign)
                    continue

            if not isinstance(child, DeclStmt) or len(child.vardecl) != 1:
                continue
                
            vardecl = child.vardecl[0]

            if not isinstance(vardecl.type, Pointer):
                continue

            if vardecl.name in self.ignore_values:
                continue

            varname = "tmp_array_ptr_" + vardecl.name + "_" + str(self.count)

            print("Splitting pointer " + vardecl.name + " into " + varname)
            self.array_map[vardecl.name] = varname
            self.count += 1
            newbody.append(VarDecl(name=self.array_map[vardecl.name], type=Int(), init=IntLiteral(value="0")))

        return BasicBlock(body=newbody)

    def visit_FuncDecl(self, node: FuncDecl):
        self.array_map = dict()
        self.ignore_values = self.global_ignore_values[node.name]

        self.generic_visit(node)
        self.global_array_map[node.name] = self.array_map

        return node


class ArrayPointerReset(NodeTransformer):
    def __init__(self, global_array_map):
        self.array_map = dict()
        self.global_array_map = global_array_map

    def reset_pointer(self, node):
        if not isinstance(node, BinOp):
            return []
        
        if not isinstance(node.lvalue, DeclRefExpr):
            return []
        
        ptr_name = self.array_map.get(node.lvalue.name)
        if ptr_name is None:
            return []
        
        return [BinOp(op="=", lvalue=DeclRefExpr(name=ptr_name, type=Int()), rvalue=IntLiteral(value="0"))]

    def visit_BasicBlock(self, node: BasicBlock):
        newbody = []

        for child in node.body:
            newbody.append(child)
            newbody += self.reset_pointer(child)
        
        return BasicBlock(body=newbody)

    def visit_FuncDecl(self, node: FuncDecl):
        self.array_map = self.global_array_map.get(node.name, dict())
        self.generic_visit(node)

        return node

class LILSimplifier(NodeTransformer):
    def __init__(self):
        self.matched = dict()
        self.ptr_names = dict()
        self.applied_transform = dict()
        self.apply_transformation = False

    def BasicBlock_visit_only(self, node: BasicBlock):
        previous_match = -1
        previous_child = None
        previous_varname = None
        previous_arr = None

        for i, child in enumerate(node.body):
            self.visit(child)
            if not isinstance(child, BinOp):
                continue

            rval = child.rvalue
            while isinstance(rval, ParenExpr):
                rval = rval.expr

            if not isinstance(rval, DeclRefExpr) or not isinstance(rval.type, Pointer):
                continue

            lval = child.lvalue
            while isinstance(lval, ParenExpr):
                lval = lval.expr

            if not isinstance(lval, ArraySubscriptExpr) or not isinstance(lval.type, Pointer):
                continue

            arr_node = lval.unprocessed_name

            while isinstance(arr_node, ParenExpr):
                arr_node = arr_node.expr

            if not isinstance(arr_node, DeclRefExpr) or not arr_node.name.startswith("c2d_struct"):
                continue

            struct_str_position = arr_node.name.find("___")
            if previous_match == i-1 and arr_node.name[:struct_str_position] == previous_arr_name[:struct_str_position]:
                self.ptr_names[previous_varname] = child.lineno
                self.ptr_names[rval.name] = child.lineno
                self.matched[child.lineno] = (
                    node,
                    child,
                    previous_child,
                    {
                        rval.name: lval,
                        previous_varname: previous_arr,
                    },
                )
                self.applied_transform[child.lineno] = False

            previous_match = i
            previous_child = child
            previous_varname = rval.name
            previous_arr_name = arr_node.name
            previous_arr = lval
        
        return node

    def BasicBlock_transform(self, node: BasicBlock):
        new_body = []
        for child in node.body:
            self.visit(child)

            if isinstance(child, DeclStmt):
                found = False
                for i in child.vardecl:
                    if isinstance(i.type, Pointer) and i.name in self.ptr_names:
                        print("throwing ", i.name)
                        found = True
                        break

                if found:
                    continue

            if not isinstance(child, BinOp):
                new_body.append(child)
                continue

            if isinstance(child.lvalue, UnOp) and isinstance(child.lvalue.lvalue, DeclRefExpr) and child.lvalue.lvalue.name in self.ptr_names:
                lineno = self.ptr_names[child.lvalue.lvalue.name]
                if not self.applied_transform[lineno]:
                    print("WARNING applying transformation for LIL sparse matrix. If your code doesn't have a LIL sparse matrix this is wrong.")
                    print("Init at line ", lineno)
                self.applied_transform[lineno] = True

                print("Set value at ", child.lineno)

                (_, _, _, array_mapping) = self.matched[lineno]
                cur_name = list(array_mapping.keys())[0] + "_offset"
                arr = array_mapping[child.lvalue.lvalue.name]
                binop = BinOp(
                    op=child.op,
                    lvalue=ArraySubscriptExpr(
                        name="",
                        indices="UNDEF",
                        unprocessed_name=copy.deepcopy(arr),
                        index=DeclRefExpr(name=cur_name, type=Int()),
                        type=arr.type.pointee_type
                    ),
                    rvalue=child.rvalue
                )
                new_body.append(binop)

                if cur_name == child.lvalue.lvalue.name + "_offset":
                    increment = UnOp(
                        op=child.lvalue.op,
                        postfix=True,
                        lvalue=DeclRefExpr(name=cur_name, type=Int()),
                    )

                    new_body.append(increment)

            else:
                new_body.append(child)

        node.body = new_body

        return node

    def visit_BasicBlock(self, node: BasicBlock):
        if not self.apply_transformation:
            return self.BasicBlock_visit_only(node)
        else:
            return self.BasicBlock_transform(node)

    def visit_AST(self, node: AST):
        self.generic_visit(node)
        self.apply_transformation = True
        self.generic_visit(node)

        for lineno, applied in self.applied_transform.items():
            if not applied:
                continue

            (body, child1, child2, arr_names) = self.matched[lineno]
            child1.rvalue = CallExpr(name=DeclRefExpr(name="malloc"), args=[IntLiteral(value="1")])
            child2.rvalue = CallExpr(name=DeclRefExpr(name="malloc"), args=[IntLiteral(value="1")])

            new_body = []
            for child in body.body:
                if child != child2:
                    new_body.append(child)
                    continue

                offset_name = list(arr_names.keys())[0] + "_offset"
                new_body.append(VarDecl(name=offset_name, type=Int(), init=IntLiteral(value="0")))
                new_body.append(child)
            
            body.body = new_body

        return node

class InitExtractorNodeLister(NodeVisitor):
    def __init__(self):
        self.nodes: List[VarDecl] = []

    def visit_ForStmt(self, node: ForStmt):
        return

    def visit_VarDecl(self, node: VarDecl):
        if hasattr(node, "init"):
            self.nodes.append(node)
        return self.generic_visit(node)

    def visit_BasicBlock(self, node: BasicBlock):
        return


class InsertMissingBasicBlocks(NodeTransformer):
    def insert_missing_block(self, body):
        assert isinstance(body, list)
        if isinstance(body[0], BasicBlock):
            return body
        return [BasicBlock(body=body)]

    def visit_ForStmt(self, node: ForStmt):
        node.body = self.insert_missing_block(node.body)
        return self.generic_visit(node)

    def visit_DoStmt(self, node: DoStmt):
        node.body = self.insert_missing_block(node.body)
        return self.generic_visit(node)

    def visit_WhileStmt(self, node: WhileStmt):
        node.body = self.insert_missing_block(node.body)
        return self.generic_visit(node)

    def visit_IfStmt(self, node: IfStmt):
        node.body_if = self.insert_missing_block(node.body_if)
        if hasattr(node, "body_else"):
            node.body_else = self.insert_missing_block(node.body_else)
        return self.generic_visit(node)


class InitExtractor(NodeTransformer):
    def __init__(self, count=0):
        self.count = count

    def visit_BasicBlock(self, node: BasicBlock):
        newbody = []

        for child in node.body:
            # res = [node for node in Node.walk(child) if isinstance(node, ArraySubscriptExpr)]
            lister = InitExtractorNodeLister()
            lister.visit(child)
            res = lister.nodes
            temp = self.count
            newbody.append(self.visit(child))
            if res is None:
                continue

            for i in res:
                '''
                # check if the init is malloc
                if isinstance(i.init, CallExpr) and isinstance(i.init.name, DeclRefExpr) and i.init.name.name != "malloc":
                    # add also an init with a concrete value s.t. the transient is always initialized
                    newbody.append(
                        BinOp(op="=",
                                lvalue=DeclRefExpr(name=i.name),
                                rvalue=IntLiteral(value="0")))
                '''
                if isinstance(i.type, Pointer) and isinstance(i.type.pointee_type, Struct):
                    # only structs left are the external ones, no need to to init extraction
                    continue

                if isinstance(i.type, Pointer) and isinstance(i.type.pointee_type, Opaque):
                    # external types
                    continue

                newbody.append(
                    BinOp(op="=",
                            lvalue=DeclRefExpr(name=i.name),
                            rvalue=i.init))

        return BasicBlock(body=newbody)


class CallExtractorNodeLister(NodeVisitor):
    def __init__(self, ext_functions):
        self.nodes: List[CallExpr] = []
        self.ext_functions = ext_functions

    def visit_ForStmt(self, node: ForStmt):
        return

    def visit_CallExpr(self, node: CallExpr):
        if node.name.name in ["malloc", "expf", "powf", "sqrt", "cbrt"]:
            return self.generic_visit(node)

        if node.name.name in self.ext_functions:
            return self.generic_visit(node)

        self.nodes.append(node)

    def visit_BasicBlock(self, node: BasicBlock):
        return


class CallExtractor(NodeTransformer):
    def __init__(self, ext_functions, count=0):
        self.ext_functions = ext_functions
        self.count = count

    def visit_CallExpr(self, node: CallExpr):

        #if isinstance(node.index,IntLiteral):
        #    return node
        if not hasattr(self, "count"):
            self.count = 0
        else:
            self.count = self.count + 1
        tmp = self.count
        if node.name.name in ["malloc", "expf", "powf", "sqrt", "cbrt"] or node.name.name in self.ext_functions:
            return node
        return DeclRefExpr(name="tmp_call_" + str(tmp - 1))

    def visit_BasicBlock(self, node: BasicBlock):
        newbody = []

        for child in node.body:
            # res = [node for node in Node.walk(child) if isinstance(node, ArraySubscriptExpr)]
            lister = CallExtractorNodeLister(self.ext_functions)
            lister.visit(child)
            res = lister.nodes
            for i in res:
                if i == child:
                    res.pop(res.index(i))
            temp = self.count
            if res is not None:
                for i in range(0, len(res)):
                    newbody.append(
                        DeclStmt(vardecl=[
                            VarDecl(name="tmp_call_" + str(temp),
                                    type=res[i].type)
                        ]))
                    newbody.append(
                        BinOp(op="=",
                              lvalue=DeclRefExpr(name="tmp_call_" + str(temp),
                                                 type=res[i].type),
                              rvalue=res[i]))
            if isinstance(child, CallExpr):
                new_args = []
                for i in child.args:
                    new_args.append(self.visit(i))
                new_child = CallExpr(type=child.type,
                                     name=child.name,
                                     args=new_args)
                newbody.append(new_child)
            else:
                newbody.append(self.visit(child))

        return BasicBlock(body=newbody)


class AddNewInitCalls(NodeTransformer):
    def __init__(self, ext_functions, init_functions):
        self.ext_functions = ext_functions
        self.init_functions = init_functions
        self.call_types = dict()

    def visit_FuncDecl(self, node: FuncDecl):
        self.call_types = dict()
        return self.generic_visit(node)

    def visit_BasicBlock(self, node: BasicBlock):
        new_body = []
        
        for child in node.body:
            if isinstance(child, BinOp) and child.op == "=" and isinstance(child.rvalue, CallExpr):
                func_name = child.rvalue.name.name
                self.call_types[func_name] = child.rvalue.type
                if func_name in self.init_functions.values():
                    continue 
            elif isinstance(child, CallExpr) and child.name.name in self.ext_functions:
                for i, arg in enumerate(self.ext_functions[child.name.name]):
                    if "new" not in arg or not isinstance(child.args[i], DeclRefExpr):
                        continue

                    call_type = self.call_types.get(self.init_functions[child.name.name])

                    if call_type is None:
                        raise Exception(child.name.name, "was never called")

                    arg_name = child.args[i].name
                    new_body.append(BinOp(
                        op="=",
                        lvalue=DeclRefExpr(name=arg_name),
                        rvalue=CallExpr(
                            name=DeclRefExpr(name=self.init_functions[child.name.name]),
                            args=[],
                            type = call_type,
                        )
                    ))

            new_body.append(self.visit(child))

        return BasicBlock(body=new_body)


class PowerOptimization(NodeTransformer):
    def visit_CallExpr(self, node: CallExpr):
        if node.name.name != "pow":
            return node

        if len(node.args) != 2:
            return node

        if not isinstance(node.args[1], IntLiteral):
            return node

        value = node.args[1].value[0]

        if value != '2':
            return node

        lnode = copy.deepcopy(node.args[0])
        rnode = copy.deepcopy(node.args[0])

        return BinOp(op="*", lvalue=lnode, rvalue=rnode)


class CondExtractorNodeLister(NodeVisitor):
    def __init__(self):
        self.nodes: List[Node] = []

    def visit_ForStmt(self, node: ForStmt):
        return

    def visit_IfStmt(self, node: IfStmt):
        self.nodes.append(node.cond[0])

    def visit_WhileStmt(self, node: WhileStmt):
        #self.nodes.append(node.cond[0])
        return

    def visit_BasicBlock(self, node: BasicBlock):
        return


class CondExtractor(NodeTransformer):
    def __init__(self, count=0):
        self.count = count

    def visit_IfStmt(self, node: IfStmt):

        if not hasattr(self, "count"):
            self.count = 0
        else:
            self.count = self.count + 1
        tmp = self.count

        #cond = [
        #    BinOp(op="!=",
        #          lvalue=DeclRefExpr(name="tmp_if_" + str(tmp - 1)),
        #          rvalue=IntLiteral(value="0"))
        #]
        cond = [DeclRefExpr(name="tmp_if_" + str(tmp - 1))]
        body_if = [self.visit(node.body_if[0])]
        if hasattr(node, "body_else"):
            body_else = [self.visit(node.body_else[0])]
            return IfStmt(cond=cond, body_if=body_if, body_else=body_else)
        else:
            return IfStmt(cond=cond, body_if=body_if)

    #def visit_WhileStmt(self, node: WhileStmt):
    #    if not hasattr(self, "count"):
    #        self.count = 0
    #    else:
    #        self.count = self.count + 1
    #    tmp = self.count

    #    cond = [DeclRefExpr(name="tmp_if_" + str(tmp - 1))]
    #    body = [self.visit(node.body[0])]
    #    return WhileStmt(cond=cond, body=body)

    def visit_BasicBlock(self, node: BasicBlock):
        newbody = []

        for child in node.body:
            lister = CondExtractorNodeLister()
            lister.visit(child)
            res = lister.nodes
            temp = self.count
            if res is not None:
                for i in range(0, len(res)):
                    newbody.append(
                        DeclStmt(vardecl=[
                            VarDecl(name="tmp_if_" + str(temp), type=Int())
                        ]))
                    newbody.append(
                        BinOp(op="=",
                              lvalue=DeclRefExpr(name="tmp_if_" + str(temp)),
                              rvalue=res[i]))
                    #if isinstance(child, WhileStmt):
                    #    child.body[0].body.append(
                    #    BinOp(op="=",
                    #          lvalue=DeclRefExpr(name="tmp_if_" + str(temp)),
                    #          rvalue=res[i]))
            newbody.append(self.visit(child))

        return BasicBlock(body=newbody)


class ForDeclarerNodeLister(NodeVisitor):
    def __init__(self):
        self.nodes: List[Node] = []

    def visit_ForStmt(self, node: ForStmt):
        if isinstance(node.init[0], BinOp):# for(int i=0;) for (i=0;)
            self.nodes.append(node.init[0])

    def visit_BasicBlock(self, node: BasicBlock):
        return


class ForDeclarer(NodeTransformer):
    def __init__(self):
        self.count = 0
        self.name_mapping = {}

    def visit_BasicBlock(self, node: BasicBlock):
        # make sure name mapping gets reverted properly when exiting contexts
        prev = self.name_mapping.copy()
        newbody = []
        for child in node.body:
            lister = ForDeclarerNodeLister()
            lister.visit(child)
            res = lister.nodes
            if res is not None:
                for i in range(0, len(res)):
                    #print("FOREXTRABINOP")
                    newbody.append(res[i])
            newbody.append(self.visit(child))
        self.name_mapping = prev
        return BasicBlock(body=newbody)

    def visit_DeclRefExpr(self, node: DeclRefExpr):
        if self.name_mapping.get(node.name) is None:
            return node
        else:
            return DeclRefExpr(name=self.name_mapping[node.name])

    def visit_ForStmt(self, node: ForStmt):
        if isinstance(node.body, list):
            node.body = node.body[0]
        if isinstance(node.init[0], BinOp):
            self.count = self.count + 1
            assert isinstance(
                node.init[0].lvalue,
                DeclRefExpr), "expecting lvalue of binop to be a declRefExpr"

            self.name_mapping[node.init[0].lvalue.name] = "tmp_for_" + str(
                self.count)
            return ForStmt(init=[
                DeclStmt(vardecl=[
                    VarDecl(name="tmp_for_" + str(self.count),
                            type=Int(),
                            init=node.init[0].rvalue)
                ])
            ],
                           cond=[self.generic_visit(node.cond[0])],
                           body=[self.generic_visit(node.body)],
                           iter=[self.generic_visit(node.iter[0])])
        elif isinstance(node.init[0], DeclStmt):
            return self.generic_visit(node)


class UnaryToBinary(NodeTransformer):
    def visit_UnOp(self, node: UnOp):
        if node.op == "++":
            return BinOp(op="=",
                         lvalue=node.lvalue,
                         rvalue=BinOp(op="+",
                                      lvalue=node.lvalue,
                                      rvalue=IntLiteral(value="1")))
        elif node.op == "--":
            return BinOp(op="=",
                         lvalue=node.lvalue,
                         rvalue=BinOp(op="-",
                                      lvalue=node.lvalue,
                                      rvalue=IntLiteral(value="1")))
        else:
            return self.generic_visit(node)


class CompoundToBinary(NodeTransformer):
    def visit_CompoundAssignOp(self, node: CompoundAssignOp):
        newop = (node.op).replace("=", "")
        return BinOp(op="=",
                     lvalue=node.lvalue,
                     rvalue=BinOp(op=newop,
                                  lvalue=node.lvalue,
                                  rvalue=node.rvalue))


class UnaryReferenceAndPointerRemover(NodeTransformer):
    def visit_ParenExpr(self, node: ParenExpr):
        # check for unpacked structs that we are dereferencing
        if not isinstance(node.expr, UnOp):
            return self.generic_visit(node)

        if not isinstance(node.expr.lvalue, list):
            return self.generic_visit(node)
        
        return list(map(lambda x: ParenExpr(expr=self.generic_visit(x), type=x.type), node.expr.lvalue))

    def visit_UnOp(self, node: UnOp):
        if node.op == "*" or node.op == "&":
            return self.generic_visit(node.lvalue)
        else:
            return self.generic_visit(node)


class FindOutputNodesVisitor(NodeVisitor):
    def __init__(self):
        self.nodes: List[DeclRefExpr] = []

    def visit_ParenExpr(self, node: ParenExpr):
        self.visit(node.expr)

    def visit_DeclRefExpr(self, node: DeclRefExpr):
        self.nodes.append(node)

    def visit_UnOp(self, node: UnOp):
        if node.op == "*":
            self.visit(node.lvalue)

    def visit_ArraySubscriptExpr(self, node: ArraySubscriptExpr):
        self.visit(node.unprocessed_name)

    def visit_BinOp(self, node: BinOp):
        if node.op == "=":
            self.visit(node.lvalue)
            if isinstance(node.rvalue, BinOp):
                self.visit(node.rvalue)

    #def visit_TernaryExpr(self, node: TernaryExpr):
    #    used_vars_condition = [node for node in walk(node.cond) if isinstance(node, DeclRefExpr)]
    #    used_vars_left = [node for node in walk(node.left) if isinstance(node, DeclRefExpr)]
    #    used_vars_right = [node for node in walk(node.right) if isinstance(node, DeclRefExpr)]
    #    self.nodes = self.nodes + used_vars_condition


class FindInputNodesVisitor(NodeVisitor):
    def __init__(self):
        self.nodes: List[DeclRefExpr] = []

    def visit_ParenExpr(self, node: ParenExpr):
        self.visit(node.expr)

    def visit_DeclRefExpr(self, node: DeclRefExpr):
        self.nodes.append(node)

    def visit_BinOp(self, node: BinOp):
        if node.op == "=":
            if isinstance(node.lvalue, DeclRefExpr):
                pass
            if isinstance(node.lvalue, ArraySubscriptExpr):
                tmp = node.lvalue
                while isinstance(tmp, ArraySubscriptExpr):
                    self.visit(tmp.index)
                    tmp = tmp.unprocessed_name
                if isinstance(tmp, DeclRefExpr):
                    pass
        else:
            self.visit(node.lvalue)
        self.visit(node.rvalue)


class FunctionLister(NodeVisitor):
    def __init__(self) -> None:
        self.function_names: Set[str] = set()
        self.defined_function_names: Set[str] = set()
        self.undefined_function_names: Set[str] = set()
        self.function_is_void: Set[str] = set()

    def visit_AST(self, node: AST):
        self.generic_visit(node)
        self.undefined_function_names = self.function_names.difference(
            self.defined_function_names)

    def visit_FuncDecl(self, node: FuncDecl):
        self.function_names.add(node.name)

        if node.body is not None and node.body != []:
            self.defined_function_names.add(node.name)

        if isinstance(node.result_type, Void):
            self.function_is_void.add(node.name)

    def is_defined(self, function_name: str) -> bool:
        return function_name in self.defined_function_names

    def is_declared(self, function_name: str) -> bool:
        return function_name in self.function_names

    def is_void(self, function_name: str) -> bool:
        return function_name in self.function_is_void


class MoveReturnValueToArguments(NodeTransformer):
    """
    expects: no class method calls
    """
    def visit_AST(self, node: AST) -> None:
        self.function_lister = FunctionLister()
        self.function_lister.visit(node)
        return self.generic_visit(node)

    def visit_FuncDecl(self, node: FuncDecl):
        if self.function_lister.is_defined(node.name):
            if not isinstance(node.result_type, Void):
                #node.args.append(ParmDecl(name = "c2d_retval", type = Pointer(pointee_type = node.result_type), lineno = node.lineno))
                node.args.append(
                    ParmDecl(name="c2d_retval",
                             type=node.result_type,
                             lineno=node.lineno))
                node.result_type = Void()

        return self.generic_visit(node)

    def visit_CallExpr(self, node: CallExpr):
        if self.function_lister.is_defined(node.name.name):
            if not self.function_lister.is_void(node.name.name):
                node.args.append(
                    DeclRefExpr(name="NULL",
                                type=Pointer(pointee_type=Void())))
                node.type = Void()

        return self.generic_visit(node)

    def visit_BinOp(self, node: BinOp):
        if isinstance(node.rvalue, CallExpr):
            if self.function_lister.is_defined(node.rvalue.name.name):
                #reference = UnOp(lvalue = node.lvalue, op = "&", postfix = False, type = Pointer(pointee_type = node.lvalue.type))
                reference = node.lvalue
                node.rvalue.args.append(reference)
                return self.generic_visit(node.rvalue)

        return self.generic_visit(node)

    def visit_RetStmt(self, node: RetStmt):
        if hasattr(node, "ret_expr"):
            return_type = node.ret_expr.type
            #left = UnOp(op = "*", postfix = False, type = Pointer(pointee_type = return_type),
            #            lvalue = DeclRefExpr(name = "c2d_retval", type = return_type))
            # TODO: implement using pointers
            left = DeclRefExpr(name="c2d_retval", type=return_type)
            assignment = BinOp(op="=",
                               lvalue=left,
                               rvalue=node.ret_expr,
                               type=return_type)
            return [assignment, RetStmt()]

        return self.generic_visit(node)


class FlattenStructs(NodeTransformer):
    def __init__(self) -> None:
        self.structdefs: Dict[str, StructDecl] = {}

    def struct_is_defined(self, struct_name):
        return struct_name in self.structdefs.keys()

    def visit_AST(self, node: AST):
        self.structdefs = {sd.name: sd for sd in node.structdefs}
        return self.generic_visit(node)

    def visit_StructDecl(self, node: StructDecl):
        replacement_fields = []
        for field in node.fields:
            if field.type.is_struct_like():
                nested_struct_name = field.type.get_chain_end().name
                if self.struct_is_defined(nested_struct_name):
                    nested_struct_fields = self.structdefs[
                        nested_struct_name].fields

                    for nested_field in nested_struct_fields:
                        replacement_fields.append(
                            FieldDecl(name=field.name + "_" +
                                      nested_field.name,
                                      type=field.type.inject_type(
                                          nested_field.type)))
                else:
                    replacement_fields.append(field)

            else:
                replacement_fields.append(field)

        return StructDecl(name=node.name, fields=replacement_fields)


class ReplaceStructDeclStatements(NodeTransformer):
    def __init__(self):
        self.structdefs: Dict[str, StructDecl] = {}

    def struct_is_defined(self, struct_name):
        return struct_name in self.structdefs.keys()

    def get_struct(self, struct_name: str):
        return self.structdefs.get(struct_name)

    def get_field_replacement_name(self, struct_type_name: str,
                                   struct_variable_name: str, field_name: str):
        return "c2d_struct_" + struct_type_name + "_" + struct_variable_name + "___" + field_name

    def split_struct_type(self, struct_like_type,
                          var_name) -> Dict[str, Tuple[str, Type]]:
        if isinstance(struct_like_type, Struct):
            if not self.struct_is_defined(struct_like_type.name):
                return None
            defined_struct = self.get_struct(struct_like_type.name)
            return {
                field.name:
                (self.get_field_replacement_name(defined_struct.name, var_name,
                                                 field.name), field.type)
                for field in defined_struct.fields
            }

        if isinstance(struct_like_type, ConstantArray):
            splits = self.split_struct_type(struct_like_type.element_type,
                                            var_name)
            if splits is not None:
                return {
                    field_name: (split_name + "_arr",
                                 ConstantArray(size=struct_like_type.size,
                                               element_type=split_type))
                    for (field_name, (split_name,
                                      split_type)) in splits.items()
                }
            else:
                return None

        if isinstance(struct_like_type, Pointer):
            splits = self.split_struct_type(struct_like_type.pointee_type,
                                            var_name)
            if splits is not None:
                return {
                    field_name:
                    (split_name + "_ptr", Pointer(pointee_type=split_type))
                    for (field_name, (split_name,
                                      split_type)) in splits.items()
                }
            else:
                return None

        raise Exception("split_struct_type expects struct like type")

    def replace_container_expr(self, container_expr: Expression,
                               desired_field: str):
        if isinstance(container_expr, DeclRefExpr):
            replacement_name, replacement_type = self.split_struct_type(
                container_expr.type, container_expr.name)[desired_field]

            if isinstance(replacement_type, Pointer):
                # need to wrap in ParenExpr when deallocating pointer
                return ParenExpr(
                        expr=UnOp(
                            op="*",
                            postfix=False,
                            type=replacement_type,
                            lvalue=DeclRefExpr(name=replacement_name, type=replacement_type)
                        ),
                        type=replacement_type
                    )

            return DeclRefExpr(name=replacement_name, type=replacement_type)
        if isinstance(container_expr, ArraySubscriptExpr):
            replacement = copy.deepcopy(container_expr)
            replacement.unprocessed_name = self.replace_container_expr(
                container_expr.unprocessed_name, desired_field)
            if isinstance(replacement.unprocessed_name.type, Array):
                replacement.type = replacement.unprocessed_name.type.element_type
            elif isinstance(replacement.unprocessed_name.type, Pointer):
                replacement.type = replacement.unprocessed_name.type.pointee_type
            else:
                print("unsupported type in array subscript expr ", replacement.unprocessed_name.type)
                raise

            return replacement
        if isinstance(container_expr, MemberRefExpr):
            replacement = copy.deepcopy(container_expr)
            replacement.name += "_" + desired_field
            return self.visit(replacement)
        if isinstance(container_expr, UnOp):
            replacement = copy.deepcopy(container_expr)
            replacement.lvalue = self.replace_container_expr(
                container_expr.lvalue, desired_field)
            replacement.type = container_expr.type.inject_type(
                replacement.lvalue.type)
            return replacement
        if isinstance(container_expr, ParenExpr):
            expr = copy.deepcopy(container_expr.expr)
            out_expr = self.replace_container_expr(expr, desired_field)
            return out_expr

        raise Exception("cannot replace container expression: ",
                        container_expr, " at line ", container_expr.lineno)

    def visit_AST(self, node: AST):
        self.structdefs = {sd.name: sd for sd in node.structdefs}
        return self.generic_visit(node)

    def visit_DeclRefExpr(self, node: DeclRefExpr):
        if hasattr(node, "type") and node.type.is_struct_like():
            splits = self.split_struct_type(node.type, node.name)
            if splits is not None:
                return [
                    DeclRefExpr(name=n, type=t) for (n, t) in splits.values()
                ]

        return self.generic_visit(node)

    def visit_BinOp(self, node: BinOp):
        if hasattr(node.lvalue, "type") and hasattr(node.rvalue, "type"):
            if node.lvalue.type.is_struct_like():
                struct = node.lvalue.type.get_chain_end()
                if self.get_struct(struct.name) is None:
                    return self.generic_visit(node)

                if node.lvalue.type == node.rvalue.type:
                    # assign a struct to another

                    if node.op == "=":
                        replacement_statements = []

                        fields = self.get_struct(struct.name).fields
                        if fields is not None:
                            for f in fields:
                                l_member_ref = MemberRefExpr(
                                    name=f.name,
                                    type=node.lvalue.type.inject_type(f.type),
                                    containerexpr=node.lvalue)
                                r_member_ref = MemberRefExpr(
                                    name=f.name,
                                    type=node.rvalue.type.inject_type(f.type),
                                    containerexpr=node.rvalue)
                                binop = BinOp(op="=",
                                              type=f.type,
                                              lvalue=l_member_ref,
                                              rvalue=r_member_ref)
                                replacement_statements.append(binop)
                            return [
                                self.visit(s) for s in replacement_statements
                            ]
                elif isinstance(node.rvalue, CallExpr) and node.rvalue.name.name == "malloc":
                    # call malloc on every field
                    mallocCall = CallExpr(
                            type=Pointer(pointee_type=Void()),
                            args=[IntLiteral(value="1")],
                            name=DeclRefExpr(name="malloc", type=Pointer(pointee_type=Void()))
                        )

                    struct = node.lvalue.type.get_chain_end()

                    if node.op == "=":
                        replacement_statements = []

                        fields = self.get_struct(struct.name).fields
                        if fields is not None:
                            for f in fields:
                                l_member_ref = MemberRefExpr(
                                    name=f.name,
                                    type=node.lvalue.type.inject_type(f.type),
                                    containerexpr=node.lvalue)
                                binop = BinOp(op="=",
                                              type=f.type,
                                              lvalue=l_member_ref,
                                              rvalue=copy.deepcopy(mallocCall))
                                replacement_statements.append(binop)
                            return [
                                self.visit(s) for s in replacement_statements
                            ]
                    return []

        return self.generic_visit(node)

    def visit_VarDecl(self, node: VarDecl):
        # only process structs
        if not node.type.is_struct_like():
            return self.generic_visit(node)

        # only valid and defined structs
        splits = self.split_struct_type(node.type, node.name)
        if splits is None:
            return self.generic_visit(node)

        if not hasattr(node, "init"):
            return self.generic_visit(node)

        # null initialization to pointer
        if isinstance(node.init, IntLiteral) and node.init.value == ['0']:
            return [VarDecl(name=n, type=t, init=IntLiteral(value="0")) for (n, t) in splits.values()]

        # check if the struct is initialized as malloc
        if not isinstance(node.init, CallExpr):
            return [VarDecl(name=n, type=t) for (n, t) in splits.values()]

        if node.init.name.name != "malloc":
            return [VarDecl(name=n, type=t) for (n, t) in splits.values()]

        mallocCall =CallExpr(
                type=Pointer(pointee_type=Void()),
                args=node.init.args,
                name=DeclRefExpr(name="malloc", type=Pointer(pointee_type=Void()))
            )

        return [VarDecl(name=n, type=t, init=mallocCall) for (n, t) in splits.values()]


    def visit_DeclStmt(self, node: DeclStmt):
        replacement_stmts = []

        for var_decl in node.vardecl:
            replacement_var_decls = self.as_list(self.visit(var_decl))
            replacement_stmts += [
                DeclStmt(vardecl=[vd]) for vd in replacement_var_decls
            ]

        return replacement_stmts

    def visit_MemberRefExpr(self, node: MemberRefExpr):
        if hasattr(node.containerexpr,
                   "type") and node.containerexpr.type.is_struct_like():
            struct_like_type = node.containerexpr.type.get_chain_end()
            if self.struct_is_defined(struct_like_type.name):
                return self.replace_container_expr(node.containerexpr,
                                                   node.name)

        return self.generic_visit(node)

    def visit_ParmDecl(self, node: ParmDecl):
        if node.type.is_struct_like():
            splits = self.split_struct_type(node.type, node.name)
            if splits is None:
                return self.generic_visit(node)

            return [ParmDecl(name=n, type=t) for (n, t) in splits.values()]

        return self.generic_visit(node)


class CXXClassToStruct(NodeTransformer):
    def __init__(self):
        self.replacement_structs: List[StructDecl] = []
        self.exported_functions: List[FuncDecl] = []

    def get_class_type_replacement_name(self, class_name):
        return "c2d_class_as_struct_" + class_name

    def get_class_type_replacement(self, class_like_type) -> Type:

        if isinstance(class_like_type, Class):
            return Struct(name=self.get_class_type_replacement_name(
                class_like_type.name))

        if isinstance(class_like_type, Pointer):
            t = self.get_class_type_replacement(class_like_type.pointee_type)
            if t is not None:
                return Pointer(pointee_type=t)

        if isinstance(class_like_type, ConstantArray):
            t = self.get_class_type_replacement(class_like_type.element_type)
            if t is not None:
                return ConstantArray(size=class_like_type.size, element_type=t)

        return None

    def is_class_like(self, type) -> bool:
        if isinstance(type, ConstantArray):
            return self.is_class_like(type.element_type)
        if isinstance(type, Pointer):
            return self.is_class_like(type.pointee_type)
        return isinstance(type, Class)

    def get_class_variable_replacement_name(self, var_name):
        return var_name

    def get_method_replacement_name(self, method_name, class_name):
        return "c2d_" + class_name + "_method_" + method_name

    def visit_AST(self, node: AST):
        transformed_ast = self.generic_visit(node)
        transformed_ast.structdefs += self.replacement_structs
        transformed_ast.funcdefs += self.exported_functions

        return transformed_ast

    def visit_ClassDecl(self, node: ClassDecl):
        replacement_struct = StructDecl(
            name=self.get_class_type_replacement_name(node.name),
            fields=node.fields)
        self.replacement_structs.append(replacement_struct)

        self.generic_visit(node)
        return None

    def visit_CXXMethod(self, node: CXXMethod):
        if node.body is None:
            return None

        node = self.generic_visit(node)

        replacement_struct_name = self.get_class_type_replacement_name(
            node.parent_class_type.name)
        this_arg = ParmDecl(
            name="c2d_this",
            type=Pointer(pointee_type=Struct(name=replacement_struct_name)))

        replacement_function_name = self.get_method_replacement_name(
            node.name, node.parent_class_type.name)
        replacement_function = FuncDecl(name=replacement_function_name,
                                        args=[this_arg] + node.args,
                                        body=node.body)
        self.exported_functions.append(replacement_function)
        return None

    def visit_MemberRefExpr(self, node: MemberRefExpr):
        """
        Replace any class field accesses with accesses to their replacement struct
        """
        node = self.generic_visit(node)

        return node

    def visit_DeclRefExpr(self, node: DeclRefExpr):
        """
        Replace any references to a class declaration with references to their replacement struct
        """
        if hasattr(node, "type") and self.is_class_like(node.type):
            replacement_struct_type = self.get_class_type_replacement(
                node.type)
            return DeclRefExpr(name=self.get_class_variable_replacement_name(
                node.name),
                               type=replacement_struct_type)

        return self.generic_visit(node)

    def visit_VarDecl(self, node: VarDecl):

        if self.is_class_like(node.type):
            replacement_struct_type = self.get_class_type_replacement(
                node.type)
            return VarDecl(name=self.get_class_variable_replacement_name(
                node.name),
                           type=replacement_struct_type)

        return self.generic_visit(node)

    def visit_CXXThisExpr(self, node: CXXThisExpr):
        replacement_struct_name = self.get_class_type_replacement_name(
            node.type.pointee_type.name)
        return DeclRefExpr(
            name="c2d_this",
            type=Pointer(pointee_type=Struct(name=replacement_struct_name)))

    def visit_CallExpr(self, node: CallExpr):
        """
        Replace any method calls with calls to their exported counterparts.
        """

        if isinstance(node.name, MemberRefExpr):
            mrefexpr = node.name
            containerexpr = mrefexpr.containerexpr

            #direct member ref expression:   class_var.method()
            if hasattr(containerexpr, "type") and isinstance(
                    containerexpr.type, Class):
                replacement_function_name = self.get_method_replacement_name(
                    mrefexpr.name, containerexpr.type.name)
                first_argument = UnOp(lvalue=self.visit(containerexpr),
                                      op="&",
                                      postfix=False)
                return CallExpr(name=replacement_function_name,
                                args=[first_argument] +
                                [self.visit(a) for a in node.args])

            #indirect member ref expression:   class_var->method()
            if hasattr(containerexpr, "type") and isinstance(
                    containerexpr.type, Pointer):
                if isinstance(containerexpr.type.pointee_type, Class):
                    replacement_function_name = self.get_method_replacement_name(
                        mrefexpr.name, containerexpr.type.pointee_type.name)
                    first_argument = self.visit(containerexpr)
                    return CallExpr(name=replacement_function_name,
                                    args=[first_argument] +
                                    [self.visit(a) for a in node.args])

        return self.generic_visit(node)


class PrinterVisitor(NodeVisitor):
    def visit_VarDecl(self, node: VarDecl):
        print(node.name + " = ", end='')
        if hasattr(node, "init"):
            print(node.init)
        else:
            print()

    def visit_BasicBlock(self, node: BasicBlock):
        for child in node.body:
            if not isinstance(child, DeclStmt):
                print(child)
            self.visit(child)
        return node