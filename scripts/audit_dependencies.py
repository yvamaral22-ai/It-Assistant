"""Audit production dependencies using the trusted certificate store from Windows."""

import runpy
import sys

import truststore


def main() -> None:
    truststore.inject_into_ssl()
    sys.argv = ["pip-audit", "-r", "requirements.txt"]
    runpy.run_module("pip_audit", run_name="__main__")


if __name__ == "__main__":
    main()
