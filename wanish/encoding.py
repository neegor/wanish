import re
import chardet


def get_encoding(page):
    """
    Obtains page's charset. Fetching it from page decoded to utf8, ignore.
    Returns charset name as string
    """

    page_prototype = page.decode("UTF-8", "ignore")

    # Regex for XML and HTML Meta charset declaration
    charset_re = re.compile(r'<meta.*?charset=["\']*(.+?)["\'>]', flags=re.I)
    pragma_re = re.compile(r'<meta.*?content=["\']*;?charset=(.+?)["\'>]', flags=re.I)
    xml_re = re.compile(r'^<\?xml.*?encoding=["\']*(.+?)["\'>]')

    declared_encodings = (charset_re.findall(page_prototype) +
                          pragma_re.findall(page_prototype) +
                          xml_re.findall(page_prototype))

    # Try any declared encodings
    if len(declared_encodings) > 0:
        for declared_encoding in declared_encodings:
            try:
                page.decode(custom_decode(declared_encoding))
                return custom_decode(declared_encoding)
            except UnicodeDecodeError:
                pass

    # Fallback to chardet if declared encodings fail
    text = re.sub('</?[^>]*>\s*', ' ', page_prototype)
    enc = 'utf-8'
    if not text.strip() or len(text) < 10:
        return enc  # can't guess
    res = chardet.detect(page)
    enc = res['encoding']

    enc = custom_decode(enc)
    return enc


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
