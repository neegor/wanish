import binascii


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


def shorten_title(doc):
    """
    Finding title
    :param doc: full initial document
    :return: found title title
    """

    title = doc.find('.//title')
    if title is None or title.text is None or len(title.text) == 0:
        return ''

    title = title.text.strip()
    title_shingles = shinglify(norm_title(title))

    candidates = {}
    body = doc.xpath('//body')
    if len(body) > 0:

        for text in body[0].itertext():
            candidate = text.strip()
            if len(candidate) <= len(candidate):
                similarity = compare(title_shingles, shinglify(norm_title(candidate)))
                if similarity >= 50:
                    candidates[candidate] = similarity
    else:
        return title

    return sorted(candidates.keys(), key=candidates.get, reverse=True)[0] if len(candidates) > 0 else title
