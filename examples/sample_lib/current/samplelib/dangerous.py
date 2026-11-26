import subprocess


def calc(expr: str):
    """PLANTED bandit issue: eval of untrusted input."""
    return eval(expr)


def run_shell(cmd: str) -> int:
    """PLANTED bandit issue: shell=True with a non-literal command."""
    return subprocess.call(cmd, shell=True)
