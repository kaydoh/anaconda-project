# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2017, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import platform
import pytest

import anaconda_project.internal.streaming_popen as streaming_popen
from anaconda_project.internal.test.tmpfile_utils import tmp_script_commandline


def add_lineseps(lines):
    return list(map(lambda l: l + os.linesep, lines))


def test_streaming():
    print_stuff = tmp_script_commandline(u"""# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import time

def flush():
    time.sleep(0.05)
    sys.stdout.flush()
    sys.stderr.flush()

print("a")
flush()
print("x", file=sys.stderr)
flush()
print("b")
flush()
print("y", file=sys.stderr)
flush()
print("c")
flush()
print("z", file=sys.stderr)
flush()
print("d")
flush()
# print partial lines with multiple syscalls
for i in [1,2,3,4,5,6]:
  sys.stdout.write("%d" % i)
sys.stdout.write("\\n")
# print unicode stuff
print("💯 🌟")
flush()
# print many lines at once, and end on non-newline
sys.stdout.write("1\\n2\\n3\\n4\\n5\\n6")
flush()

sys.exit(2)
""")

    stdout_from_callback = []

    def on_stdout(data):
        stdout_from_callback.append(data)

    stderr_from_callback = []

    def on_stderr(data):
        stderr_from_callback.append(data)

    (p, out_lines, err_lines) = streaming_popen.popen(print_stuff, on_stdout, on_stderr)

    expected_out = add_lineseps([u'a', u'b', u'c', u'd', u'123456', u'💯 🌟', u'1', u'2', u'3', u'4', u'5'])
    if platform.system() == 'Windows':
        # Windows can't output unicode
        expected_out[5] = u"\\U0001f4af \\U0001f31f"

    expected_out.append('6')  # no newline after this one
    expected_err = add_lineseps([u'x', u'y', u'z'])

    assert expected_out == out_lines
    assert "".join(expected_out) == "".join(stdout_from_callback)

    assert expected_err == err_lines
    assert "".join(expected_err) == "".join(stderr_from_callback)

    assert p.returncode is 2


def test_bad_utf8():
    print_bad = tmp_script_commandline(u"""# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import sys

print("hello")
sys.stdout.flush()
# write some garbage
os.write(sys.stdout.fileno(), b"\\x42\\xff\\xef\\xaa\\x00\\x01\\xcc")
sys.stdout.flush()
print("goodbye")
sys.stdout.flush()

sys.exit(0)
""")

    stdout_from_callback = []

    def on_stdout(data):
        stdout_from_callback.append(data)

    stderr_from_callback = []

    def on_stderr(data):
        stderr_from_callback.append(data)

    (p, out_lines, err_lines) = streaming_popen.popen(print_bad, on_stdout, on_stderr)

    expected_out = add_lineseps([u'hello', u'B��\x00\x01�goodbye'])
    expected_err = []

    assert expected_out == out_lines
    assert expected_err == err_lines

    assert "".join(expected_out) == "".join(stdout_from_callback)
    assert "".join(expected_err) == "".join(stderr_from_callback)


def test_callbacks_are_none():
    print_stuff = tmp_script_commandline(u"""# -*- coding: utf-8 -*-
from __future__ import print_function
import sys

print("a")
print("b", file=sys.stderr)

sys.exit(0)
""")

    (p, out_lines, err_lines) = streaming_popen.popen(print_stuff, None, None)

    expected_out = add_lineseps(['a'])
    expected_err = add_lineseps(['b'])

    assert expected_out == out_lines
    assert expected_err == err_lines

    assert p.returncode is 0


def test_io_error(monkeypatch):
    print_hello = tmp_script_commandline("""from __future__ import print_function
import os
import sys

print("hello")
sys.stdout.flush()

sys.exit(0)
""")

    stdout_from_callback = []

    def on_stdout(data):
        stdout_from_callback.append(data)

    stderr_from_callback = []

    def on_stderr(data):
        stderr_from_callback.append(data)

    def mock_read(*args, **kwargs):
        raise IOError("Nope")

    monkeypatch.setattr("anaconda_project.internal.streaming_popen._read_from_stream", mock_read)

    with pytest.raises(IOError) as excinfo:
        streaming_popen.popen(print_hello, on_stdout, on_stderr)

    assert "Nope" in str(excinfo.value)
