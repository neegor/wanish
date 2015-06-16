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

    # looking for headlines first
    headlines = doc.xpath("//*[@itemprop='headline']/text()")
    if len(headlines) > 0:
        return headlines[0]

    # otherwise looking for og:title attribute
    meta_titles = doc.xpath("//meta[@*='og:title']/@content")
    if len(meta_titles) > 0:
        title = orig = meta_titles[0]
    else:
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

    sbd_flag = False  # splitted by delimiter flag
    for delimiter in [' | ', ' - ', ' :: ', ' / ', ' → ']:
        if delimiter in title:
            parts = title.split(delimiter)
            if len(parts[0].split()) >= 4:
                title = parts[0]
                sbd_flag = True

            elif len(parts[-1].split()) >= 4:
                title = parts[-1]
                sbd_flag = True

    if not sbd_flag:
        if ': ' in title:
            parts = title.split(': ')
            if len(parts[-1].split()) >= 4:
                title = parts[-1]
            else:
                title = orig.split(': ', 1)[1]

    if not 15 < len(title) < 150:
        return orig

    return title


def test_title(doc):
    title = doc.find('.//title')
    print(title)
    return title
