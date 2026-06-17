# Compiled once at import time. The DB CHECK uses the same expression.
import re


TENANT_CODE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
