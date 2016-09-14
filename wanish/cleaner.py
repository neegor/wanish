import re

from lxml.etree import tostring
from lxml.html import document_fromstring, fragment_fromstring
from lxml import etree
from lxml.html.clean import Cleaner


REGEXES = {
    'unlikelyCandidatesRe': re.compile(
            'combx|comment|community|disqus|extra|foot|header|menu|remark|rss|shoutbox'
            '|sidebar|sponsor|ad-break|agegate|pagination|pager|popup|tweet|twitter|adblock', re.I
        ),
    'okMaybeItsACandidateRe': re.compile('and|article|body|column|main|shadow', re.I),
    'positiveRe': re.compile('article|body|content|entry|hentry|main|page|pagination|post|text|blog|story', re.I),
    'negativeRe': re.compile(
            'combx|comment|com-|contact|foot|footer|footnote|masthead|media|meta|outbrain|promo'
            '|related|scroll|shoutbox|sidebar|sponsor|shopping|tags|tool|widget|adblock', re.I
        ),
    'divToPElementsRe': re.compile('<(a|blockquote|dl|div|img|ol|p|pre|table|ul)', re.I),
}

ESCAPED_ENTITIES = {
    " ": ("&nbsp;", "&#160;"),
    "£": ("&pound;", "&#163;"),
    "€": ("&euro;", "&#8364;"),
    "¶": ("&para;", "&#182;"),
    "§": ("&sect;", "&#167;"),
    "©": ("&copy;", "&#169;"),
    "®": ("&reg;", "&#174;"),
    "™": ("&trade;", "&#8482;"),
    "°": ("&deg;", "&#176;"),
    "±": ("&plusmn;", "&#177;"),
    "¼": ("&frac14;", "&#188;"),
    "½": ("&frac12;", "&#189;"),
    "¾": ("&frac34;", "&#190;"),
    "×": ("&times;", "&#215;"),
    "÷": ("&divide;", "&#247;"),
    "ƒ": ("&fnof;", "&#402;"),
    "…": ("&hellip;", "&#8230;"),
    "′": ("&prime;", "&#8242;"),
    "″": ("&Prime;", "&#8243;"),
    "–": ("&ndash;", "&#8211;"),
    "—": ("&mdash;", "&#8212;"),
    '"': ("&quot;", "&#34;"),
    "'": ("&apos;", "&#39;"),
    "‘": ("&lsquo;", "&#8216;"),
    "’": ("&rsquo;", "&#8217;"),
    "‚": ("&sbquo;", "&#8218;"),
    "“": ("&ldquo;", "&#8220;"),
    "”": ("&rdquo;", "&#8221;"),
    "„": ("&bdquo;", "&#8222;"),
    "«": ("&laquo;", "&#171;"),
    "»": ("&raquo;", "&#187;"),
}


class ArticleExtractor(object):
    """
    Class for article extraction from web page by given URL
    """

    TEXT_LENGTH_THRESHOLD = 25  # threshold
    RETRY_LENGTH = 250

    def __init__(self, positive_keywords=None, negative_keywords=None):
        self._html = None
        self._positive_keywords = compile_pattern(positive_keywords)
        self._negative_keywords = compile_pattern(negative_keywords)

    def get_clean_html(self, source_html=None, html_partial=False):
        """
        Getting cleaned summary of the html article.

        :param source_html: source HTML object
        :param html_partial: return only the div of the document, don't wrap in html and body tags.
        """
        if source_html is None:
            return None

        try:
            ruthless = True  # flag to remove unworthy candidates

            while True:
                self._html = source_html  # reinitialization of current performing html

                # narrowing the scope to articleBody, article or body tags.
                html_partial = self.narrow_scope(html_partial)

                # get initial candidates
                candidates = self.find_candidates(ruthless)

                # raw possible article
                article, ruthless, should_continue = self.get_possible_article(candidates, html_partial, ruthless)

                if should_continue is True:
                    continue

                cleaned_article = self.sanitize(article, candidates)

                article_length = len(cleaned_article or '')
                retry_length = self.RETRY_LENGTH

                # check the resulting length, if too short, do a new iteration without removal of unlikely nodes
                if ruthless and article_length < retry_length:
                    ruthless = False
                    continue
                else:
                    return cleaned_article

        except Exception as e:
            # unable to summarize
            raise Unparseable(str(e))

        # not found
        return None

    def find_candidates(self, ruthless):
        """
        Finds candidate nodes containing possible text articles.
        :param ruthless: flag to remove candidates which are unlikely to contain correct article
        :return: list of candidate nodes
        """

        # cleaning useless tag subtrees
        for i in self.tags(self._html, 'script', 'style'):
            i.drop_tree()
        for i in self.tags(self._html, 'body'):
            i.set('id', 'readabilityBody')

        if ruthless:
            self.remove_unlikely_candidates()

        # transforms all <div> without another block elements into <p>
        self.transform_misused_divs_into_paragraphs()

        # collecting candidate nodes scoring them by density and content length
        candidates = self.score_paragraphs()

        return candidates

    def narrow_scope(self, html_partial=False):
        """
        Narrows the scope of self._html to articleBody, article or body tags if present

        :return:
        """
        if self._html is not None:
            article_body = self._html.xpath("//*[@itemprop='articleBody']")
            articles = self._html.xpath("//article")
            body = self._html.xpath("//body")

            for data in (article_body, articles, body):
                if len(data) > 0:
                    self._html = data[0]
                    html_partial = True

        return html_partial

    def get_possible_article(self, candidates, html_partial, ruthless):
        """
        Tries to fetch an article among the given candidates
        :param candidates:
        :param html_partial:
        :param ruthless:
        :return:
        """
        should_continue = False
        article = None

        # fetching the best candidate
        best_candidate = self.select_best_candidate(candidates)

        if best_candidate:
            # forming an article from the best candidate
            article = self.get_article(candidates, best_candidate, html_partial=html_partial)
        else:
            if ruthless:
                # too much was removed - doing a new iteration of performing without removal of unlikely nodes
                ruthless = False
                should_continue = True

            else:
                # second iteration failed - working with html as it is
                article = self._html.find('body')

                if article is None:
                    article = self._html

        return article, ruthless, should_continue

    @staticmethod
    def tags(node, *tag_names):
        """
        Yields tags from list of args, which are met in the node in sequential order.
        """
        for tag_name in tag_names:
            for e in node.findall('.//%s' % tag_name):
                yield e

    @staticmethod
    def reverse_tags(node, *tag_names):
        """
        Yields tags from list of args, which are met in the node in reverse order.
        """
        for tag_name in tag_names:
            for e in reversed(node.findall('.//%s' % tag_name)):
                yield e

    def remove_unlikely_candidates(self):
        """
        Removes undesired tags including subtrees from html pages.
        """
        for elem in self._html.iter():
            s = "%s %s" % (elem.get('class', ''), elem.get('id', ''))
            if len(s) < 2:
                continue
            if REGEXES['unlikelyCandidatesRe'].search(s) \
                    and (not REGEXES['okMaybeItsACandidateRe'].search(s)) \
                    and elem.tag not in ['html', 'body']:
                elem.drop_tree()

    def transform_misused_divs_into_paragraphs(self):
        """
        Transforms <div> without other block elements into <p>, merges near-standing <p> together.
        """
        for elem in self.tags(self._html, 'div'):
            # transform <div>s that do not contain other block elements into
            # <p>s
            # FIXME: The current implementation ignores all descendants that are not direct children of elem
            # This results in incorrect results in case there is an <img> buried within an <a> for example

            if not REGEXES['divToPElementsRe'].search(tostring(elem).decode()):
                elem.tag = "p"

        for elem in self.tags(self._html, 'div'):
            if elem.text and elem.text.strip():
                p = fragment_fromstring('<p/>')
                p.text = elem.text
                elem.text = None
                elem.insert(0, p)

            for pos, child in reversed(list(enumerate(elem))):
                if child.tail and child.tail.strip():
                    p = fragment_fromstring('<p/>')
                    p.text = child.tail
                    child.tail = None
                    elem.insert(pos + 1, p)

                if child.tag == 'br':
                    child.drop_tree()

    def score_paragraphs(self):
        """
        Evaluates paragraphs, forms a list of candidate texts by paragraph length and links density.

        :return: list of candidates
        """

        min_len = self.TEXT_LENGTH_THRESHOLD
        candidates = {}
        ordered = []
        for elem in self.tags(self._html, "p", "pre", "td"):
            parent_node = elem.getparent()
            if parent_node is None:
                continue
            grand_parent_node = parent_node.getparent()

            inner_text = clean(elem.text_content() or "")
            inner_text_len = len(inner_text)

            # Don't even count this paragraph if it is less than 25 characters
            if inner_text_len < min_len:
                continue

            if parent_node not in candidates:
                candidates[parent_node] = self.score_node(parent_node)
                ordered.append(parent_node)

            if grand_parent_node is not None and grand_parent_node not in candidates:
                candidates[grand_parent_node] = self.score_node(
                    grand_parent_node)
                ordered.append(grand_parent_node)

            content_score = 1
            content_score += len(inner_text.split(','))
            content_score += min((inner_text_len / 100), 3)

            candidates[parent_node]['content_score'] += content_score
            if grand_parent_node is not None:
                candidates[grand_parent_node]['content_score'] += content_score / 2.0

        # Scale the final candidates score based on link density. Good content
        # should have a relatively small link density (5% or less) and be mostly unaffected by this operation.
        for elem in ordered:
            candidate = candidates[elem]

            ld = self.get_link_density(elem)
            candidate['content_score'] *= (1 - ld)

            # Multiplying the score by multiplier of raw text length
            candidate['content_score'] *= (1 + float(len(elem.text_content())) / 500)

        return candidates

    def score_node(self, elem):
        """
        Scores the element by its tag.

        :param elem: element to score
        :return: score rating of the element
        """
        content_score = self.class_weight(elem)
        name = elem.tag.lower()
        if name == "div":
            content_score += 5
        elif name in ["pre", "td", "blockquote"]:
            content_score += 3
        elif name in ["address", "ol", "ul", "dl", "dd", "dt", "li", "form"]:
            content_score -= 3
        elif name in ["h1", "h2", "h3", "h4", "h5", "h6", "th"]:
            content_score -= 5
        return {
            'content_score': content_score,
            'elem': elem
        }

    def class_weight(self, e):
        """
        Calculates weight of the node by its classes and ids. Negative words inside decrease it, positive increase.
        :param e: element to calculate class weight
        :return: calculated weight
        """
        weight = 0
        for feature in (e.get('class', None), e.get('id', None)):
            if feature:
                weight += self.check_regexes(feature)
                weight += self.check_keywords(feature)
        weight += self.check_keywords('tag-'+e.tag)
        return weight

    @staticmethod
    def check_regexes(text=''):
        """
        Checks if text contains positive or negative parts from regexps and return its weight offset
        :param text: text to perform
        :return: weight offset
        """
        weight = 0
        if REGEXES['negativeRe'].match(text):
            weight -= 25
        if REGEXES['positiveRe'].match(text):
            weight += 25
        return weight

    def check_keywords(self, text=''):
        """
        Checks if text contains positive or negative keyword parts and return its weight offset
        :param text: text to perform
        :return: weight offset
        """
        weight = 0
        if self._positive_keywords and self._positive_keywords.match(text):
            weight += 25
        if self._negative_keywords and self._negative_keywords.match(text):
            weight -= 25
        return weight

    @staticmethod
    def select_best_candidate(candidates):
        """
        Selects the best calculate from a list by it's content_score.

        :param candidates: list of candidates to get the best one
        :return: best candidate
        """
        sorted_candidates = sorted(candidates.values(), key=lambda x: x['content_score'], reverse=True)
        if len(sorted_candidates) == 0:
            return None

        best_candidate = sorted_candidates[0]
        return best_candidate

    @staticmethod
    def get_link_density(elem):
        """
        Calculating link density of the element.

        :param elem: element to calculate the link density
        :return: calculated link density of the element
        """
        link_length = 0
        for i in elem.findall(".//a"):
            link_length += text_length(i)
        total_length = text_length(elem)
        return float(link_length) / max(total_length, 1)

    def get_article(self, candidates, best_candidate, html_partial=False):
        """
        Initial article cleansing. Siblings of the top candidate are looked through for content
        that might also be related. Things like preambles, content split by ads that we removed, etc.

        :param candidates: list of candidate nodes
        :param best_candidate: best candidate from the list
        :param html_partial: flag to perform an article: True = full html, False = html fragment
        :return: calculated link density of the element
        """
        sibling_score_threshold = max([
            10,
            best_candidate['content_score'] * 0.2])

        # create a new html document with a html->body->div
        output = self.initial_output(html_partial)
        best_elem = best_candidate['elem']

        for sibling in best_elem.getparent().getchildren():
            append = True if sibling is best_elem else self.is_appendable(sibling,
                                                                          candidates,
                                                                          sibling_score_threshold)

            if append:
                # We don't want to append directly to output, but the div in html->body->div
                if html_partial:
                    output.append(sibling)
                else:
                    output.getchildren()[0].getchildren()[0].append(sibling)

        return output

    @staticmethod
    def initial_output(html_partial=False):
        """
        Creates initial HTML document according to the given flag
        :param html_partial: determines if there should be the html page or only a fragment
        :return: html output element
        """
        return fragment_fromstring('<div/>') if html_partial else document_fromstring('<div/>')

    def is_appendable(self, sibling, candidates, sibling_score_threshold):
        """
        Finds out if this sibling element should be appended to the output
        :param sibling: element to perform
        :param candidates: list of candidate elements
        :param sibling_score_threshold: threshlod of the score
        :return: boolean flag
        """
        append = False

        sibling_key = sibling  # HashableElement(sibling)

        if sibling_key in candidates and candidates[sibling_key]['content_score'] >= sibling_score_threshold:
            append = True

        if sibling.tag == "p":
            link_density = self.get_link_density(sibling)
            node_content = sibling.text or ""
            node_length = len(node_content)

            if node_length > 80 and link_density < 0.25:
                append = True
            elif node_length <= 80 and link_density == 0 and re.search('\.( |$)', node_content):
                append = True

        return append

    def sanitize(self, node, candidates):
        """
        Sanitizing html node by different criteria.

        :param node: source html-fragment
        :param candidates: list of node candidates
        :return: cleaned html fragment, containing base tags without attributes
        """

        for header in self.tags(node, "h1", "h2", "h3", "h4", "h5", "h6"):
            if self.class_weight(header) < 0 or self.get_link_density(header) > 0.33:
                header.drop_tree()

        for elem in self.tags(node, "form", "iframe", "textarea"):
            elem.drop_tree()
        allowed = {}

        # Conditionally clean <table>s, <ul>s, and <div>s
        for el in self.reverse_tags(node, "table", "ul", "div"):
            if el in allowed:
                continue
            weight = self.class_weight(el)
            if el in candidates:
                content_score = candidates[el]['content_score']
            else:
                content_score = 0

            if weight + content_score < 0:
                el.drop_tree()
            elif el.text_content().count(",") < 10:
                self.remove_unnecessary_element(el, weight, allowed)

        self._html = node

        # # removing subtrees without text
        # for child in self._html.getroottree().iter("*"):
        #     has_text = False
        #     for txt in child.itertext():
        #         if len(txt.strip(' \t\n')) > 0:
        #             has_text = True
        #             break
        #     if not has_text:
        #         child.clear()

        return clean_attributes(etree.tostring(self._html).decode())

    def remove_unnecessary_element(self, element, weight, allowed):
        """
        Removes insignificant element trees

        :param element: element to perform
        :param weight: weight of a given node
        :param allowed: list of elements which are allowed and will be not removed in future
        :return:
        """

        min_len = self.TEXT_LENGTH_THRESHOLD
        tag = element.tag

        counts = {}
        for kind in ['p', 'img', 'li', 'a', 'embed', 'input']:
            counts[kind] = len(element.findall('.//%s' % kind))
        counts["li"] -= 100
        counts["input"] -= len(element.findall('.//input[@type="hidden"]'))

        # Count the text length excluding any surrounding whitespace
        content_length = text_length(element)
        link_density = self.get_link_density(element)
        to_remove = False

        if any([
            self.counts_conditions(counts),
            self.density_conditions(weight, link_density),
            counts["li"] > counts["p"] and tag != "ul" and tag != "ol",
            content_length < min_len and (counts["img"] == 0 or counts["img"] > 2),
            (counts["embed"] == 1 and content_length < 75) or counts["embed"] > 1,
        ]) is True:
            to_remove = True

        to_remove = self.check_if_allowed(element, allowed, to_remove)

        if to_remove:
            element.drop_tree()

    @staticmethod
    def counts_conditions(counts):
        """
        Evaluates conditions about counts of elements
        :param counts: dict of tags counts
        :return: flag if conditions are True or False
        """
        return (counts["p"] and counts["img"] > counts["p"]) or \
               (counts["input"] > (counts["p"] / 3))

    @staticmethod
    def density_conditions(weight=0, link_density=0.0):
        """
        Evaluates conditions about density of links
        :param weight: tag's weight
        :param link_density: link density indicator
        :return: flag if conditions are True or False
        """
        return (weight < 25 and link_density > 0.2) or (weight >= 25 and link_density > 0.5)


    def check_if_allowed(self, element, allowed, to_remove):
        """
        Checks if this element should be allowed and not removed in future checks
        :param element: element to perform
        :param allowed: list of allowed elements
        :param to_remove: flag to set the element for removal
        :return:
        """

        # find x non empty preceding and succeeding siblings
        siblings = []
        siblings.extend(self.get_siblings_content_lengths(element, how_many=1))
        siblings.extend(self.get_siblings_content_lengths(element, preceding=True, how_many=1))

        if siblings and sum(siblings) > 1000:
            to_remove = False
            for desnode in self.tags(element, "table", "ul", "div"):
                allowed[desnode] = True

        return to_remove

    @staticmethod
    def get_siblings_content_lengths(element, preceding=False, how_many=1):
        """
        Returns a list of siblings content length

        :param element: element to perform
        :param preceding: flag describing should we do that for preceding or succeeding siblings
        :param how_many: amount of siblings to return
        :return:
        """
        siblings = []
        ctr = 0
        for sib in element.itersiblings(preceding=preceding):
            sib_content_length = text_length(sib)
            if sib_content_length:
                ctr += 1
                siblings.append(sib_content_length)
                if ctr == how_many:
                    break

        return siblings



single_quoted = "'[^']+'"
double_quoted = '"[^"]+"'
non_space = '[^ "\'>]+'
html_strip = re.compile("<"  # open
                        "([^>]+) "  # prefix
                        "(?:\w+) *" +  # any attribute in tag
                        '= *(?:%s|%s|%s)' % (non_space, single_quoted, double_quoted) +  # value
                        "([^>]*)"  # postfix
                        ">",  # end
                        re.I)

html_cleaner = Cleaner(scripts=True, javascript=True, comments=True,
                       style=True, links=True, meta=False, add_nofollow=False,
                       page_structure=False, processing_instructions=True, embedded=False,
                       frames=False, forms=False, annoying_tags=False, remove_tags=None,
                       remove_unknown_tags=False, safe_attrs_only=False)


def clean_attributes(html):
    """
    Strips tags of attributes
    """
    while html_strip.search(html):
        html = html_strip.sub('<\\1\\2>', html)
    return html


def normalize_spaces(s):
    """
    Replaces all sequences of whitespace characters with a single space
    """
    if not s:
        return ''
    return ' '.join(s.split())


class Unparseable(ValueError):
    pass


def describe(node, depth=1):
    """
    Node describer for debug purposes.

    :param node: node to describe
    :param depth: depth of node
    :return: stringified name of node with parents
    """
    if not hasattr(node, 'tag'):
        return "[%s]" % type(node)
    name = node.tag
    if node.get('id', ''):
        name += '#' + node.get('id')
    if node.get('class', ''):
        name += '.' + node.get('class').replace(' ', '.')
    if name[:4] in ['div#', 'div.']:
        name = name[3:]
    if depth and node.getparent() is not None:
        return name + ' - ' + describe(node.getparent(), depth - 1)
    return name


def clean(text):
    """
    Cleans text, removes excess tabs, CRs, spaces

    :param text: raw text string
    :return: clean text string
    """
    text = re.sub('\s*\n\s*', '\n', text)
    text = re.sub('[ \t]{2,}', ' ', text)
    return text.strip()


def text_length(i):
    """
    Calculates the length of "clean" text content of an Element.

    :param i: Element
    :return: length of its clean text
    """
    return len(clean(i.text_content() or ""))


regexp_type = type(re.compile('hello, world'))


def compile_pattern(elements):
    """
    Compiles a list of elements' names into one 'or' regular

    :param elements: list of tag elements
    :return:
    """
    if not elements:
        return None
    if isinstance(elements, regexp_type):
        return elements
    if isinstance(elements, str):
        elements = elements.split(',')
    return re.compile('|'.join([re.escape(x.lower()) for x in elements]), re.U)


def clean_entities(text):
    """
    Cleans text of escaped entities.
    :param text: input text
    :return: text without escaped entities
    """
    for key, seq in ESCAPED_ENTITIES.items():
        for val in seq:
            text = text.replace(val, key)
    return text
