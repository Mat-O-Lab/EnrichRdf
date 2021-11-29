
import pandas as pd
import io
import ast
import json
from urllib.request import urlopen
from urllib.parse import urlparse, unquote
from dateutil.parser import parse
from contextlib import redirect_stderr
from csv import Sniffer

import chardet
from owlready2 import *

##disable ssl verification
#import ssl
#ssl._create_default_https_context = ssl._create_unverified_context

# there is a bug in Owlready2 when having imports in turtle in a owl file
# if the error is thrown, load again and it is fine
try:
    mseo= get_ontology("https://purl.matolab.org/mseo/mid").load()
except:
    mseo= get_ontology("https://purl.matolab.org/mseo/mid").load()

cco_mu= get_ontology("http://www.ontologyrepository.com/CommonCoreOntologies/Mid/UnitsOfMeasureOntology/").load()
qudt= get_ontology('http://www.qudt.org/qudt/owl/1.0.0/unit.owl').load()


class CSV_Annotator():
    def __init__(self, separator : str, encoding : str):



        self.separator = separator
        self.encoding = encoding



        self.json_ld_context= [
            "http://www.w3.org/ns/csvw", {
                "cco": "http://www.ontologyrepository.com/CommonCoreOntologies/",
                "mseo": mseo.base_iri,
                "label": "http://www.w3.org/2000/01/rdf-schema#label",
                "xsd": "http://www.w3.org/2001/XMLSchema#"}
        ]
        self.umlaute_dict = {
            '\u00e4': 'ae',  # U+00E4	   \xc3\xa4
            '\u00f6': 'oe',  # U+00F6	   \xc3\xb6
            '\u00fc': 'ue',  # U+00FC	   \xc3\xbc
            '\u00c4': 'Ae',  # U+00C4	   \xc3\x84
            '\u00d6': 'Oe',  # U+00D6	   \xc3\x96
            '\u00dc': 'Ue',  # U+00DC	   \xc3\x9c
            '\u00df': 'ss',  # U+00DF	   \xc3\x9f
        }

    def open_file(self, uri=''):
        try:
            uri_parsed = urlparse(uri)
        except:
            print('not an uri - if local file add file:// as prefix')
            return None
        else:
            filename = unquote(uri_parsed.path).split('/')[-1]
            if uri_parsed.scheme in ['https', 'http']:
                filedata = urlopen(uri).read()

            elif uri_parsed.scheme == 'file':
                filedata = open(unquote(uri_parsed.path), 'rb').read()
            else:
                print('unknown scheme {}'.format(uri_parsed.scheme))
                return None
            return filedata, filename

    def process(self, url) -> (str, str):
        '''
        :return: returns a filename and content(json string dump) of a metafile in the json format.
        '''

        file_data, file_name = self.open_file(url)

        if file_name is None or file_data is None:
            return "error", "cannot parse url"

        if self.encoding == 'auto':
            self.encoding = self.get_encoding(file_data)

        if self.separator == 'auto':
            try:
                self.separator = self.get_column_separator(file_data)
            except:
                return "error", 'cant find separator, pls manualy select'

        metafile_name, result = self.process_file(file_name, file_data, self.separator,
                                                  self.encoding)

        return metafile_name, result


    def get_encoding(self, file_data):
        """

        :param file_data:   content of the file we want to parse
        :return:            encoding of the specified file content e.g. utf-8, ascii..
        """
        result = chardet.detect(file_data)
        return result['encoding']

    def get_column_separator(self, file_data):
        """

        :param file_data: data of the file we want to parse
        :return:          the seperator of the specified data, e.g. ";" or ","
        """
        file_string = io.StringIO(file_data.decode(self.encoding))
        sniffer = Sniffer()
        dialect = sniffer.sniff(file_string.read(512))
        return dialect.delimiter

    def get_header_length(self, file_data, separator_string, encoding):
        """
        This method finds the beginning of a header line inside a csv file.
        Some csv files begin with additional information before
        displaying the actual data-table.

        We want to solve this problem by finding the beginning of the header-line
        (column-descriptors) and read the metainfo and data-table separately.

        :param file_data: content of the file we want to parse
        :param separator_string: csv-separator
        :param encoding: text encoding
        :return: a 2-tuple of (first_head_line, max_columns_additional_header)
                      where
                          first_head_line : index of the header line in the csv file
                          max_columns_additional_header : number of columns in the data-table
        """

        # since pandas throws errormessages when encountering a parseerror (meaning when
        # encountering a csv-file with changing column-count for example), we can
        # redirect the error to file_string. Then, we can read and analyze the error-message.
        # This is helpful since we can see in which line the parser expected n columns, but got m instead.

        file_string = io.StringIO(file_data.decode(encoding))
        f = io.StringIO()
        with redirect_stderr(f):
            df = pd.read_csv(file_string, sep=separator_string, error_bad_lines=False, warn_bad_lines=True, header=None)
        f.seek(0)
        # without utf string code b'
        warn_str = f.read()[2:-2]

        # split the warnings up
        warnlist = warn_str.split('\\n')[:-1]

        # The warnings we care about are of form 'Skipping line x: expected n columns, got m'
        # readout row index and column count in warnings
        line_numbers = [int(re.search('Skipping line (.+?):', line).group(1)) for line in warnlist]

        # get the found number of columns
        column_numbers = [int(line[-1]) for line in warnlist]
        column_numbersm1 = column_numbers.copy()
        if not column_numbersm1:
            # no additional header
            return 0, 0

        # pop last element, so column_numbers is always lenght +1
        column_numbersm1.pop(-1)

        # assumes that the file ends with a uniform table with constant column count
        # determine changes in counted columns starting from the last line of file
        changed_column_count_line = [line_numbers[index + 1] for index in reversed(range(len(column_numbersm1))) if
                                     column_numbersm1[index] != column_numbers[index + 1]]

        # if there are column count - changes, then the first head-line is the the index
        # of the row of the last change of column count minus 1.
        if changed_column_count_line:

            # additional header has ends in line before the last change of column count
            first_head_line = changed_column_count_line[0] - 1
        elif line_numbers:

            # edgecase is that we only have one column-count change, in this case,
            # changed_column_count_line is empty, thus, first_head_line is just the first change
            first_head_line = line_numbers[0] - 1
        else:
            first_head_line = 0

        # starting from first_head_line, max_columns_additional_header is the
        # maximum number of columns
        max_columns_additional_header = (max(column_numbers[:line_numbers.index(first_head_line + 1) - 1]))
        return first_head_line, max_columns_additional_header

    def get_num_header_rows_and_dataframe(self, file_data, separator_string, header_length, encoding):
        """

        :param file_data: content of the file we want to parse
        :param separator_string: csv-delimiter
        :param header_length: rows of the header
        :param encoding: csv-encoding
        :return: 2-tuple (num_header_rows, table_data)
                      where
                          num_header_rows : number of header rows
                          table_data : pandas DataFrame object containing the tabular information
        """

        file_string = io.StringIO(file_data.decode(encoding))
        num_header_rows = 1

        good_readout = False
        while not good_readout:
            file_string.seek(0)
            table_data = pd.read_csv(file_string, header=list(range(num_header_rows)), sep=separator_string,
                                     skiprows=header_length, encoding=encoding)

            # test if all text values in first table row -> is a second header row
            all_text = all([self.get_value_type(value) == 'TEXT' for column, value in table_data.iloc[0].items()])
            if all_text:
                num_header_rows += 1
                continue
            else:
                good_readout = True
        return num_header_rows, table_data

    def get_unit(self, string):
        found = list(cco_mu.search(alternative_label=string)) \
                + list(cco_mu.search(SI_unit_symbol=string)) \
                + list(mseo.search(alternative_label=string)) \
                + list(mseo.search(SI_unit_symbol=string)) \
                + list(qudt.search(symbol=string)) \
                + list(qudt.search(abbreviation=string)) \
                + list(qudt.search(ucumCode=string))
        if found:
            return {"cco:uses_measurement_unit": {"@id": str(found[0].iri), "@type": str(found[0].is_a)}}
        else:
            return {}

    def is_date(self, string, fuzzy=False):
        try:
            parse(string, fuzzy=fuzzy)
            return True

        except ValueError:
            return False

    def get_value_type(self, string):
        string = str(string)
        # remove spaces and replace , with . and
        string = string.strip().replace(',', '.')
        if len(string) == 0: return 'BLANK'
        try:
            t = ast.literal_eval(string)
        except ValueError:
            return 'TEXT'
        except SyntaxError:
            if self.is_date(string):
                return 'DATE'
            else:
                return 'TEXT'
        else:
            if type(t) in [int, float, bool]:
                if type(t) is int:
                    return 'INT'
                if t in set((True, False)):
                    return 'BOOL'
                if type(t) is float:
                    return 'FLOAT'
            else:
                return 'TEXT'

    def describe_value(self, value_string):
        if pd.isna(value_string):
            return {}
        elif self.get_value_type(value_string) == 'INT':
            return {'cco:has_integer_value': {'@value': value_string, '@type': 'xsd:integer'}}
        elif self.get_value_type(value_string) == 'BOOL':
            return {'cco:has_bolean_value': {'@value': value_string, '@type': 'xsd:boolean'}}
        elif self.get_value_type(value_string) == 'FLOAT':
            return {'cco:has_decimal_value': {'@value': value_string, '@type': 'xsd:decimal'}}
        elif self.get_value_type(value_string) == 'DATE':
            return {'cco:has_datetime_value': {'@value': str(parse(value_string)), '@type': 'xsd:dateTime'}}
        else:
            # check if its a unit
            unit_dict = self.get_unit(value_string)
            if unit_dict:
                return unit_dict
            else:
                return {'cco:has_text_value': {'@value': value_string, '@type': 'xsd:string'}}

    def make_id(self, string, namespace=None):
        for k in self.umlaute_dict.keys():
            string = string.replace(k, self.umlaute_dict[k])
        if namespace:
            return namespace + ':' + re.sub('[^A-ZÜÖÄa-z0-9]+', '', string.title().replace(" ", ""))
        else:
            return './' + re.sub('[^A-ZÜÖÄa-z0-9]+', '', string.title().replace(" ", ""))

    def get_additional_header(self, file_data, separator, encoding):
        """

        :param file_data: content of the file we want to parse
        :param separator: csv-separator
        :param encoding: text encoding
        :return:
        """

        # get length of additional header
        header_length, max_columns_additional_header = self.get_header_length(file_data, separator, encoding)

        if header_length:
            file_string = io.StringIO(file_data.decode(encoding))
            header_data = pd.read_csv(file_string, header=None, sep=separator, nrows=header_length,
                                      names=range(max_columns_additional_header), encoding=encoding,
                                      skip_blank_lines=False)
            header_data['row'] = header_data.index
            header_data.rename(columns={0: 'param'}, inplace=True)
            header_data.set_index('param', inplace=True)
            header_data = header_data[~header_data.index.duplicated()]
            header_data.dropna(thresh=2, inplace=True)
            return header_data, header_length

        else:
            return None, 0

    def serialize_header(self, header_data, file_namespace=None):

        params = list()
        info_line_iri = "cco:InformationLine"
        for parm_name, data in header_data.to_dict(orient='index').items():
            # describe_value(data['value'])
            para_dict = {'@id': self.make_id(parm_name, file_namespace)+str(data['row']), 'label': parm_name, '@type': info_line_iri}
            for col_name, value in data.items():
                # print(parm_name,col_name, value)
                if col_name == 'row':
                    para_dict['mseo:has_row_index'] = {"@value": data['row'], "@type": "xsd:integer"}
                else:
                    para_dict = {**para_dict, **self.describe_value(value)}
            params.append(para_dict)
        # print(params)
        return params

    def process_file(self, file_name, file_data, separator, encoding):
        """

        :param file_name: name of the file we want to process
        :param file_data: content of the file
        :param separator: csv-seperator /delimiter
        :param encoding:  text-encoding (e.g. utf-8..)
        :return: a 2-tuple (meta_filename,result)
                      where
                          result :    the resulting metadata on how to
                                      read the file (skiprows, colnames ..)
                                      as a json dump
                          meta_filename :  the name of the metafile we want to write
        """

        # init results dict
        data_root_url = "https://github.com/Mat-O-Lab/resources/"

        file_namespace = None
        metadata_csvw = dict()
        metadata_csvw["@context"] = self.json_ld_context

        # metadata_csvw["@id"]=file_namespace
        metadata_csvw["url"] = file_name

        # read additional header lines and provide as meta in results dict
        header_data, header_length = self.get_additional_header(file_data, separator, encoding)

        if header_length:
            # print("serialze additinal header")
            metadata_csvw["notes"] = self.serialize_header(header_data, file_namespace)

        # read tabular data structure, and determine number of header lines for column description used
        header_lines, table_data = self.get_num_header_rows_and_dataframe(file_data, separator, header_length, encoding)

        # describe dialect
        metadata_csvw["dialect"] = {"delimiter": separator,
                                    "skipRows": header_length, "headerRowCount": header_lines, "encoding": encoding}

        # describe columns
        if header_lines == 1:
            # see if there might be a unit string at the end of each title
            # e.g. "E_y (MPa)"
            column_json = list()
            for index, title in enumerate(table_data.columns):

                # skip Unnamed cols
                if "Unnamed" in title:
                    continue

                if len(title.split(' ')) > 1:
                    unit_json = self.get_unit(title.split(' ')[-1])
                else:
                    unit_json = {}
                json_str = {**{'titles': title, '@id': self.make_id(title), "@type": "Column"}, **unit_json}
                column_json.append(json_str)
            metadata_csvw["tableSchema"] = {"columns": column_json}

        else:
            column_json = list()
            for index, (title, unit_str) in enumerate(table_data.columns):
                json_str = {**{'titles': title, '@id': self.make_id(title), "@type": "Column"},
                            **self.get_unit(unit_str)}
                column_json.append(json_str)
            metadata_csvw["tableSchema"] = {"columns": column_json}

        result = json.dumps(metadata_csvw, indent=4)
        meta_file_name = file_name.split(sep='.')[0] + '-metadata.json'
        return meta_file_name, result

    def set_encoding(self, new_encoding : str):
        self.encoding = new_encoding

    def set_separator(self, new_separator : str):
        self.separator = new_separator
