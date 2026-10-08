#!/usr/bin/env python3
"""Offline STT readiness. Optional local audio smoke; never installs or downloads."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import socket

MODEL_FILES = ('model.bin', 'config.json', 'tokenizer.json', 'preprocessor_config.json')


def readiness(model_dir):
    root = Path(model_dir).expanduser().resolve()
    missing = []
    if importlib.util.find_spec('faster_whisper') is None:
        missing.append('faster_whisper')
    for name in MODEL_FILES:
        path = root / name
        if not path.is_file() or not path.stat().st_size:
            missing.append(name)
    return {'ready': not missing, 'missing': missing, 'transcription': 'NOT_RUN'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', required=True, type=Path,
                        help='Existing converted faster-whisper model directory, not a model ID')
    parser.add_argument('--audio', type=Path)
    parser.add_argument('--transcribe', action='store_true')
    parser.add_argument('--non-sensitive', action='store_true', help='Confirm approved non-sensitive audio')
    parser.add_argument('--expect', help='Expected spoken phrase (case/punctuation insensitive)')
    args = parser.parse_args(argv)
    if any((args.audio, args.transcribe, args.non_sensitive, args.expect)) and not all(
            (args.audio, args.transcribe, args.non_sensitive, args.expect and args.expect.strip())):
        parser.error('Audio requires --audio, --transcribe, --non-sensitive and --expect together')
    report = readiness(args.model_dir)
    print(json.dumps(report))
    if not report['ready']:
        return 2
    if not args.transcribe:
        return 0
    if not args.audio.is_file():
        parser.error('Audio file does not exist')
    # Avoid Hermes transcription dispatch: that path can lazy-install or fall back.
    # Explicit local path + local_files_only plus socket denial is defense in depth.
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    def deny_network(*unused, **kwargs):
        raise RuntimeError('Network disabled for local STT smoke')
    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    socket.create_connection = deny_network
    from faster_whisper import WhisperModel
    model = WhisperModel(str(args.model_dir.expanduser().resolve()), device='cpu',
                         compute_type='int8', local_files_only=True, cpu_threads=2)
    segments, _ = model.transcribe(str(args.audio.resolve()), beam_size=1)
    text = ' '.join(segment.text for segment in segments)
    normalize = lambda value: ' '.join(re.findall(r'\w+', value.casefold()))
    expected = normalize(args.expect)
    passed = bool(expected) and expected in normalize(text)
    # Do not persist a recording or transcript in the receipt.
    print(json.dumps({'transcription': 'PASS' if passed else 'FAIL', 'expected_phrase_matched': passed}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
