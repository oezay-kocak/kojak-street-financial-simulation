"""Abruptly terminate only the calling test child, without native DLL cleanup."""
import ctypes
import os


def crash_exit(code: int = 91) -> None:
    if os.name == "nt":
        # CRT _exit can still enter native DLL detach on Windows. A kernel
        # termination is the intended hard-crash experiment, including when
        # an SQL owner/background thread is active. It never closes the DB.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        kernel.TerminateProcess.restype = ctypes.c_int
        if not kernel.TerminateProcess(kernel.GetCurrentProcess(), code):
            raise ctypes.WinError(ctypes.get_last_error())
    os._exit(code)
