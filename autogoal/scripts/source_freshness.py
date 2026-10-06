#!/usr/bin/env python3
"""Bounded source fingerprints for selection freshness, not acceptance or ownership."""
import argparse
import hashlib
import json
import re
from pathlib import Path

MAX_FILES=32
MAX_BYTES=8*1024*1024


def _fingerprint(root, name):
    rel=Path(name)
    if not isinstance(name,str) or not name or rel.is_absolute() or '..' in rel.parts or str(rel)=='.':
        raise ValueError('Use explicit root-relative file paths without ..')
    if any(part=='.git' for part in rel.parts) or rel.name in {'auth.json','credentials.json'} or rel.suffix in {'.pem','.key'} or (rel.name.startswith('.env') and rel.name not in {'.env.example','.env.sample','.env.template'}):
        raise ValueError('Do not fingerprint credentials or Git internals')
    path=root
    for part in rel.parts:
        path=path/part
        if path.is_symlink():raise ValueError('Do not fingerprint symlink paths')
    if not path.exists():return {'path':name,'sha256':None}
    if not path.is_file():raise ValueError('Select files, not directory trees')
    with path.open('rb') as stream:
        data=stream.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise ValueError('Selected source exceeds fingerprint byte budget')
    return {'path':name,'sha256':hashlib.sha256(data).hexdigest()}


def capture(root, paths):
    root=Path(root).resolve(strict=True)
    if not root.is_dir() or not 1<=len(paths)<=MAX_FILES:
        raise ValueError('Choose between 1 and 32 explicit evidence files')
    if len(set(paths))!=len(paths):raise ValueError('Duplicate evidence paths')
    return {'version':1,'workspace':str(root),'files':[_fingerprint(root,p) for p in paths],
            'boundary':'Fingerprints only; not proof of unresolved work, ownership, approval or tests'}


def check(snapshot, root):
    root=Path(root).resolve(strict=True)
    if snapshot.get('version')!=1 or snapshot.get('workspace')!=str(root):
        raise ValueError('Source snapshot belongs to a different workspace or format')
    files=snapshot.get('files')
    if not isinstance(files,list) or not 1<=len(files)<=MAX_FILES:
        raise ValueError('Invalid evidence file count')
    names=[]
    for row in files:
        if not isinstance(row,dict) or set(row)!={'path','sha256'}:raise ValueError('Invalid evidence row')
        digest=row['sha256']
        if digest is not None and (not isinstance(digest,str) or re.fullmatch('[0-9a-f]{64}',digest) is None):
            raise ValueError('Invalid source fingerprint')
        names.append(row['path'])
    current=capture(root,names)
    changed=[old['path'] for old,new in zip(files,current['files']) if old!=new]
    return {'fresh':not changed,'changed':changed,'files_checked':len(files),
            'boundary':'Unchanged fingerprints do not prove this task is still necessary'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    a=sub.add_parser('capture');a.add_argument('workspace');a.add_argument('--path',action='append',required=True)
    a=sub.add_parser('check');a.add_argument('snapshot');a.add_argument('--workspace',required=True)
    args=parser.parse_args()
    try:
        if args.action=='capture':result=capture(args.workspace,args.path)
        else:result=check(json.loads(Path(args.snapshot).read_text()),args.workspace)
    except (ValueError,OSError,TypeError,KeyError) as error:parser.exit(2,str(error)+'\n')
    print(json.dumps(result,indent=2))
    if args.action=='check' and not result['fresh']:raise SystemExit(1)

if __name__=='__main__':main()
