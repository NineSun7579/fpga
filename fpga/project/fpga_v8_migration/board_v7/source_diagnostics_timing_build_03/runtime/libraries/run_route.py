"""Local guard bridge for the local raw parser only."""
from preflight import DATA, load, sha
from physical_flow import snapshot
def guards():return {p:sha(p) for p in load(DATA/'protected_guard.json')}
def inputs():return snapshot()
