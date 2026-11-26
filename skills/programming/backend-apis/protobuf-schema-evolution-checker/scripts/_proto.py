"""Minimal .proto (proto3 / editions) parser shared by the scripts in this skill.

Returns a dict: syntax, package, options, messages {full_name: {fields, reserved_numbers, reserved_names, line}},
enums {full_name: {values: [(name, number)], line}}, services {name: {rpcs: [(name, req, resp, req_stream, resp_stream)]}}.
Fields: {name, number, type, label ('repeated', 'optional', 'required' or ''), oneof, line}.
Good enough for linting and diffing hand-written protos; not a full protoc replacement.
"""

import re

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[A-Za-z_][\w.]*|\d+|[{}()\[\];=<>,]|\S')


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def tokenize(text):
    out = []
    for i, line in enumerate(strip_comments(text).split("\n"), 1):
        out += [(m.group(0), i) for m in TOKEN.finditer(line)]
    return out


def parse(text):
    toks = tokenize(text)
    res = {"syntax": None, "package": "", "options": {}, "messages": {}, "enums": {}, "services": {}}
    pos = 0

    def peek(k=0):
        return toks[pos + k][0] if pos + k < len(toks) else None

    def take():
        nonlocal pos
        tok = toks[pos]
        pos += 1
        return tok

    def skip_statement():
        depth = 0
        while pos < len(toks):
            t = take()[0]
            if t in "[(<{":
                depth += 1
            elif t in "])>}":
                depth -= 1
            elif t == ";" and depth <= 0:
                return

    def skip_block():
        depth = 0
        while pos < len(toks):
            t = take()[0]
            if t == "{":
                depth += 1
            elif t == "}":
                depth -= 1
                if depth == 0:
                    return

    def parse_enum(prefix):
        _, line = take()
        name = take()[0]
        full = f"{prefix}{name}"
        take()  # {
        values = []
        while peek() not in ("}", None):
            if peek() in ("option", "reserved"):
                skip_statement()
                continue
            vname = take()[0]
            if peek() == "=":
                take()
                neg = take()[0] if peek() == "-" else ""
                values.append((vname, int(neg + take()[0])))
            skip_statement()
        take()
        res["enums"][full] = {"values": values, "line": line}

    def parse_message(prefix):
        _, line = take()
        name = take()[0]
        full = f"{prefix}{name}"
        take()  # {
        msg = {"fields": [], "reserved_numbers": set(), "reserved_names": set(), "line": line}
        res["messages"][full] = msg
        oneof = None
        depth_oneof = 0
        while pos < len(toks):
            t = peek()
            if t == "}":
                take()
                if oneof and depth_oneof:
                    oneof, depth_oneof = None, 0
                    continue
                return
            if t == "message":
                parse_message(full + ".")
            elif t == "enum":
                parse_enum(full + ".")
            elif t == "oneof":
                take()
                oneof = take()[0]
                take()  # {
                depth_oneof = 1
            elif t in ("option", "extensions", "extend"):
                skip_block() if t == "extend" else skip_statement()
            elif t == "reserved":
                take()
                while peek() not in (";", None):
                    tok = take()[0]
                    if tok.startswith('"'):
                        msg["reserved_names"].add(tok.strip('"'))
                    elif tok.isdigit():
                        lo = int(tok)
                        hi = lo
                        if peek() == "to":
                            take()
                            nxt = take()[0]
                            hi = 536870911 if nxt == "max" else int(nxt)
                        msg["reserved_numbers"].update(range(lo, min(hi, lo + 100000) + 1))
                take()
            else:
                label = take()[0] if t in ("repeated", "optional", "required") else ""
                fline = toks[pos][1]
                if peek() == "map":
                    take(); take()
                    k = take()[0]; take(); v = take()[0]; take()
                    ftype = f"map<{k},{v}>"
                else:
                    ftype = take()[0]
                fname = take()[0]
                if peek() == "=":
                    take()
                    num = take()[0]
                    msg["fields"].append({"name": fname, "number": int(num) if num.isdigit() else -1, "type": ftype,
                                          "label": label, "oneof": oneof, "line": fline})
                skip_statement()
        return

    while pos < len(toks):
        t = peek()
        if t == "syntax" or t == "edition":
            take(); take()
            res["syntax"] = take()[0].strip('"')
            skip_statement()
        elif t == "package":
            take()
            res["package"] = take()[0]
            skip_statement()
        elif t == "option":
            take()
            key = take()[0]
            if peek() == "=":
                take()
                res["options"][key] = take()[0].strip('"')
            skip_statement()
        elif t == "import":
            skip_statement()
        elif t == "message":
            parse_message("")
        elif t == "enum":
            parse_enum("")
        elif t == "service":
            _, line = take()
            sname = take()[0]
            take()
            rpcs = []
            while peek() not in ("}", None):
                if peek() == "rpc":
                    take()
                    rname = take()[0]
                    take()
                    req_stream = peek() == "stream" and bool(take())
                    req = take()[0]
                    take(); take(); take()  # ) returns (
                    resp_stream = peek() == "stream" and bool(take())
                    resp = take()[0]
                    take()  # )
                    if peek() == "{":
                        skip_block()
                    else:
                        skip_statement()
                    rpcs.append((rname, req, resp, req_stream, resp_stream))
                else:
                    skip_statement()
            take()
            res["services"][sname] = {"rpcs": rpcs, "line": line}
        else:
            take()
    return res
