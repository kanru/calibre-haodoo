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

import os, struct

import calibre.ebooks.pdb.input
import calibre.customize.builtins

from calibre import prepare_string_for_xml
from calibre.ebooks.metadata import MetaInformation
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
    u"│": u"…",
    u"￤": u"…",
    u"　": u"  ",
    }

def fix_punct(line):
    for (key, value) in punct_table.items():
        line = line.replace(key, value)
    return line

class LegacyHeaderRecord(object):

    def __init__(self, raw):
        fields = raw.lstrip().replace('\x1b\x1b\x1b', '\x1b').split('\x1b')
        self.title = fix_punct(fields[0].decode('cp950', 'replace'))
        self.num_records = int(fields[1])
        self.chapter_titles = map(
            lambda x: fix_punct(x.decode('cp950', 'replace').rstrip('\x00')),
            fields[2:])

class UnicodeHeaderRecord(object):

    def __init__(self, raw):
        fields = raw.lstrip().replace('\x1b\x00\x1b\x00\x1b\x00', '\x1b\x00').split('\x1b\x00')
        self.title = fix_punct(fields[0].decode('utf_16_le', 'ignore'))
        self.num_records = int(fields[1])
        self.chapter_titles = map(
            lambda x: fix_punct(x.decode('utf_16_le', 'replace').rstrip('\x00')),
            fields[2].split('\r\x00\n\x00'))

class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.stream = stream
        self.log = log

        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        if header.ident == BPDB_IDENT:
            self.header_record = LegacyHeaderRecord(self.section_data(0))
            self.encoding = 'cp950'
        else:
            self.header_record = UnicodeHeaderRecord(self.section_data(0))
            self.encoding = 'utf_16_le'

    def author(self):
        self.stream.seek(35)
        version = struct.unpack('>b', self.stream.read(1))[0]
        if version == 2:
            self.stream.seek(0)
            author = self.stream.read(35).rstrip('\x00').decode(self.encoding, 'replace')
            return author
        else:
            return u'Unknown'

    def get_metadata(self):
        mi = MetaInformation(self.header_record.title,
                             [self.author()])
        mi.language = 'zh-tw'

        return mi

    def section_data(self, number):
        return self.sections[number]

    def decompress_text(self, number):
        return self.section_data(number).decode(self.encoding, 'replace').rstrip('\x00')

    def extract_content(self, output_dir):
        txt = ''

        self.log.info('Decompressing text...')
        for i in range(1, self.header_record.num_records + 1):
            self.log.debug('\tDecompressing text section %i' % i)
            title = self.header_record.chapter_titles[i-1]
            lines = []
            title_added = False
            for line in self.decompress_text(i).splitlines():
                line = fix_punct(line)
                line = line.strip()
                if not title_added and title in line:
                    line = u'<h1 class="chapter">' + line + u'</h1>\n'
                    title_added = True
                else:
                    line = prepare_string_for_xml(line)
                lines.append(u'<p>%s</p>' % line)
            if not title_added:
                lines.insert(0, u'<h1 class="chapter">' + title + u'</h1>\n')
            txt += '\n'.join(lines)

        self.log.info('Converting text to OEB...')
        html = HTML_TEMPLATE % (self.header_record.title, txt)
        with open(os.path.join(output_dir, 'index.html'), 'wb') as index:
            index.write(html.encode('utf-8'))

        mi = self.get_metadata()
        manifest = [('index.html', None)]
        spine = ['index.html']
        opf_writer(output_dir, 'metadata.opf', manifest, spine, mi)

        return os.path.join(output_dir, 'metadata.opf')

class HaoDooPdb(calibre.ebooks.pdb.input.PDBInput,
                calibre.customize.builtins.PDBMetadataReader):

    name                = 'HaoDoo PDB Plugin'
    description         = 'Add HaoDoo PDB/uPDB support to core PDB plugin'
    supported_platforms = ['windows', 'osx', 'linux']
    author              = 'Kan-Ru Chen <kanru@kanru.info>'
    file_types          = set(['pdb', 'updb'])
    version             = (0, 4, 1)
    priority            = 10

    def initialize(self):
        pass

    def get_metadata(self, stream, ftype):
        header = PdbHeaderReader(stream)
        if header.ident not in (UPDB_IDENT, BPDB_IDENT):
            stream.seek(0)
            return super(HaoDooPdb, self).get_metadata(stream, ftype)
        reader = Reader(header, stream, None, None)

        return reader.get_metadata()

    def convert(self, stream, options, file_ext, log, accelerators):
        header = PdbHeaderReader(stream)
        if header.ident not in (UPDB_IDENT, BPDB_IDENT):
            return super(HaoDooPdb, self).convert(
                stream, options, file_ext, log, accelerators)
        reader = Reader(header, stream, log, options)
        opf = reader.extract_content(os.getcwd())

        return opf
