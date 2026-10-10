"""Bounded read-only source leads; never execute/import project code."""
import argparse
import json
import os
from pathlib import Path
import re

PRUNE={'.git','.worktrees','node_modules','.dart_tool','.venv','venv','build','dist','vendor','Pods','__pycache__','coverage'}
EXTENSIONS={'.py','.dart','.ts','.tsx','.js','.jsx','.go','.rs','.java','.kt','.swift','.svelte'}
GENERATED=('.g.dart','.freezed.dart','.gen.dart','.generated.ts','.pb.go','.min.js')
MARKER=re.compile(r'^\s*(?:#|//|/\*|\*)\s*(TODO|FIXME|HACK|XXX)\b',re.I)

def scan(root, paths, max_files=500, limit=30):
    root=Path(root).expanduser().resolve(strict=True)
    if not root.is_dir() or max_files<1 or limit<1:raise ValueError('Directory and positive budgets required')
    selected=[]
    for value in paths:
        relative=Path(value)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise ValueError('Choose root-relative implementation paths without ..')
        source=root/relative
        if source.is_symlink():raise ValueError('Do not scan symlink roots')
        resolved=source.resolve(strict=True)
        if not resolved.is_relative_to(root):raise ValueError('Source path escapes workspace')
        selected.append(resolved)
    markers=[];modules=[];seen=set();visited=0;scanned=0;truncated=False;skipped=0
    for source in selected:
        walk=os.walk(source,followlinks=False) if source.is_dir() else [(str(source.parent),[],[source.name])]
        for directory,dirs,files in walk:
            dirs[:]=sorted(d for d in dirs if d not in PRUNE and not d.startswith('.') and not (Path(directory)/d).is_symlink())
            for name in sorted(files):
                path=Path(directory)/name
                if path in seen:continue
                seen.add(path);visited+=1
                if visited>10000:truncated=True;break
                if path.is_symlink() or path.suffix not in EXTENSIONS or name.endswith(GENERATED) or re.fullmatch(r'app_localizations(?:_[a-z_]+)?\.dart',name):continue
                if scanned>=max_files:truncated=True;break
                if path.stat().st_size>524288:skipped+=1;continue
                try:lines=path.read_text(encoding='utf-8').splitlines()
                except (OSError,UnicodeError):skipped+=1;continue
                scanned+=1;relative=path.relative_to(root).as_posix()
                modules.append({'path':relative,'lines':len(lines),'lead_only':True})
                for index,line in enumerate(lines,1):
                    match=MARKER.match(line)
                    if match:markers.append({'path':relative,'line':index,'marker':match.group(1).upper(),'lead_only':True})
            if truncated:break
        if truncated:break
    return {'workspace':str(root),'paths':list(paths),'files_scanned':scanned,'scan_truncated':truncated,
            'skipped_large_or_unreadable':skipped,'marker_count':len(markers),'markers':markers[:limit],
            'markers_omitted':max(0,len(markers)-limit),
            'largest_modules':sorted(modules,key=lambda m:(-m['lines'],m['path']))[:min(limit,10)],
            'interpretation':'Leads only. Markers and file length prove neither a bug nor a worthwhile refactor. Verify behavior, callers, ownership and milestone payoff.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('workspace');p.add_argument('--path',action='append',required=True)
    p.add_argument('--max-files',type=int,default=500);p.add_argument('--limit',type=int,default=30)
    a=p.parse_args();print(json.dumps(scan(a.workspace,a.path,a.max_files,a.limit),indent=2))
