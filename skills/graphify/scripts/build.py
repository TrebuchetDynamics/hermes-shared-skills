"""Build a fresh Graphify code graph without semantic/labeling model calls."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def build(source, output_root, binary=None):
    source = Path(source).resolve(strict=True)
    output_root = Path(output_root).resolve()
    if not source.is_dir():
        raise ValueError('Source must be an authorized project directory')
    if output_root == source or source in output_root.parents:
        raise ValueError('Use an output root outside the scanned project')
    graph_dir = output_root / 'graphify-out'
    if graph_dir.exists() or graph_dir.is_symlink():
        raise ValueError('Existing graph output: choose a fresh output root; no overwrite')
    binary = binary or shutil.which('graphify')
    if not binary:
        raise RuntimeError('Missing CLI: install the official graphifyy package')
    output_root.mkdir(parents=True, exist_ok=True)
    subprocess.run([binary, 'extract', str(source), '--code-only', '--no-cluster',
                    '--max-workers', '2', '--out', str(output_root)], check=True,
                   cwd=output_root)
    subprocess.run([binary, 'cluster-only', str(output_root), '--no-label'],
                   check=True, cwd=output_root)
    required = ['graph.json', 'GRAPH_REPORT.md', 'graph.html']
    if any(not (graph_dir / name).is_file() or (graph_dir / name).stat().st_size == 0
           for name in required):
        raise RuntimeError('Missing or empty expected graph/report/HTML artifacts')
    graph = json.loads((graph_dir / 'graph.json').read_text())
    nodes = graph.get('nodes')
    edges = graph.get('links', graph.get('edges'))
    if not isinstance(nodes, list) or not nodes or not isinstance(edges, list):
        raise RuntimeError('Empty or unsupported graph: inspect extraction coverage')
    return {'graph': str(graph_dir / 'graph.json'), 'nodes': len(nodes),
            'edges': len(edges), 'metadata': graph.get('graph', {}),
            'mode': 'local_code_only_no_llm_labels'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output_root), indent=2))


if __name__ == '__main__':
    main()
