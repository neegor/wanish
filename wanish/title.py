# Searching short title from readability implementation
def normalize_entities(cur_title):
    entities = {
        '—': '-',
        '–': '-',
        '&mdash;': '-',
        '&ndash;': '-',
        ' ': ' ',
        '«': '"',
        '»': '"',
        '&quot;': '"',
    }
    for c in entities:
        if c in cur_title:
            cur_title = cur_title.replace(c, entities[c])

    return cur_title


def normalize_spaces(s):
    """
    Replace any sequence of whitespace characters with a single space.
    """
    if not s:
        return ''
    return ' '.join(s.split())


def norm_title(title):
    return normalize_entities(normalize_spaces(title))


def add_match(collection, text, orig):
    text = norm_title(text)
    if len(text.split()) >= 2 and len(text) >= 15:
        if text.replace('"', '') in orig.replace('"', ''):
            collection.add(text)


def shorten_title(doc):

    # looking for tag containing itemprop='headline' first
    headlines = doc.xpath("//*[normalize-space(@itemprop)='headline']/text()")
    if len(headlines) > 0:
        return normalize_spaces(headlines[0])

    # looking for tag containing itemprop='name' if exists
    names = doc.xpath("//*[normalize-space(@itemprop)='name']/text()")
    if len(names) > 0:
        return normalize_spaces(names[0])

    # otherwise looking for og:title attribute
    meta_titles = doc.xpath("//meta[normalize-space(@*)='og:title']/@content")
    if len(meta_titles) > 0:
        return normalize_spaces(meta_titles[0])

    # if no attributes, then doing it the long way
    title = doc.find('.//title')
    if title is None or title.text is None or len(title.text) == 0:
        return ''
    title = orig = norm_title(title.text)

    candidates = set()

    for item in ['.//h1', './/h2', './/h3']:
        for e in list(doc.iterfind(item)):
            if e.text:
                add_match(candidates, e.text, orig)
            if e.text_content():
                add_match(candidates, e.text_content(), orig)

    for item in ['#title', '#head', '#heading', '.pageTitle', '.news_title',
                 '.title', '.head', '.heading', '.contentheading', '.small_header_red']:
        for e in doc.cssselect(item):
            if e.text:
                add_match(candidates, e.text, orig)
            if e.text_content():
                add_match(candidates, e.text_content(), orig)

    if candidates:
        title = sorted(candidates, key=len)[-1]

    if not 15 < len(title) < 150:
        return orig

    return title
