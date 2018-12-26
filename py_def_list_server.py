
# -*- coding: utf-8 -*-
import pdb
import ast
from collections import deque
import tokenize

from epc.server import EPCServer


file_def_cache = {}
_func_def_types = tuple(
    getattr(ast, type_s) for type_s in (
        'FunctionDef', 'AsyncFunctionDef') if hasattr(ast, type_s))


def get_file_def_list(*args):
    filename = args[0]
    with open(filename) as f:
        source = f.read()
    main_node = ast.parse(source)
    node_list = []
    for node in main_node.body:
        def_list = parse_def_node(node)
        if def_list:
            node_list.append(def_list)
    return list(filter(bool, node_list))


def get_file_def_pos(filename, keyword=None):

    if filename not in file_def_cache:
        # 没命中缓存
        # No hit cache
        def_map = refresh_file_def_pos(filename)
    else:
        def_map = file_def_cache[filename]

    if not keyword:
        return tuple(def_map.keys())
    return def_map[keyword]


def refresh_file_def_pos(filename):
    def_list = get_file_def_list(filename)
    def_token = get_file_def_token(filename)
    def_map = iter_def_list(def_list, def_token)
    file_def_cache[filename] = def_map
    return def_map


def iter_def_list(def_list, token_map, rootclass=None):
    def_map = {}
    for d in def_list:
        def_type = d[0]
        if rootclass is None:
            def_map[d[1]] = token_map[d[1]]
        else:
            new_name = rootclass + '.' + d[1]
            def_map[new_name] = token_map[new_name]

        if def_type == 'class':
            # 类中定义
            # Class definition
            if rootclass is None:
                down_rootclass = d[1]
            else:
                down_rootclass = rootclass + '.' + d[1]

            def_map.update(iter_def_list(d[-1], token_map, down_rootclass))
    return def_map


def echo(*args):
    return args


def parse_def_node(node):
    if isinstance(node, _func_def_types):
        # 函数节点
        # function node
        return ('function', node.name, node.lineno, node.col_offset)
    elif isinstance(node, ast.ClassDef):
        # 类节点
        # class node
        children_list = []
        for n in node.body:
            def_list = parse_def_node(n)
            if def_list:
                children_list.append(def_list)
        return ('class', node.name, node.lineno, node.col_offset, children_list)
    return ()


def get_file_def_token(filename):
    readline = open(filename).readline
    token_generator = tokenize.generate_tokens(readline)
    indent_queue = deque()
    check_token = (tokenize.INDENT, tokenize.DEDENT, tokenize.NAME)
    check_name = ('def', 'class')
    token_map = {}
    function_name = None
    class_name = None
    def_token = None

    while True:
        try:
            token_type, token_str, start, end, __ = next(token_generator)
        except StopIteration:
            break

        if token_type not in check_token:
            continue

        if token_type == tokenize.INDENT:
            # 缩进
            # indentation
            if function_name:
                indent_token = 'def'
            elif class_name:
                indent_token = 'class'
            else:
                indent_token = None

            indent_queue.append((indent_token, class_name, function_name))

        elif token_type == tokenize.DEDENT:
            # 退出缩进
            # exit indent
            if not indent_queue:
                continue

            d = indent_queue.pop()
            if d[0] == 'def':
                # 退出函数缩进
                # exit function indent
                if indent_queue:
                    function_name = indent_queue[-1][2]
                else:
                    function_name = None
            elif d[0] == 'class':
                # 退出类缩进
                # exit class indent
                if indent_queue:
                    class_name = indent_queue[-1][1]
                else:
                    class_name = None
        else:
            # 定义
            # definition
            if token_str in check_name:
                def_token = token_str
                if function_name:
                    if not indent_queue or function_name != indent_queue[-1][-1]:
                        # 处理单行函数定义
                        # Handling ingle line function definition
                        function_name = None
                    else:
                        # 忽略函数内部定义的类和函数
                        # Ignore classes and functions defined inside the function
                        def_token = None
                elif class_name:
                    if not indent_queue or class_name != indent_queue[-1][1]:
                        # 处理单行类定义
                        # Handling single-line class definitions
                        class_name = None
            elif def_token:
                if def_token == 'def':
                    # 定义函数
                    # Defining function
                    function_name = token_str
                    if class_name is None:
                        # 模块顶级函数
                        # Module top level function
                        token_map[function_name] = start
                    else:
                        # 类函数
                        # Class function
                        full_function_name = class_name + '.' + function_name
                        token_map[full_function_name] = start
                elif def_token == 'class':
                    if class_name is None or not indent_queue:
                        # 新定义一个类
                        # Define a new class
                        class_name = token_str
                    elif indent_queue:
                        class_name = class_name + '.' + token_str
                    token_map[class_name] = start
                def_token = None

    return token_map


def main():
    server  = EPCServer(('localhost', 9898))
    server.register_function(echo)
    server.register_function(get_file_def_pos)
    server.register_function(refresh_file_def_pos)
    server.print_port()
    server.serve_forever()


if __name__ == '__main__':
    main()
