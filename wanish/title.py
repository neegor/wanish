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


# http://stackoverflow.com/questions/22726177/longest-common-substring-without-cutting-a-word-python
def longest_common_substring(s1, s2):
    m = [[0] * (1 + len(s2)) for i in range(1 + len(s1))]
    longest, x_longest = 0, 0
    for x in range(1, 1 + len(s1)):
        for y in range(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
                    x_longest = x
            else:
                m[x][y] = 0
    return s1[x_longest - longest: x_longest]


def longest_common_sentence(s1, s2):
    """
    Finds longest common substring of words from two strings
    :param s1: first string
    :param s2: second string
    :return: longest words sequence of the two strings
    """
    s1_words = s1.split(' ')
    s2_words = s2.split(' ')
    return ' '.join(longest_common_substring(s1_words, s2_words))


def shorten_title(doc):

    # looking for tag containing itemprop='headline' first
    headlines = doc.xpath("//*[normalize-space(@itemprop)='headline']/text()")
    if len(headlines) > 0:
        return normalize_spaces(headlines[0])

    # looking for tag containing itemprop='name' if exists
    names = doc.xpath("//*[normalize-space(@itemprop)='name']/text()")
    if len(names) > 0:
        return normalize_spaces(names[0])

    # looking for h1/h2/h3 with "head" ot "title" substrings in it
    possible_h1_headers = doc.xpath("//h1[contains(@class, 'head')]/text() | //h1[contains(@class, 'title')]/text()")
    if len(possible_h1_headers) > 0:
        return possible_h1_headers[0]

    possible_h2_headers = doc.xpath("//h2[contains(@class, 'head')]/text() | //h2[contains(@class, 'title')]/text()")
    if len(possible_h2_headers) > 0:
        return possible_h2_headers[0]

    # otherwise looking for og:title attribute
    meta_titles = doc.xpath("//meta[normalize-space(@*)='og:title']/@content")

    if len(meta_titles) > 0:
        candidates = []
        candidates.append(normalize_spaces(meta_titles[0]))

        # getting headings from h1, h2, h3
        headings = doc.xpath("//h1/text() | //h2/text() | //h3/text() | //span/text() | //a/text()")

        for heading in headings:
            candidates.append(normalize_spaces(heading))

        commons = []

        for idx in range(1, len(candidates)):
            common = longest_common_sentence(candidates[0], candidates[idx])
            if len(common) > 0 and common not in commons:
                commons.append(common)

        if len(commons) > 0:
            return sorted(commons, key=len)[-1]
        else:
            return ""

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

        if not 15 < len(title) < 150:
            return orig

        return title
