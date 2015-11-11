from lxml.html import fromstring
import cgi


def get_encodings(page):
    """
    Obtains page's charset. Fetching it from page decoded to utf8, ignore.
    Returns charset name as string
    """

    detected_charsets = []
    page_prototype = fromstring(page.decode("UTF-8", "ignore"))
    page_head = page_prototype.xpath(".//head")[0]

    # Regex for XML and HTML Meta charset declaration
    meta_charset_nodes = page_head.xpath(".//meta/@charset")
    for node in meta_charset_nodes:
        detected_charsets.append(custom_decode(node))

    meta_content_type_nodes = page_head.xpath(
        ".//meta[translate(@http-equiv, 'CONTEYP', 'conteyp')='content-type']/@content"
    )
    for node in meta_content_type_nodes:
        _, params = cgi.parse_header(node)
        if 'charset' in params:
            detected_charsets.append(custom_decode(params['charset']))

    xml_encoding_nodes = page_prototype.xpath(".//xml/@encoding")
    for node in xml_encoding_nodes:
        detected_charsets.append(custom_decode(node))

    return detected_charsets


def custom_decode(encoding):
    """Overrides encoding when charset declaration
       or charset determination is a subset of a larger
       charset.  Created because of issues with Chinese websites"""
    encoding = encoding.lower()
    alternates = {
        'big5': 'big5hkscs',
        'gb2312': 'gb18030',
        'ascii': 'utf-8',
        'MacCyrillic': 'cp1251',
    }
    if encoding in alternates:
        return alternates[encoding]
    else:
        return encoding
