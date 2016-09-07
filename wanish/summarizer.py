"""
Extraction of raw text from lxml tree and text summarization
"""
from itertools import combinations

import snowballstemmer
import networkx as nx

from wanish import lang_identifier

from segtok.segmenter import split_multi
from segtok.tokenizer import word_tokenizer

LANG_CODES = {
    'da': 'danish',
    'de': 'german',
    'en': 'english',
    'es': 'spanish',
    'fi': 'finnish',
    'fr': 'french',
    'hu': 'hungarian',
    'it': 'italian',
    'nl': 'dutch',
    'no': 'norwegian',
    'pt': 'portuguese',
    'ru': 'russian',
    'sv': 'swedish',
    'tr': 'turkish',
}


def get_plain_text(cleaned_html_node, summary_sentences_qty):
    """
    Summarizes text from html element.

    :param cleaned_html_node: html node to extract text sentences
    :param summary_sentences_qty: quantity of sentences of summarized text
    :return: summarized text, two-digit language code
    """
    clean_text = ""

    # assembling text only with complete sentences, ended with respective punctuations.
    for node in cleaned_html_node.iter('p'):
        if node.text is not None:
            for sentence in split_multi(node.text):
                if len(sentence) > 0 and sentence[-1:] in ['.', '!', '?', '…'] and \
                        not sentence.strip(' .!?…').isdigit():
                    clean_text = clean_text + ' ' + sentence

    # creating summary, obtaining language code and total sentences quantity
    final_result, lang_code, sent_qty = create_referat(clean_text, '', summary_sentences_qty)

    return final_result, lang_code


def similarity(s1, s2):
    if not len(s1) or not len(s2):
        return 0.0
    return len(s1.intersection(s2))/(1.0 * (len(s1) + len(s2)))


def textrank(text, hdr):
    # finding out the most possible language of the text
    lang_code = lang_identifier.classify(' '.join([hdr, text]))[0]

    # tokenizing for words
    sentences = [sentence for sentence in split_multi(text)]

    stemmer = snowballstemmer.stemmer(LANG_CODES.get(lang_code, 'english'))

    words = [set(stemmer.stemWord(word) for word in word_tokenizer(sentence.lower()) if word.isalpha())
             for sentence in sentences]

    pairs = combinations(range(len(sentences)), 2)
    scores = [(i, j, similarity(words[i], words[j])) for i, j in pairs]
    scores = filter(lambda x: x[2], scores)

    g = nx.Graph()
    g.add_weighted_edges_from(scores)
    pr = nx.pagerank(g)

    return sorted(((i, pr[i], s) for i, s in enumerate(sentences) if i in pr),
                  key=lambda x: pr[x[0]], reverse=True), lang_code


def create_referat(text, hdr, n=5):
    tr, lang_code = textrank(text, hdr)
    if n > len(tr):
        n = len(tr)
    top_n = sorted(tr[:n])
    return ' '.join(x[2] for x in top_n), lang_code, len(top_n)
