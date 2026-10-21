#!/usr/bin/env python3
"""Classify where a Python profile spends its time, and say whether threads can help.

Reads a cProfile/pstats file (``python -m cProfile -o out.prof app.py``) and/or a
collapsed-stack text file (``py-spy record --format raw -o stacks.txt ...`` or the
output of ``stackcollapse-perf.pl`` on ``perf script`` taken with ``python -X perf``).
It never imports or runs the profiled code; only ``--demo`` runs a small built-in
synthetic workload under cProfile so the pstats path can be exercised on any
Python version.

Every hot spot (self time) is put in one bucket:

  python-cpu      pure-Python bytecode (holds the GIL)
  native-hold     C/Rust code known to hold the GIL (re, json, pickle, sorted, str methods, ...)
  native-release  C/Rust code known to release the GIL (hashlib, zlib, numpy ufuncs, BLAS, ...)
  native-unknown  other built-ins (GIL behaviour unknown, assume it holds)
  io-wait         sleep, select/poll/epoll, socket and file reads, lock acquire (GIL released)
  gil-wait        waiting to take the GIL (needs native frames: py-spy --native or perf)
  import          import machinery and module bodies run at import time

It then prints the share of time per bucket, the top hot spots, a verdict and
recommendations ranked by expected impact (threads will / will not help, use
processes, vectorise, asyncio, free-threaded build, fix the algorithm), each with a
confidence level.

Exit codes: 0 analysed, 1 --fail-if-python-cpu-over gate failed,
2 usage error, unreadable file, or a pstats file this Python cannot load.

Examples:
    python -m cProfile -o out.prof ingest.py
    python profile_classify.py out.prof
    py-spy record --format raw -o stacks.txt --native -- python ingest.py
    python profile_classify.py stacks.txt --top 15 --json
    cat stacks.txt | python profile_classify.py - --fail-if-python-cpu-over 50
    python profile_classify.py --demo
"""

import argparse
import json
import os
import re
import sys
import tempfile

EXIT_OK, EXIT_GATE, EXIT_ERROR = 0, 1, 2

CATEGORIES = [
    ("python-cpu", "pure-Python CPU (holds the GIL)"),
    ("native-hold", "native code holding the GIL"),
    ("native-unknown", "native code, GIL behaviour unknown"),
    ("native-release", "native code releasing the GIL"),
    ("io-wait", "I/O, sleep and lock waits (GIL released)"),
    ("gil-wait", "waiting to acquire the GIL"),
    ("import", "imports and startup"),
]
LABELS = dict(CATEGORIES)
GIL_HELD = ("python-cpu", "native-hold", "native-unknown")

# --- built-in names as cProfile writes them: "<built-in method mod.fn>" / "<method 'm' of 'T' objects>" ---
# (pattern, category, family)
BUILTIN_RULES = [
    # imports
    (r"built-in method (marshal\.loads|_imp\.|builtins\.__import__|_io\.open_code)", "import", "import"),
    # waiting: the GIL is released while blocked
    (r"time\.sleep", "io-wait", "sleep"),
    (r"select\.(select|poll|epoll)|of 'select\.(poll|epoll|kqueue|devpoll)' objects", "io-wait", "select/poll"),
    (r"'(recv|recv_into|recvfrom|recvfrom_into|recvmsg|accept|_accept|connect|connect_ex|send|sendall|sendto"
     r"|sendmsg)' of '_socket\.socket'", "io-wait", "socket"),
    (r"_socket\.getaddrinfo|_socket\.gethostbyname", "io-wait", "dns"),
    (r"of '_ssl\._SSLSocket' objects", "io-wait", "ssl"),
    (r"'(acquire|__enter__|acquire_lock)' of '_thread\.(lock|RLock)'|of '_queue\.SimpleQueue'", "io-wait",
     "lock/queue wait"),
    (r"posix\.(waitpid|wait|wait4|waitid|read|write|readv|pread|stat|lstat|listdir|scandir|open|fsync)"
     r"|nt\.(waitpid|read|write|stat|listdir|scandir|open)", "io-wait", "os/syscall"),
    (r"of '_io\.(FileIO|BufferedReader|BufferedWriter|BufferedRandom|TextIOWrapper)' objects", "io-wait",
     "file I/O"),
    (r"_winapi\.WaitFor|_overlapped\.", "io-wait", "windows wait"),
    (r"builtins\.(print|input)", "io-wait", "console I/O"),
    # native code that releases the GIL
    (r"_hashlib\.|of '_hashlib\.|_blake2\.|of '_blake2\.|_sha2\.|of '_sha2\.|_sha3\.|_md5\.|_sha1\.",
     "native-release", "hashlib"),
    (r"zlib\.(compress|decompress|crc32|adler32)|of 'zlib\.(Compress|Decompress|_ZlibDecompressor)'",
     "native-release", "zlib"),
    (r"_bz2\.|of '_bz2\.|_lzma\.|of '_lzma\.|_zstd\.|of '_zstd\.", "native-release", "bz2/lzma/zstd"),
    (r"numpy\.(array|asarray|asanyarray|fromiter|ascontiguousarray)>|'tolist' of 'numpy\.ndarray'",
     "native-hold", "numpy object conversion"),
    (r"numpy\.ufunc|of 'numpy\.ndarray' objects|numpy\.(dot|matmul|vdot|inner|einsum|concatenate|where|sort"
     r"|argsort|empty|zeros|arange|copyto)|_umath_linalg|numpy\..*implement_array_function|numpy\.linalg",
     "native-release", "numpy"),
    (r"torch\._C|of 'torch\._C|torch\.(matmul|mm|bmm|cat|stack|softmax|topk|sort)\b", "native-release",
     "torch"),
    (r"'encode_batch' of 'tokenizers|'decode_batch' of 'tokenizers", "native-release", "HF tokenizers batch"),
    (r"_sqlite3\.|of 'sqlite3\.(Cursor|Connection)'", "native-release", "sqlite3"),
    (r"of 'PIL\.|PIL\._imaging|cv2\.", "native-release", "image codecs"),
    # native code that holds the GIL
    (r"of 're\.(Pattern|Match)' objects|_sre\.", "native-hold", "re"),
    (r"_json\.|of '_json\.", "native-hold", "json"),
    (r"orjson\.|msgspec\.|ujson\.|simdjson", "native-hold", "fast json"),
    (r"_pickle\.|of '_pickle\.|marshal\.(dumps|loads)", "native-hold", "pickle"),
    (r"pydantic_core|of 'pydantic_core", "native-hold", "pydantic"),
    (r"builtins\.(sorted|sum|min|max|any|all|len|isinstance|hash|abs|round|map|filter|zip|enumerate|repr"
     r"|format|getattr|setattr|hasattr|iter|next|divmod|pow|ord|chr)", "native-hold", "builtins"),
    (r"builtins\.(exec|eval|compile|__build_class__)", "native-hold", "exec/compile"),
    (r"of '(str|bytes|bytearray)' objects", "native-hold", "str/bytes methods"),
    (r"of '(list|dict|set|frozenset|tuple|int|float|collections\.deque)' objects", "native-hold",
     "container methods"),
    (r"_struct\.|_csv\.|_heapq\.|_bisect\.|math\.|_functools\.|itertools\.|_collections\.|_operator\."
     r"|_random\.|of '_random|unicodedata\.|_codecs\.|_string\.|_elementtree|pyexpat|lxml\.", "native-hold",
     "stdlib C helpers"),
    (r"'encode' of 'tokenizers|tokenizers\.", "native-unknown", "HF tokenizers (single)"),
]
BUILTIN_RULES = [(re.compile(p), c, f) for p, c, f in BUILTIN_RULES]

# Python-level wrappers whose self time is really spent in C (cProfile cannot see C callables
# such as _json.Scanner, and py-spy without --native attributes C time to the calling line).
PY_WRAPPERS = [
    (re.compile(r"json[/\\](decoder|encoder|__init__)\.py"), {"raw_decode", "decode", "iterencode", "encode",
                                                              "loads", "dumps"}, "native-hold", "json"),
    (re.compile(r"re[/\\]__init__\.py|(^|[/\\])re\.py"), {"sub", "subn", "findall", "finditer", "search",
                                                         "match", "fullmatch", "split"}, "native-hold", "re"),
    (re.compile(r"selectors\.py"), {"select"}, "io-wait", "select/poll"),
    (re.compile(r"threading\.py"), {"wait", "_wait_for_tstate_lock", "join", "acquire"}, "io-wait",
     "lock/queue wait"),
    (re.compile(r"(^|[/\\])queue\.py"), {"get", "put"}, "io-wait", "lock/queue wait"),
    (re.compile(r"(^|[/\\])(socket|ssl)\.py"), {"readinto", "read", "recv", "recv_into", "accept",
                                                "create_connection", "sendall", "do_handshake", "connect"},
     "io-wait", "socket"),
    (re.compile(r"subprocess\.py"), {"_wait", "wait", "communicate", "_try_wait", "_communicate"}, "io-wait",
     "subprocess wait"),
    (re.compile(r"multiprocessing[/\\]connection\.py"), {"_recv", "_recv_bytes", "recv", "recv_bytes", "poll",
                                                         "_poll", "wait"}, "io-wait", "multiprocessing pipe"),
    (re.compile(r"concurrent[/\\]futures[/\\]_base\.py"), {"result", "wait", "as_completed"}, "io-wait",
     "future wait"),
    (re.compile(r"(^|[/\\])time\.py"), {"sleep"}, "io-wait", "sleep"),
]

# --- native symbols in collapsed stacks (py-spy --native, perf) ---
NATIVE_RULES = [
    (r"take_gil|drop_gil|_PyEval_AcquireLock|PyEval_RestoreThread|PyEval_AcquireThread|_PyThreadState_Attach"
     r"|PyGILState_Ensure", "gil-wait", "GIL"),
    (r"__libc_(recv|read|write|send|accept|connect|select|poll)|sem_clockwait|pthread_cond_clockwait|epoll_wait|\bpoll\b|\bselect\b|__select|nanosleep|clock_nanosleep|\bsleep\b|recv|__libc_read|\bread\b"
     r"|__libc_write|\bwrite\b|accept|connect|sendto|\bsend\b|pthread_cond_(timed)?wait|sem_(timed)?wait"
     r"|futex|__lll_lock_wait|PyThread_acquire_lock|do_syscall|WaitForSingleObject|WaitForMultipleObjects",
     "io-wait", "syscall wait"),
    (r"sha\d|SHA\d|sha256_block|md5_block|blake2|deflate|inflate|crc32|adler32|BZ2_|lzma_|ZSTD_", "native-release",
     "hash/compress"),
    (r"gemm|gemv|mkl_|openblas|cblas|dot_kernel|GOMP|omp_|__kmp|tbb::", "native-release", "BLAS/OpenMP"),
    (r"npy_|DOUBLE_|FLOAT_|HALF_|LONG_|INT\d*_|_umath|ufunc_|PyArray_|simd_", "native-release", "numpy"),
    (r"tokenizers::|rayon|crossbeam", "native-release", "Rust thread pool"),
    (r"at::|c10::|torch::|mkldnn|dnnl_|cudaStream|cuLaunch", "native-release", "torch"),
    (r"sre_|_sre|SRE\(|sre_ucs", "native-hold", "re"),
    (r"scanstring|_json|encoder_listencode|scan_once", "native-hold", "json"),
    (r"_PyEval_EvalFrame|_PyEval_Vector|PyEval_EvalCode|_PyObject_Call|PyObject_Vectorcall|_PyFunction_"
     r"|PyFrame|_Py_call|_PyInterpreterFrame|py_trampoline", "python-cpu", "interpreter"),
    (r"_pickle|save_reduce|load_build|marshal", "native-hold", "pickle"),
    (r"list_sort|unicode_|PyUnicode_|PyBytes_|_PyBytes|dict_|PyDict_|_PyDict|PyList_|PyLong_|long_|float_"
     r"|PyTuple_|_PyLong|PyObject_|_PyObject|_Py_|Py[A-Z][a-z]+_", "native-hold", "CPython runtime"),
]
NATIVE_RULES = [(re.compile(p), c, f) for p, c, f in NATIVE_RULES]
KERNEL_RE = re.compile(r"\[k\]|kernel|^entry_SYSCALL|^__x64_sys_|^do_syscall|^\[unknown\]$")
IMPORT_FRAME_RE = re.compile(r"_find_and_load|_load_unlocked|<frozen importlib|importlib[/\\]_bootstrap"
                             r"|_call_with_frames_removed|exec_module")
PYSPY_FRAME_RE = re.compile(r"^(?P<func>.*?) \((?P<file>[^()]*?)(?::(?P<line>\d+))?\)$")
PERF_PY_RE = re.compile(r"^py::(?P<func>[^:]+):(?P<file>.+)$")
COLLAPSED_LINE_RE = re.compile(r"^(?P<stack>.*\S)\s+(?P<count>\d+)\s*$")


class UsageError(Exception):
    """Bad input: reported on stderr with exit code 2."""


# ----------------------------------------------------------------------------- classification

def classify_builtin(name):
    """Return (category, family) for a cProfile built-in entry name."""
    for rx, cat, fam in BUILTIN_RULES:
        if rx.search(name):
            return cat, fam
    return "native-unknown", "other built-in"


def classify_python_function(filename, func):
    """Return (category, family) for a Python-level function's self time."""
    norm = filename.replace("\\", "/")
    if norm.startswith("<frozen importlib") or "importlib/_bootstrap" in norm:
        return "import", "import"
    for rx, funcs, cat, fam in PY_WRAPPERS:
        if func in funcs and rx.search(norm):
            return cat, fam
    return "python-cpu", "python"


def classify_native_symbol(sym):
    for rx, cat, fam in NATIVE_RULES:
        if rx.search(sym):
            return cat, fam
    return "native-unknown", "native"


# ----------------------------------------------------------------------------- pstats

def load_pstats(path, display=None):
    import pstats

    try:
        stats = pstats.Stats(path)
        raw = stats.stats
        total = 0.0
        for key, value in raw.items():
            if len(key) != 3 or len(value) != 5:
                raise ValueError("unexpected entry layout")
            total += float(value[2])
    except Exception as err:  # marshal/version/layout errors all mean "cannot use this file"
        raise UsageError(
            f"cannot load {display or path!r} as a cProfile/pstats file ({type(err).__name__}: {err}). pstats files are "
            f"marshal data written by one Python version; regenerate it with this interpreter "
            f"(Python {sys.version_info[0]}.{sys.version_info[1]}): python -m cProfile -o out.prof your_script.py, "
            f"or pass --format collapsed if it is a py-spy/perf collapsed-stack text file") from None
    return raw, total


def import_fractions(raw):
    """Fraction of each entry's time that happens during imports, propagated through caller edges."""
    seeds = {}
    module_entries = [k for k in raw if k[2] == "<module>"]
    main_module = max(module_entries, key=lambda k: raw[k][3], default=None)
    for key in raw:
        filename, _line, func = key
        if filename.startswith("<frozen importlib") or "importlib/_bootstrap" in filename.replace("\\", "/"):
            seeds[key] = 1.0
        elif filename == "~" and classify_builtin(func)[0] == "import":
            seeds[key] = 1.0
        elif func == "<module>":
            seeds[key] = 0.0 if key == main_module or filename in ("<string>",) else 1.0
    frac = {k: seeds.get(k, 0.0) for k in raw}
    for _ in range(25):
        changed = False
        for key, value in raw.items():
            if key in seeds:
                continue
            callers = value[4] or {}
            weight = sum(float(c[3]) if len(c) > 3 else 0.0 for c in callers.values())
            if weight <= 0:
                continue
            new = sum((float(c[3]) if len(c) > 3 else 0.0) * frac.get(ck, 0.0) for ck, c in callers.items())
            new /= weight
            if abs(new - frac[key]) > 1e-6:
                frac[key] = new
                changed = True
        if not changed:
            break
    return frac


def analyse_pstats(path, display):
    raw, total = load_pstats(path, display)
    if total <= 0:
        raise UsageError(f"{display}: the profile records no time (empty or truncated pstats file)")
    frac = import_fractions(raw)
    buckets = {}
    for key, value in raw.items():
        filename, line, func = key
        tt, ncalls = float(value[2]), int(value[1])
        if tt <= 0:
            continue
        if filename == "~":
            cat, fam = classify_builtin(func)
            label = func.replace("<", "{", 1)[:-1] + "}" if func.startswith("<") else func
        else:
            cat, fam = classify_python_function(filename, func)
            label = f"{func} ({short_path(filename)}:{line})"
        f_imp = frac.get(key, 0.0) if cat != "import" else 1.0
        if f_imp > 0:
            add(buckets, ("import", "import", label), tt * f_imp, ncalls)
        if f_imp < 1:
            add(buckets, (cat, fam, label), tt * (1 - f_imp), ncalls)
    caveats = [
        "cProfile times only the thread it was enabled in (normally the main thread); profile worker threads "
        "with py-spy --threads or threading.setprofile.",
        "Operator calls on arrays (a + b, a @ b) are not function calls: cProfile charges that numpy time to the "
        "calling Python function, so numpy-heavy code can look like pure-Python CPU.",
        "cProfile adds per-call overhead, inflating code that makes millions of tiny calls; confirm with py-spy.",
    ]
    return make_report(display, "pstats", "seconds", total, buckets, {}, caveats)


# ----------------------------------------------------------------------------- collapsed stacks

def parse_frame(frame):
    """Return (kind, func, file) where kind is 'python', 'native' or 'header'."""
    frame = frame.strip()
    if re.match(r"^process \d+", frame) or re.match(r"^thread \(0x[0-9a-fA-F]+\)", frame):
        return "header", frame, ""
    m = PERF_PY_RE.match(frame)
    if m:
        return "python", m.group("func"), m.group("file")
    m = PYSPY_FRAME_RE.match(frame)
    if m:
        file = m.group("file")
        if file.endswith((".py", ".pyw", ".pyx")) or file.startswith("<"):
            return "python", m.group("func"), file
        return "native", m.group("func"), file
    if frame.endswith(".py") or frame.startswith("<frozen"):
        return "python", frame, frame
    return "native", frame, ""


def classify_stack(frames):
    """Classify one sampled stack (root first) by its leaf; return (category, family, label)."""
    parsed = [parse_frame(f) for f in frames]
    body = [p for p in parsed if p[0] != "header"]
    if not body:
        return "native-unknown", "empty", "<empty stack>"
    if any(IMPORT_FRAME_RE.search(f"{func} {file}") for _k, func, file in body):
        leaf = next((p for p in reversed(body) if p[0] == "python"), body[-1])
        return "import", "import", frame_label(leaf)
    # walk native frames from the leaf up to the first Python frame
    native_tail = []
    for kind, func, file in reversed(body):
        if kind == "python":
            break
        native_tail.append((kind, func, file))
    if native_tail:
        for frame in native_tail:
            cat, fam = classify_native_symbol(frame[1])
            if cat == "gil-wait":
                return cat, fam, frame_label(frame)
        leaf = next((p for p in native_tail if not KERNEL_RE.search(p[1])), native_tail[-1])
        cat, fam = classify_native_symbol(leaf[1])
        if cat == "native-unknown" and leaf is not native_tail[0]:
            cat, fam = classify_native_symbol(native_tail[0][1])
        return cat, fam, frame_label(leaf)
    leaf = body[-1]
    cat, fam = classify_python_function(leaf[2], leaf[1])
    return cat, fam, frame_label(leaf)


def frame_label(parsed):
    kind, func, file = parsed
    return f"{func} ({short_path(file)})" if file else func


def analyse_collapsed(text, display):
    buckets, threads = {}, {}
    total, has_native, bad = 0, False, 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = COLLAPSED_LINE_RE.match(line)
        if not m:
            bad += 1
            continue
        count = int(m.group("count"))
        frames = [f for f in m.group("stack").split(";") if f]
        if not frames:
            continue
        thread = next((f.strip() for f in frames if f.strip().startswith("thread (")), None)
        if any(parse_frame(f)[0] == "native" for f in frames):
            has_native = True
        cat, fam, label = classify_stack(frames)
        add(buckets, (cat, fam, label), count, None)
        if thread:
            per = threads.setdefault(thread, {})
            per[cat] = per.get(cat, 0) + count
        total += count
    if total == 0:
        raise UsageError(f"{display}: no collapsed-stack lines found (expected 'frame;frame;frame COUNT'); "
                         f"for a pstats file pass --format pstats")
    caveats = []
    if not has_native:
        caveats.append("No native frames: time inside C/Rust calls is charged to the calling Python line, so "
                       "native and GIL-wait time can hide inside 'pure-Python CPU'. Re-record with "
                       "py-spy --native (or perf with python -X perf) for a precise split.")
    if bad:
        caveats.append(f"Skipped {bad} line(s) that are not collapsed-stack format.")
    caveats.append("py-spy drops idle threads unless --idle is given, and --gil keeps only samples holding the "
                   "GIL; the shares describe whichever samples were recorded.")
    return make_report(display, "collapsed", "samples", total, buckets, threads, caveats,
                       native_frames=has_native)


# ----------------------------------------------------------------------------- report

def add(buckets, key, amount, ncalls):
    entry = buckets.setdefault(key, [0.0, 0])
    entry[0] += amount
    if ncalls:
        entry[1] += ncalls


def short_path(path):
    norm = path.replace("\\", "/")
    for marker in ("site-packages/", "dist-packages/"):
        if marker in norm:
            return norm.split(marker, 1)[1]
    m = re.search(r"/python3\.\d+t?/(.+)$", norm)
    if m:
        return m.group(1)
    parts = norm.split("/")
    return "/".join(parts[-2:]) if len(parts) > 2 else norm


def make_report(display, fmt, unit, total, buckets, threads, caveats, native_frames=True):
    shares = {c: 0.0 for c, _ in CATEGORIES}
    families = {}
    for (cat, fam, _label), (amount, _n) in buckets.items():
        shares[cat] += amount
        families[(cat, fam)] = families.get((cat, fam), 0.0) + amount
    shares = {c: round(100.0 * v / total, 2) for c, v in shares.items()}
    hotspots = sorted(buckets.items(), key=lambda kv: -kv[1][0])
    hot = [{"label": label, "category": cat, "family": fam, "share": round(100.0 * amount / total, 2),
            "self": round(amount, 6) if unit == "seconds" else int(amount), "ncalls": n or None}
           for (cat, fam, label), (amount, n) in hotspots]
    fam_list = sorted(({"category": c, "family": f, "share": round(100.0 * v / total, 2)}
                       for (c, f), v in families.items()), key=lambda d: -d["share"])
    per_thread = {}
    for name, cats in threads.items():
        n = sum(cats.values())
        per_thread[name] = {"samples": n, "shares": {c: round(100.0 * v / n, 1) for c, v in cats.items()}}
    return {"source": display, "format": fmt, "unit": unit, "total": round(total, 6) if unit == "seconds"
            else int(total), "shares": shares, "families": fam_list, "hotspots": hot, "threads": per_thread,
            "caveats": caveats, "native_frames": native_frames}


def recommend(shares, families, hotspots, precise_native):
    """Return (verdict, [recommendation dicts]) ranked by expected impact."""
    held = sum(shares[c] for c in GIL_HELD)
    released = shares["native-release"] + shares["io-wait"]
    py, io, rel, gw, imp = (shares["python-cpu"], shares["io-wait"], shares["native-release"],
                            shares["gil-wait"], shares["import"])
    fam = {}
    for f in families:
        fam[f["family"]] = fam.get(f["family"], 0.0) + f["share"]
    top = hotspots[0] if hotspots else None

    if imp >= 40:
        verdict = f"STARTUP-DOMINATED: {imp:.0f}% of the time is imports; profile a longer steady-state run"
    elif gw >= 20:
        verdict = f"GIL-CONTENDED: {gw:.0f}% of samples wait to take the GIL; threads are fighting over it"
    elif io >= 50:
        verdict = f"I/O-BOUND: {io:.0f}% of the time waits on I/O, sleep or locks with the GIL released"
    elif held >= 60:
        verdict = (f"GIL-BOUND: {held:.0f}% of the time holds the GIL (pure Python {py:.0f}%, native "
                   f"{held - py:.0f}%); threads will not scale this on a GIL build")
    elif rel >= 50:
        verdict = f"GIL-RELEASING NATIVE: {rel:.0f}% runs in native code that releases the GIL; threads can scale"
    else:
        verdict = (f"MIXED: {held:.0f}% holds the GIL, {released:.0f}% releases it (native {rel:.0f}%, "
                   f"waits {io:.0f}%)")

    conf_held = "high" if precise_native and held >= 60 else ("medium" if held >= 40 else "low")
    recs = []

    def rec(impact, confidence, action, why):
        if impact > 0:
            recs.append({"impact": round(impact, 1), "confidence": confidence, "action": action, "why": why})

    if top and top["category"] in ("python-cpu", "native-hold") and top["share"] >= 20:
        rec(top["share"], "medium", f"Fix the algorithm first in {top['label']}",
            f"one function owns {top['share']:.0f}% of the time; a better algorithm, caching or fewer calls "
            f"beats any parallelism" + (f" ({top['ncalls']} calls)" if top.get("ncalls") else ""))
    if held >= 40:
        rec(held, conf_held, "Threads will NOT help: do not add a ThreadPoolExecutor for this hot path",
            f"{held:.0f}% of the time holds the GIL, so threads run it one at a time")
        rec(held * 0.9, conf_held, "Use processes (ProcessPoolExecutor / multiprocessing.Pool) for the hot path",
            "separate interpreters each have their own GIL; ship small arguments, load models once per worker "
            "(see python-multiprocessing-pool-designer)")
    if py >= 25:
        rec(py * 0.85, "medium", "Vectorise or compile the hot Python loop (numpy/polars, numba nogil=True, "
            "Cython with nogil, mypyc, Rust/pyo3)", f"{py:.0f}% is bytecode; native loops are 10-100x faster "
            "and can release the GIL so threads then scale")
        rec(py * 0.5, "low", "Try the free-threaded build (3.14t; supported but optional per PEP 779) with threads",
            "removes the GIL for pure-Python threads, if every extension you import supports it; check "
            "sys._is_gil_enabled() after imports")
    if released >= 30:
        rec(released, "high" if released >= 60 else "medium",
            "Threads WILL help: ThreadPoolExecutor (or the library's own thread pool) for this work",
            f"{released:.0f}% runs with the GIL released (native {rel:.0f}%, waits {io:.0f}%)")
    if io >= 30:
        rec(io * 0.95, "high" if io >= 50 else "medium",
            "Use asyncio (or threads) with bounded concurrency for the I/O waits",
            f"{io:.0f}% is waiting; overlap it (Semaphore-limited fan-out, see python-asyncio-pattern-advisor)")
    if gw >= 20:
        rec((gw + held) * 0.9, "medium", "Move the CPU-bound threads to processes (or the free-threaded build)",
            f"threads spend {gw:.0f}% waiting for the GIL and {held:.0f}% holding it: they never run in parallel")
    if gw >= 10:
        rec(gw, "medium", "Reduce GIL contention: fewer CPU threads, move CPU work out of I/O threads",
            f"{gw:.0f}% waiting for the GIL; each extra CPU-bound thread adds hand-off latency to I/O threads")
    if fam.get("re", 0) >= 10:
        rec(fam["re"] * 0.6, "medium", "Speed up regex work: precompile, merge patterns, prefilter with "
            "str methods, then parallelise with processes", f"re holds the GIL ({fam['re']:.0f}% of time)")
    json_share = fam.get("json", 0) + fam.get("fast json", 0)
    if json_share >= 10:
        rec(json_share * 0.6, "medium", "Use orjson/msgspec for JSON (several times faster, still GIL-held)",
            f"JSON parsing/serialising is {json_share:.0f}% of time")
    if fam.get("pickle", 0) >= 10:
        rec(fam["pickle"] * 0.7, "medium", "Cut pickling: send ids/paths or shared memory instead of objects",
            f"pickle is {fam['pickle']:.0f}% (typical IPC overhead of process pools)")
    if fam.get("numpy object conversion", 0) >= 10:
        rec(fam["numpy object conversion"] * 0.7, "medium",
            "Build arrays once: avoid np.array(list) / .tolist() inside loops",
            "converting Python objects to arrays holds the GIL and copies")
    if imp >= 15:
        rec(imp * 0.8, "high" if imp >= 40 else "medium",
            "Cut startup: lazy-import heavy modules, check python -X importtime, preload once per worker",
            f"imports are {imp:.0f}% of the profile")
    recs.sort(key=lambda r: -r["impact"])
    for i, r in enumerate(recs, 1):
        r["rank"] = i
    return verdict, recs


def combine(reports):
    shares = {c: round(sum(r["shares"][c] for r in reports) / len(reports), 2) for c, _ in CATEGORIES}
    fams = {}
    for r in reports:
        for f in r["families"]:
            k = (f["category"], f["family"])
            fams[k] = fams.get(k, 0.0) + f["share"] / len(reports)
    families = [{"category": c, "family": f, "share": round(v, 2)} for (c, f), v in fams.items()]
    hot = sorted((h for r in reports for h in r["hotspots"]), key=lambda h: -h["share"])
    precise = all(r["format"] == "pstats" or r["native_frames"] for r in reports)
    return shares, families, hot, precise


def bar(pct, width=30):
    n = int(round(width * max(0.0, min(pct, 100.0)) / 100.0))
    return "#" * n + "." * (width - n)


def render_text(reports, verdict, recs, top, gate):
    out = []
    for r in reports:
        unit = "s" if r["unit"] == "seconds" else " samples"
        total = f"{r['total']:.3f}s" if r["unit"] == "seconds" else f"{r['total']} samples"
        out.append(f"== {r['source']} ({r['format']}, {total}) ==")
        out.append("Share of time")
        for cat, label in CATEGORIES:
            pct = r["shares"][cat]
            if pct > 0 or cat in GIL_HELD:
                out.append(f"  {label:<42} {pct:6.1f}%  {bar(pct)}")
        out.append(f"Top {min(top, len(r['hotspots']))} hot spots (self time)")
        for i, h in enumerate(r["hotspots"][:top], 1):
            calls = f"  [{h['ncalls']} calls]" if h.get("ncalls") else ""
            amount = f"{h['self']:.4f}s" if unit == "s" else f"{h['self']}"
            out.append(f"  {i:>2}. {h['share']:5.1f}%  {h['category']:<14} {amount:>9}  {h['label']}{calls}")
        if r["threads"]:
            out.append("Per thread (samples, share of that thread)")
            for name, t in sorted(r["threads"].items(), key=lambda kv: -kv[1]["samples"]):
                parts = ", ".join(f"{c} {v:.0f}%" for c, v in sorted(t["shares"].items(), key=lambda kv: -kv[1]))
                out.append(f"  {name}: {t['samples']} samples: {parts}")
        for c in r["caveats"]:
            out.append(f"  note: {c}")
        out.append("")
    if len(reports) > 1:
        out.append("Combined shares are the mean of the sources above.")
    out.append(f"Verdict: {verdict}")
    out.append("Recommendations (ranked by expected impact)")
    if not recs:
        out.append("  (none: no bucket dominates; profile a longer or more representative run)")
    for r in recs:
        out.append(f"  {r['rank']}. [{r['confidence']}] {r['action']} (impact ~{r['impact']:.0f}% of time)")
        out.append(f"     why: {r['why']}")
    if gate is not None:
        status = "FAIL" if gate["failed"] else "PASS"
        out.append(f"Gate: {status} (pure-Python CPU {gate['python_cpu']:.1f}%, limit {gate['limit']:.1f}%)")
    return "\n".join(out)


# ----------------------------------------------------------------------------- input handling

def sniff_format(data):
    if data[:1] in (b"{", b"\xfb"):  # marshal dict type code (with or without FLAG_REF)
        return "pstats"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "pstats"
    return "collapsed"  # text; analyse_collapsed reports a clear error if it has no stack lines


def analyse_source(path, fmt):
    display = "<stdin>" if path == "-" else path
    try:
        data = sys.stdin.buffer.read() if path == "-" else open(path, "rb").read()
    except OSError as err:
        raise UsageError(f"cannot read {display}: {err.strerror or err}") from None
    if not data.strip():
        raise UsageError(f"{display}: file is empty")
    kind = sniff_format(data) if fmt == "auto" else fmt
    if kind == "collapsed":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise UsageError(f"{display}: not UTF-8 text, so not a collapsed-stack file") from None
        return analyse_collapsed(text, display)
    if path == "-":
        fd, tmp = tempfile.mkstemp(suffix=".prof")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            return analyse_pstats(tmp, display)
        finally:
            os.unlink(tmp)
    return analyse_pstats(path, display)


def _demo_workload():
    """Synthetic profile target for --demo: Python loops, regex, json, hashlib, zlib and a sleep."""
    import hashlib
    import time
    import zlib

    docs = [f"Doc {i}:  The   quick brown fox {i % 7} jumps\tover the lazy dog. " * 20 for i in range(300)]
    cleaned = [re.sub(r"\s+", " ", d) for d in docs]
    tokens = 0
    for d in cleaned:
        for word in d.split(" "):
            tokens += sum(1 for ch in word if ch.isalpha())
    payload = json.dumps([{"id": i, "text": d[:80], "score": i / 3} for i, d in enumerate(cleaned)])
    for _ in range(5):
        json.loads(payload)
    blob = "".join(cleaned).encode()
    hashlib.sha256(blob * 20).hexdigest()
    zlib.compress(blob * 5)
    time.sleep(0.02)
    return tokens


def run_demo():
    import cProfile

    fd, tmp = tempfile.mkstemp(suffix=".prof")
    os.close(fd)
    try:
        prof = cProfile.Profile()
        prof.enable()
        _demo_workload()
        prof.disable()
        prof.dump_stats(tmp)
        report = analyse_pstats(tmp, "<demo workload profiled with cProfile>")
    finally:
        os.unlink(tmp)
    return report


def build_parser():
    p = argparse.ArgumentParser(
        prog="profile_classify.py",
        description="Classify a cProfile/pstats file or py-spy/perf collapsed stacks into pure-Python CPU, "
                    "GIL-holding native, GIL-releasing native, I/O wait, GIL wait and import time, then "
                    "recommend threads, processes, vectorisation, asyncio or the free-threaded build. Static: "
                    "never runs the profiled code (only --demo runs a built-in synthetic workload).",
        epilog="Exit codes: 0 analysed, 1 --fail-if-python-cpu-over gate failed, 2 usage/read/load error. "
               "Record inputs with: python -m cProfile -o out.prof app.py | "
               "py-spy record --format raw -o stacks.txt [--native] [--threads] [--idle] -- python app.py")
    p.add_argument("paths", nargs="*", help="pstats .prof files and/or collapsed-stack text files ('-' = stdin)")
    p.add_argument("--collapsed", action="append", default=[], metavar="FILE",
                   help="force FILE to be read as collapsed stacks (repeatable)")
    p.add_argument("--format", choices=["auto", "pstats", "collapsed"], default="auto",
                   help="format of the positional paths (default: sniff the content)")
    p.add_argument("--top", type=int, default=10, metavar="N", help="hot spots to show per source (default 10)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p.add_argument("--fail-if-python-cpu-over", type=float, metavar="PCT",
                   help="CI gate: exit 1 if pure-Python CPU share exceeds PCT percent")
    p.add_argument("--demo", action="store_true",
                   help="profile a built-in synthetic workload with this interpreter and analyse it "
                        "(portable check of the pstats path)")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be >= 1")
    gate_pct = args.fail_if_python_cpu_over
    if gate_pct is not None and not 0 <= gate_pct <= 100:
        parser.error("--fail-if-python-cpu-over must be between 0 and 100")
    if not args.paths and not args.collapsed and not args.demo:
        parser.error("give at least one profile file, '-', --collapsed FILE or --demo")
    if sum(1 for p in args.paths + args.collapsed if p == "-") > 1:
        parser.error("stdin ('-') can only be used once")
    try:
        reports = [run_demo()] if args.demo else []
        reports += [analyse_source(p, args.format) for p in args.paths]
        reports += [analyse_source(p, "collapsed") for p in args.collapsed]
    except UsageError as err:
        print(f"profile_classify.py: error: {err}", file=sys.stderr)
        return EXIT_ERROR
    shares, families, hot, precise = combine(reports)
    verdict, recs = recommend(shares, families, hot, precise)
    gate = None
    if gate_pct is not None:
        gate = {"limit": gate_pct, "python_cpu": shares["python-cpu"], "failed": shares["python-cpu"] > gate_pct}
    if args.json:
        for r in reports:
            r["hotspots"] = r["hotspots"][:args.top]
        print(json.dumps({"sources": reports, "combined": {"shares": shares, "verdict": verdict,
                                                           "recommendations": recs}, "gate": gate}, indent=2))
    else:
        print(render_text(reports, verdict, recs, args.top, gate))
    return EXIT_GATE if gate and gate["failed"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
