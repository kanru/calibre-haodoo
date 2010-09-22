# Copyright (C) 2010  Kan-Ru Chen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__license__   = 'GPL v3'
__copyright__ = '2010, Kan-Ru Chen <kanru@kanru.info>'

import os

from calibre import prepare_string_for_xml
from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.pdb import MREADER
from calibre.ebooks.pdb import PDBError, FORMAT_READERS, FORMAT_WRITERS, IDENTITY_TO_NAME
from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.ebooks.txt.processor import opf_writer, HTML_TEMPLATE


BPDB_IDENT = 'BOOKMTIT'
UPDB_IDENT = 'BOOKMTIU'

punct_table = {
    u"︵": u"（",
    u"︶": u"）",
    u"︷": u"｛",
    u"︸": u"｝",
    u"︹": u"〔",
    u"︺": u"〕",
    u"︻": u"【",
    u"︼": u"】",
    u"︗": u"〖",
    u"︘": u"〗",
    u"﹇": u"［］",
    u"﹈": u"［］",
    u"︽": u"《",
    u"︾": u"》",
    u"︿": u"〈",
    u"﹀": u"〉",
    u"﹁": u"「",
    u"﹂": u"」",
    u"﹃": u"『",
    u"﹄": u"』",
    u"｜": u"—",
    u"︙": u"…",
    u"ⸯ": u"～",
    }

def fix_punct(line):
    for (key, value) in punct_table.items():
        line = line.replace(key, value)
    return line

class LegacyHeaderRecord(object):

    def __init__(self, raw):
        fields = raw.lstrip().replace('\x1b\x1b\x1b', '\x1b').split('\x1b')
        self.title = fields[0].decode('cp950', 'replace')
        self.num_records = int(fields[1])
        self.chapter_titles = map(lambda x: x.decode('cp950', 'replace'), fields[2:])

class UnicodeHeaderRecord(object):

    def __init__(self, raw):
        fields = raw.lstrip().replace('\x1b\x00\x1b\x00\x1b\x00', '\x1b\x00').split('\x1b\x00')
        self.title = fields[0].decode('utf_16_le', 'ignore')
        self.num_records = int(fields[1])
        self.chapter_titles = map(lambda x: x.decode('utf_16_le', 'replace'), fields[2].split('\r\x00\n\x00'))

class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.stream = stream
        self.log = log
        self.single_line_paras = options.single_line_paras
        self.print_formatted_paras = options.print_formatted_paras

        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        if header.ident == BPDB_IDENT:
            self.header_record = LegacyHeaderRecord(self.section_data(0))
            self.encoding = 'cp950'
        else:
            self.header_record = UnicodeHeaderRecord(self.section_data(0))
            self.encoding = 'utf_16_le'

    def section_data(self, number):
        return self.sections[number]

    def decompress_text(self, number):
        return self.section_data(number).decode(self.encoding, 'replace')

    def extract_content(self, output_dir):
        txt = ''

        self.log.info('Decompressing text...')
        for i in range(1, self.header_record.num_records + 1):
            self.log.debug('\tDecompressing text section %i' % i)
            title = self.header_record.chapter_titles[i-1]
            txt += u'<h1>' + title + u'</h1>' + u'\n'
            lines = []
            for line in self.decompress_text(i).splitlines():
                line = line.strip()
                line = prepare_string_for_xml(line)
                line = fix_punct(line)
                lines.append(u'<p>%s</p>' % line)
            txt += '\n'.join(lines)

        self.log.info('Converting text to OEB...')
        html = HTML_TEMPLATE % (self.header_record.title, txt)
        with open(os.path.join(output_dir, 'index.html'), 'wb') as index:
            index.write(html.encode('utf-8'))

        mi = MetaInformation(None, [_('Unknown')])
        mi.title = self.header_record.title
        manifest = [('index.html', None)]
        spine = ['index.html']
        opf_writer(output_dir, 'metadata.opf', manifest, spine, mi)

        return os.path.join(output_dir, 'metadata.opf')

def get_Haodoo(stream, extract_cover=True):
    mi = MetaInformation(None, [_('Unknown')])
    stream.seek(0)

    header = PdbHeaderReader(stream)

    if header.ident == BPDB_IDENT:
        hr = LegacyHeaderRecord(header.section_data(0))
    else:
        hr = UnicodeHeaderRecord(header.section_data(0))

    mi.title = hr.title
    
    return mi

class HaoDooPdb(InputFormatPlugin):

    name                = 'HaoDoo PDB Plugin'
    description         = 'Add HaoDoo PDB/uPDB support to core PDB plugin'
    supported_platforms = ['windows', 'osx', 'linux']
    author              = 'Kan-Ru Chen <kanru@kanru.info>'
    file_types          = set(['updb'])
    version             = (0, 2, 0)

    def initialize(self):
        FORMAT_READERS[BPDB_IDENT] = Reader
        FORMAT_READERS[UPDB_IDENT] = Reader
        IDENTITY_TO_NAME[BPDB_IDENT] = 'HaoDoo.net'
        IDENTITY_TO_NAME[UPDB_IDENT] = 'HaoDoo.net'
        MREADER[BPDB_IDENT] = get_Haodoo
        MREADER[UPDB_IDENT] = get_Haodoo

    def convert(self, stream, options, file_ext, log, accelerators):
        header = PdbHeaderReader(stream)
        if header.ident != UPDB_IDENT:
            raise PDBError('Not a Haodoo UPDB format')
        reader = Reader(header, stream, log, options)
        opf = reader.extract_content(os.getcwd())

        return opf
