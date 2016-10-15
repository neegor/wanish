import binascii


# Searching short title from readability implementation
import re


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
        '\xa0': ' ',
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


def remove_punctuation(s):
    if not s:
        return ''
    return ''.join([l for l in s if l not in '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'])


def norm_title(title):
    return normalize_spaces(remove_punctuation(normalize_entities(title)))


def shinglify(clean_text):
    """
    Generates list of 'shingles': crc sums of word subsequences of default length
    :param clean_text: cleaned text to calculate shingles sequence.
    :return: shingles sequence
    """
    shingle_length = 3
    result = []
    for idx in range(len(clean_text) - shingle_length + 1):
        result.append(
            binascii.crc32(
                bytes(
                    u' '.join(
                        [word for word in clean_text[idx:idx+shingle_length]]
                    ),
                    'utf-8'
                )
            )
        )

    return result


def compare(initial, candidate):
    """
    Compares two shingles sequence and returns similarity value.
    :param initial: initial sentence shingles sequence
    :param candidate: compared sentence shingles sequence
    :return: similarity value
    """
    matches = 0
    for shingle in initial:
        if shingle in candidate:
            matches += 1

    return matches * 2 / float(len(initial) + len(candidate)) * 100


def shorten_title(doc, article_node):
    """
    Finding title
    :param doc: full initial document
    :param article_node: node containing article
    :return: found title
    """

    title = doc.find('.//title')
    if title is None or title.text is None or len(title.text) == 0:
        return ''

    title = title.text.strip()
    title_shingles = shinglify(norm_title(title))

    candidates = []
    search_tree = None

    body = doc.xpath('//body')
    if len(body) > 0:
        search_tree = body[0].iter()

    if search_tree is not None:

        for elem in search_tree:
            # titles are usually set somewhere before articles
            if article_node is not None and elem == article_node:
                break
            if elem.text is not None:
                candidate = elem.text.strip()
                if 0 < len(candidate) <= len(title):
                    similarity = compare(title_shingles, shinglify(norm_title(candidate)))
                    if similarity >= 50:
                        candidates.append({
                            'text': candidate,
                            'similarity': similarity,
                            'element': elem,
                        })
    else:
        return title, None

    cleaned_candidates = []
    for c in reversed(candidates):
        if all([cc.get('similarity') != c.get('similarity') for cc in cleaned_candidates]) is True:
            cleaned_candidates.insert(0, c)

    best_title_entry = sorted(cleaned_candidates, key=lambda x: x['similarity'], reverse=True)[0] \
        if len(candidates) > 0 else {'text': title, 'similarity': 100, 'element': None}

    # normalizing title and stripping starting/ending sequences of non-letter/non-digit symbols, dates
    best_title = normalize_spaces(normalize_entities(best_title_entry.get('text')))

    # improve leading dates/time stripping
    best_title = re.sub(r'^\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\s+', '', best_title)
    best_title = re.sub(r'^\d{1,2}[-:]\d{1,2}\d{0,2}\s+', '', best_title)

    best_title = re.sub(r'^(\W+\s+)', '', best_title)
    best_title = re.sub(r'(\s+\W+)$', '', best_title)

    return best_title, best_title_entry.get('element')
