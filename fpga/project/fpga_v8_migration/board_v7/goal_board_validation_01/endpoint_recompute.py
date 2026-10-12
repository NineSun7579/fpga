"""Offline pure graph recomputation; never import controller/PDS entry points."""
import ast
from pathlib import Path

ROLES = {
    'endpoint_graph': 'analysis_tools/graph_adapter.py',
    'endpoint_logic': 'libraries/endpoint_logic.py',
    'endpoint_parameters': 'libraries/endpoint_detail.py',
    'endpoint_checker': 'libraries/endpoints.py',
}


def recompute(graph, sources, root, require, sha):
    scopes = {}
    for role, relative in ROLES.items():
        path = root / relative
        require(sources.get(role) == path.resolve(), 'Unexpected endpoint audit source: ' + role)
        tree = ast.parse(path.read_bytes(), filename=str(path))
        # Imports and module initialization can alter runtime state. Execute only
        # pure definitions and ordinary stdlib imports used by these functions.
        nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        if role == 'endpoint_parameters':
            nodes = [n for n in nodes if n.name == 'parameters']
        import itertools
        import re
        scope = {'re': re, 'itertools': itertools, 'Path': Path, 'sha': sha,
                 '__file__': str(path)}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
        scopes[role] = scope
    checker = scopes['endpoint_checker']
    checker.update({k: scopes['endpoint_graph'][k] for k in ('Resolver', 'classify', 'canon')})
    checker.update(parameters=scopes['endpoint_parameters']['parameters'],
                   evaluate=scopes['endpoint_logic']['evaluate'], require=require)
    proof = checker['full_top_audit']('routed', graph, lambda *args: None)
    require(len(proof['rows']) == len({r['cell'] for r in proof['rows']}) == 60,
            'Current routed independent60 recomputation failed')
    for row in proof['rows']:
        primitive = graph['primitives'][row['cell']]
        require(primitive['type'].startswith(('GTP_DFF', 'gopQ_Cell_')),
                'Unsupported independent endpoint primitive: ' + primitive['type'])
        if primitive['type'].startswith('gopQ_Cell_'):
            require(row['parameters_decoded'].get('LATCH_EN') == 'FALSE' and
                    row['parameters_decoded'].get('IMPL_MODE') == 'Q',
                    'Unsupported latch/packed implementation of independent endpoint')
        require(row['D'].endswith('/D') and row['CLK'].endswith('/CLK') and
                row['reset'].endswith(('/RS', '/P', '/C')),
                'Unsupported actual DCLK/reset endpoint form')
    return proof
