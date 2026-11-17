from streamdl.process import describe_exit


def test_describe_exit():
    assert describe_exit(0) == "exit status 0"
    assert describe_exit(1) == "exit status 1"
    assert describe_exit(-9) == "signal: killed"
    assert describe_exit(-2) == "signal: interrupt"
    assert describe_exit(-34) == "signal: signal 34"
    assert describe_exit(-70) == "signal: signal 70"
