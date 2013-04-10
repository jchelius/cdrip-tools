#!/usr/bin/python
from __future__ import print_function
import os, sys, signal

import utils

from subprocess import Popen,  PIPE
from argparse import ArgumentParser
from os.path import isfile, basename, dirname, exists, splitext, join, abspath

BIN = {'metaflac': None,
       'ffprobe': 'avprobe',
       'sox': None,
       'splitaudio': None,
       }

PROGNAME = 'fixoffset'
VERSION = '0.1'
REQUIRED = ['ffprope', 'sox', 'splitaudio']
PROCS = []
TEMPDIRS = []

def process_arguments():
    parser = \
        ArgumentParser(description='Fix sample offsets of CD rips.',
                       prog=PROGNAME)
    parser.add_argument('offset', help='offset to correct', type=int)
    parser.add_argument('paths', metavar='file', nargs='+',
                        help='lossless audio file')
    parser.add_argument('-f', '--format',
                        default='wav',
                        choices=['wav', 'flac'],
                        help='format of generated output file(s)')

    utils.add_common_arguments(parser, VERSION)

    return parser.parse_args()

def fix_offset(sources, offset, fmt='wav', verbose=False):
    output_dir = None
    i = 0
    while not output_dir:
        a = '_%i' % i if i > 0 else ''
        output_dir = abspath(join(dirname(sources[0]['path']),
                                  'fixedoffset_%i%s' % (offset, a)))
        if exists(output_dir):
            output_dir = None
        i += 1
    TEMPDIRS.append(output_dir)
    os.mkdir(output_dir)
    common_args = ['-t', 'raw',
                   '-b16',
                   '-c2',
                   '-r44100',
                   '-e', 'signed-integer',
                   '-',
                   ]
    sox_args = [BIN['sox']]+[s['path'] for s in sources]+common_args

    total_samples = sum([s['num_samples'] for s in sources])
    if offset > 0:
        sox_args += ['pad', '0', '%is' % offset,
                     'trim', '%is' % offset, '%is' % total_samples]
    else:
        sox_args += ['pad', '%is' % -offset, '0',
                     'trim', '0', '%is' % total_samples]

    splitaudio_args = [BIN['splitaudio'], '1' if fmt is 'flac' else '0']

    for s in sources:
        splitaudio_args += [str(s['num_samples'])]

    if verbose:
        print('%s | %s' % (' '.join(sox_args), ' '.join(splitaudio_args)))
    PROCS.append(Popen(sox_args, stdout=PIPE))
    PROCS.append(Popen(splitaudio_args, stdin=PROCS[-1].stdout, cwd=output_dir))

    p = PROCS[-1]
    while p.poll() is None:
        utils.show_status('Fixing offset (%i samples)', offset)

    out, err = p.communicate()
    print('', file=sys.stderr, end='\n')
    if p.returncode != 0:
        raise utils.SoxError('sox had an error (returned %i)' % p.returncode)

    TEMPDIRS.remove(output_dir)
    for i, s in enumerate(sources):
        src = join(output_dir, 'fixed%03i.wav' % i)
        outpath = join(output_dir, splitext(basename(s['path']))[0]+'.wav')
        os.rename(src, outpath)

    return output_dir

def print_summary(sources, output_dir):
    s = 's' if len(sources) > 1 else ''
    print('Fixed file%s saved to directory %s' % (s, output_dir))

def main():
    utils.check_dependencies(BIN, REQUIRED)
    ns = process_arguments()
    sources = [dict(path=p) for p in ns.paths if isfile(p)]
    total = len(sources)
    if total == 0:
        raise utils.InvalidFilesError('Please provide valid input files')

    for s in sources:
        s['num_samples'] = utils.get_num_samples(BIN, s['path'])
        if s['num_samples'] % 588 != 0:
            msg = "%s not from CD (%i samples)\n" % (s['path'],
                                                     s['num_samples'])
            raise utils.NotFromCDError(msg)
    output_dir = fix_offset(sources, ns.offset, ns.format, ns.verbose)
    print_summary(sources, output_dir)

    return 0

if __name__ == '__main__':
    utils.execute(main, PROCS, tempdirs=TEMPDIRS)