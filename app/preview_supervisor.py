"""Trusted parent-death watchdog for one owned, already-confined preview process."""
import os
import resource
import signal
import subprocess
import sys
import time


def main():
    parent, descriptor = int(sys.argv[1]), int(sys.argv[2])
    process = None
    stop = False
    def cancel(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024, 256 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (900, 900))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        listener = int(os.environ['PERSONAL_CODEX_LISTEN_FD'])
        process = subprocess.Popen(sys.argv[3:], start_new_session=True, pass_fds=(listener,))
        os.close(listener)
        os.write(descriptor, str(process.pid).encode() + b'\n')
        os.close(descriptor)
        descriptor = -1
        deadline = time.monotonic() + 900
        while process.poll() is None:
            if stop or os.getppid() != parent or time.monotonic() >= deadline:
                return 130
            time.sleep(.1)
        return process.returncode
    finally:
        if descriptor >= 0: os.close(descriptor)
        if process is not None:
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                try: os.killpg(process.pid, 0)
                except ProcessLookupError: break
                time.sleep(.05)
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()


if __name__ == '__main__': sys.exit(main())
