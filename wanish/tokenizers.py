# Natural Language Toolkit: Punkt sentence tokenizer
#
# Copyright (C) 2001-2013 NLTK Project
# Algorithm: Kiss & Strunk (2006)
# Author: Willy <willy@csse.unimelb.edu.au> (original Python port)
#         Steven Bird <stevenbird1@gmail.com> (additions)
#         Edward Loper <edloper@gmail.com> (rewrite)
#         Joel Nothman <jnothman@student.usyd.edu.au> (almost rewrite)
# URL: <http://nltk.org/>

import types
import re
from collections import defaultdict
from re import finditer

######################################################################
# { Orthographic Context Constants
######################################################################
# The following constants are used to describe the orthographic
# contexts in which a word can occur.  BEG=beginning, MID=middle,
# UNK=unknown, UC=uppercase, LC=lowercase, NC=no case.

_ORTHO_BEG_UC = 1 << 1
"""Orthographic context: beginning of a sentence with upper case."""

_ORTHO_MID_UC = 1 << 2
"""Orthographic context: middle of a sentence with upper case."""

_ORTHO_UNK_UC = 1 << 3
"""Orthographic context: unknown position in a sentence with upper case."""

_ORTHO_BEG_LC = 1 << 4
"""Orthographic context: beginning of a sentence with lower case."""

_ORTHO_MID_LC = 1 << 5
"""Orthographic context: middle of a sentence with lower case."""

_ORTHO_UNK_LC = 1 << 6
"""Orthographic context: unknown position in a sentence with lower case."""

_ORTHO_UC = _ORTHO_BEG_UC + _ORTHO_MID_UC + _ORTHO_UNK_UC
"""Orthographic context: occurs with upper case."""

_ORTHO_LC = _ORTHO_BEG_LC + _ORTHO_MID_LC + _ORTHO_UNK_LC
"""Orthographic context: occurs with lower case."""

_ORTHO_MAP = {
    ('initial',  'upper'): _ORTHO_BEG_UC,
    ('internal', 'upper'): _ORTHO_MID_UC,
    ('unknown',  'upper'): _ORTHO_UNK_UC,
    ('initial',  'lower'): _ORTHO_BEG_LC,
    ('internal', 'lower'): _ORTHO_MID_LC,
    ('unknown',  'lower'): _ORTHO_UNK_LC,
}
"""A map from context position and first-letter case to the
appropriate orthographic context flag."""

# } (end orthographic context constants)
######################################################################

######################################################################
# { Decision reasons for debugging
######################################################################

REASON_DEFAULT_DECISION = 'default decision'
REASON_KNOWN_COLLOCATION = 'known collocation (both words)'
REASON_ABBR_WITH_ORTHOGRAPHIC_HEURISTIC = 'abbreviation + orthographic heuristic'
REASON_ABBR_WITH_SENTENCE_STARTER = 'abbreviation + frequent sentence starter'
REASON_INITIAL_WITH_ORTHOGRAPHIC_HEURISTIC = 'initial + orthographic heuristic'
REASON_NUMBER_WITH_ORTHOGRAPHIC_HEURISTIC = 'initial + orthographic heuristic'
REASON_INITIAL_WITH_SPECIAL_ORTHOGRAPHIC_HEURISTIC = 'initial + special orthographic heuristic'

######################################################################
# { Language-dependent variables
######################################################################


class PunktLanguageVars(object):
    """
    Stores variables, mostly regular expressions, which may be
    language-dependent for correct application of the algorithm.
    An extension of this class may modify its properties to suit
    a language other than English; an instance can then be passed
    as an argument to PunktSentenceTokenizer and PunktTrainer
    constructors.
    """

    __slots__ = ('_re_period_context', '_re_word_tokenizer')

    def __getstate__(self):
        # All modifications to the class are performed by inheritance.
        # Non-default parameters to be pickled must be defined in the inherited
        # class.
        return 1

    def __setstate__(self, state):
        return 1

    sent_end_chars = ('.', '?', '!')
    """Characters which are candidates for sentence boundaries"""

    @property
    def _re_sent_end_chars(self):
        return '[%s]' % re.escape(''.join(self.sent_end_chars))

    internal_punctuation = ',:;'  # might want to extend this..
    """sentence internal punctuation, which indicates an abbreviation if
    preceded by a period-final token."""

    re_boundary_realignment = re.compile(r'["\')\]}]+?(?:\s+|(?=--)|$)',
                                         re.MULTILINE)
    """Used to realign punctuation that should be included in a sentence
    although it follows the period (or ?, !)."""

    _re_word_start = r"[^\(\"\`{\[:;&\#\*@\)}\]\-,]"
    """Excludes some characters from starting word tokens"""

    _re_non_word_chars = r"(?:[?!)\";}\]\*:@\'\({\[])"
    """Characters that cannot appear within words"""

    _re_multi_char_punct = r"(?:\-{2,}|\.{2,}|(?:\.\s){2,}\.)"
    """Hyphen and ellipsis are multi-character punctuation"""

    _word_tokenize_fmt = r'''(
        %(MultiChar)s
        |
        (?=%(WordStart)s)\S+?   # Accept word characters until end is found
        (?= # Sequences marking a word's end
            \s| # White-space
            $| # End-of-string
            %(NonWord)s|%(MultiChar)s| # Punctuation
            ,(?=$|\s|%(NonWord)s|%(MultiChar)s) # Comma if at end of word
        )
        |
        \S
    )'''
    """Format of a regular expression to split punctuation from words,
    excluding period."""

    def _word_tokenizer_re(self):
        """Compiles and returns a regular expression for word tokenization"""
        try:
            return self._re_word_tokenizer
        except AttributeError:
            self._re_word_tokenizer = re.compile(
                self._word_tokenize_fmt %
                {
                    'NonWord': self._re_non_word_chars,
                    'MultiChar': self._re_multi_char_punct,
                    'WordStart': self._re_word_start,
                },
                re.UNICODE | re.VERBOSE
        )
        return self._re_word_tokenizer

    def word_tokenize(self, s):
        """Tokenize a string to split off punctuation other than periods"""
        return self._word_tokenizer_re().findall(s)

    _period_context_fmt = r"""
        \S*                         # some word material
        %(SentEndChars)s            # a potential sentence ending
        (?=(?P<after_tok>
            %(NonWord)s             # either other punctuation
            |
            \s+(?P<next_tok>\S+)    # or whitespace and some other token
        ))"""

    """Format of a regular expression to find contexts including possible
    sentence boundaries. Matches token which the possible sentence boundary
    ends, and matches the following token within a lookahead expression."""

    def period_context_re(self):
        """Compiles and returns a regular expression to find contexts
        including possible sentence boundaries."""
        try:
            return self._re_period_context
        except:
            self._re_period_context = re.compile(
                self._period_context_fmt %
                {
                    'NonWord': self._re_non_word_chars,
                    'SentEndChars': self._re_sent_end_chars,
                },
                re.UNICODE | re.VERBOSE)
            return self._re_period_context

_re_non_punct = re.compile(r'[^\W\d]', re.UNICODE)
"""Matches token types that are not merely punctuation. (Types for
numeric tokens are changed to ##number## and hence contain alpha.)"""

# }
######################################################################


def _pair_iter(it):
    """
    Yields pairs of tokens from the given iterator such that each input
    token will appear as the first element in a yielded tuple. The last
    pair will have None as its second element.
    """
    it = iter(it)
    prev = next(it)
    for el in it:
        yield (prev, el)
        prev = el
    yield (prev, None)


class PunktParameters(object):
    """Stores data used to perform sentence boundary detection with Punkt."""

    def __init__(self):
        self.abbrev_types = set()
        """A set of word types for known abbreviations."""

        self.collocations = set()
        """A set of word type tuples for known common collocations
        where the first word ends in a period.  E.g., ('S.', 'Bach')
        is a common collocation in a text that discusses 'Johann
        S. Bach'.  These count as negative evidence for sentence
        boundaries."""

        self.sent_starters = set()
        """A set of word types for words that often appear at the
        beginning of sentences."""

        self.ortho_context = defaultdict(int)
        """A dictionary mapping word types to the set of orthographic
        contexts that word type appears in.  Contexts are represented
        by adding orthographic context flags: ..."""

    def clear_abbrevs(self):
        self.abbrev_types = set()

    def clear_collocations(self):
        self.collocations = set()

    def clear_sent_starters(self):
        self.sent_starters = set()

    def clear_ortho_context(self):
        self.ortho_context = defaultdict(int)

    def add_ortho_context(self, typ, flag):
        self.ortho_context[typ] |= flag

    def _debug_ortho_context(self, typ):
        c = self.ortho_context[typ]
        if c & _ORTHO_BEG_UC:
            yield 'BEG-UC'
        if c & _ORTHO_MID_UC:
            yield 'MID-UC'
        if c & _ORTHO_UNK_UC:
            yield 'UNK-UC'
        if c & _ORTHO_BEG_LC:
            yield 'BEG-LC'
        if c & _ORTHO_MID_LC:
            yield 'MID-LC'
        if c & _ORTHO_UNK_LC:
            yield 'UNK-LC'


# @python_2_unicode_compatible
class PunktToken(object):
    """Stores a token of text with annotations produced during
    sentence boundary detection."""
    _properties = [
        'parastart',
        'linestart',
        'sentbreak',
        'abbr',
        'ellipsis'
    ]
    __slots__ = ['tok', 'type', 'period_final'] + _properties

    def __init__(self, tok, **params):
        self.tok = tok
        self.type = self._get_type(tok)
        self.period_final = tok.endswith('.')

        for p in self._properties:
            setattr(self, p, None)

        for k in params:
            setattr(self, k, params[k])

    # ////////////////////////////////////////////////////////////
    # { Regular expressions for properties
    # ////////////////////////////////////////////////////////////
    # Note: [A-Za-z] is approximated by [^\W\d] in the general case.
    _RE_ELLIPSIS = re.compile(r'\.\.+$')
    _RE_NUMERIC = re.compile(r'^-?[\.,]?\d[\d,\.-]*\.?$')
    _RE_INITIAL = re.compile(r'[^\W\d]\.$', re.UNICODE)
    _RE_ALPHA = re.compile(r'[^\W\d]+$', re.UNICODE)

    # ////////////////////////////////////////////////////////////
    # { Derived properties
    # ////////////////////////////////////////////////////////////

    def _get_type(self, tok):
        """Returns a case-normalized representation of the token."""
        return self._RE_NUMERIC.sub('##number##', tok.lower())

    @property
    def type_no_period(self):
        """ The type with its final period removed if it has one. """
        if len(self.type) > 1 and self.type[-1] == '.':
            return self.type[:-1]
        return self.type

    @property
    def type_no_sentperiod(self):
        """ The type with its final period removed if it is marked as a
        sentence break. """
        if self.sentbreak:
            return self.type_no_period
        return self.type

    @property
    def first_upper(self):
        """True if the token's first character is uppercase."""
        return self.tok[0].isupper()

    @property
    def first_lower(self):
        """True if the token's first character is lowercase."""
        return self.tok[0].islower()

    @property
    def first_case(self):
        if self.first_lower:
            return 'lower'
        elif self.first_upper:
            return 'upper'
        return 'none'

    @property
    def is_ellipsis(self):
        """True if the token text is that of an ellipsis."""
        return self._RE_ELLIPSIS.match(self.tok)

    @property
    def is_number(self):
        """True if the token text is that of a number."""
        return self.type.startswith('##number##')

    @property
    def is_initial(self):
        """True if the token text is that of an initial."""
        return self._RE_INITIAL.match(self.tok)

    @property
    def is_alpha(self):
        """True if the token text is all alphabetic."""
        return self._RE_ALPHA.match(self.tok)

    @property
    def is_non_punct(self):
        """True if the token is either a number or is alphabetic."""
        return _re_non_punct.search(self.type)

    # ////////////////////////////////////////////////////////////
    # { String representation
    # ////////////////////////////////////////////////////////////

    def __repr__(self):
        """ A string representation of the token that can reproduce it
        with eval(), which lists all the token's non-default
        annotations.
        """
        typestr = (' type=%s,' % self.type
                   if self.type != self.tok else '')

        propvals = ', '.join(
            '%s=%s' % (p, getattr(self, p))
            for p in self._properties
            if getattr(self, p)
        )

        return '%s(%s,%s %s)' % (self.__class__.__name__,
                                 self.tok,
                                 typestr,
                                 propvals)

    def __str__(self):
        """
        A string representation akin to that used by Kiss and Strunk.
        """
        res = self.tok
        if self.abbr:
            res += '<A>'
        if self.ellipsis:
            res += '<E>'
        if self.sentbreak:
            res += '<S>'
        return res


class PunktBaseClass(object):
    """
    Includes common components of PunktTrainer and PunktSentenceTokenizer.
    """

    def __init__(self, lang_vars=PunktLanguageVars(), token_cls=PunktToken, params=PunktParameters()):
        self._params = params
        self._lang_vars = lang_vars
        self._Token = token_cls
        """The collection of parameters that determines the behavior
        of the punkt tokenizer."""

    # ////////////////////////////////////////////////////////////
    # { Word tokenization
    # ////////////////////////////////////////////////////////////

    def _tokenize_words(self, plaintext):
        """
        Divide the given text into tokens, using the punkt word
        segmentation regular expression, and generate the resulting list
        of tokens augmented as three-tuples with two boolean values for whether
        the given token occurs at the start of a paragraph or a new line,
        respectively.
        """
        parastart = False
        for line in plaintext.split('\n'):
            if line.strip():
                line_toks = iter(self._lang_vars.word_tokenize(line))

                yield self._Token(next(line_toks), parastart=parastart, linestart=True)
                parastart = False

                for t in line_toks:
                    yield self._Token(t)
            else:
                parastart = True

    # ////////////////////////////////////////////////////////////
    # { Annotation Procedures
    # ////////////////////////////////////////////////////////////

    def _annotate_first_pass(self, tokens):
        """
        Perform the first pass of annotation, which makes decisions
        based purely based on the word type of each word:

          - '?', '!', and '.' are marked as sentence breaks.
          - sequences of two or more periods are marked as ellipsis.
          - any word ending in '.' that's a known abbreviation is
            marked as an abbreviation.
          - any other word ending in '.' is marked as a sentence break.

        Return these annotations as a tuple of three sets:

          - sentbreak_toks: The indices of all sentence breaks.
          - abbrev_toks: The indices of all abbreviations.
          - ellipsis_toks: The indices of all ellipsis marks.
        """
        for aug_tok in tokens:
            self._first_pass_annotation(aug_tok)
            yield aug_tok

    def _first_pass_annotation(self, aug_tok):
        """
        Performs type-based annotation on a single token.
        """

        tok = aug_tok.tok

        if tok in self._lang_vars.sent_end_chars:
            aug_tok.sentbreak = True
        elif aug_tok.is_ellipsis:
            aug_tok.ellipsis = True
        elif aug_tok.period_final and not tok.endswith('..'):
            if (tok[:-1].lower() in self._params.abbrev_types or
                        tok[:-1].lower().split('-')[-1] in self._params.abbrev_types):

                aug_tok.abbr = True
            else:
                aug_tok.sentbreak = True

        return


def _mro(cls):
    if isinstance(cls, type):
        return cls.__mro__
    else:
        mro = [cls]
        for base in cls.__bases__:
            mro.extend(_mro(base))
        return mro


def overridden(method):

    # [xx] breaks on classic classes!
    if isinstance(method, types.MethodType) and method.im_class is not None:
        name = method.__name__
        funcs = [cls.__dict__[name]
                 for cls in _mro(method.im_class)
                 if name in cls.__dict__]
        return len(funcs) > 1
    else:
        raise TypeError('Expected an instance method.')


class TokenizerI(object):
    """
    A processing interface for tokenizing a string.
    Subclasses must define ``tokenize()`` or ``batch_tokenize()`` (or both).
    """
    def tokenize(self, s):
        """
        Return a tokenized copy of *s*.

        :rtype: list of str
        """
        if overridden(self.batch_tokenize):
            return self.batch_tokenize([s])[0]
        else:
            raise NotImplementedError()

    def span_tokenize(self, s):
        """
        Identify the tokens using integer offsets ``(start_i, end_i)``,
        where ``s[start_i:end_i]`` is the corresponding token.

        :rtype: iter(tuple(int, int))
        """
        raise NotImplementedError()

    def batch_tokenize(self, strings):
        """
        Apply ``self.tokenize()`` to each element of ``strings``.  I.e.:

            return [self.tokenize(s) for s in strings]

        :rtype: list(list(str))
        """
        return [self.tokenize(s) for s in strings]

    def batch_span_tokenize(self, strings):
        """
        Apply ``self.span_tokenize()`` to each element of ``strings``.  I.e.:

            return [self.span_tokenize(s) for s in strings]

        :rtype: iter(list(tuple(int, int)))
        """
        for s in strings:
            yield list(self.span_tokenize(s))


class PunktSentenceTokenizer(PunktBaseClass, TokenizerI):
    """
    A sentence tokenizer which uses an unsupervised algorithm to build
    a model for abbreviation words, collocations, and words that start
    sentences; and then uses that model to find sentence boundaries.
    This approach has been shown to work well for many European
    languages.
    """
    def __init__(self, lang_vars=PunktLanguageVars(), token_cls=PunktToken):
        PunktBaseClass.__init__(self, lang_vars=lang_vars, token_cls=token_cls)

    # ////////////////////////////////////////////////////////////
    # { Tokenization
    # ////////////////////////////////////////////////////////////

    def tokenize(self, text, realign_boundaries=True):
        """
        Given a text, returns a list of the sentences in that text.
        """
        return list(self.sentences_from_text(text, realign_boundaries))

    def debug_decisions(self, text):
        """
        Classifies candidate periods as sentence breaks, yielding a dict for
        each that may be used to understand why the decision was made.
        See format_debug_decision() to help make this output readable.
        """
        for match in self._lang_vars.period_context_re().finditer(text):
            decision_text = match.group() + match.group('after_tok')
            tokens = self._tokenize_words(decision_text)
            tokens = list(self._annotate_first_pass(tokens))
            while not tokens[0].period_final:
                tokens.pop(0)
            yield dict(period_index=match.end() - 1,
                       text=decision_text,
                       type1=tokens[0].type,
                       type2=tokens[1].type,
                       type1_in_abbrs=bool(tokens[0].abbr),
                       type1_is_initial=bool(tokens[0].is_initial),
                       type2_is_sent_starter=tokens[1].type_no_sentperiod in self._params.sent_starters,
                       type2_ortho_heuristic=self._ortho_heuristic(tokens[1]),
                       type2_ortho_contexts=set(self._params._debug_ortho_context(tokens[1].type_no_sentperiod)),
                       collocation=(tokens[0].type_no_sentperiod, tokens[1].type_no_sentperiod) in self._params.collocations,
                       reason=self._second_pass_annotation(tokens[0], tokens[1]) or REASON_DEFAULT_DECISION,
                       break_decision=tokens[0].sentbreak, )

    def span_tokenize(self, text):
        """
        Given a text, returns a list of the (start, end) spans of sentences in the text.
        """
        return [(sl.start, sl.stop) for sl in self._slices_from_text(text)]

    def sentences_from_text(self, text, realign_boundaries=True):
        """
        Given a text, generates the sentences in that text by only
        testing candidate sentence breaks. If realign_boundaries is
        True, includes in the sentence closing punctuation that
        follows the period.
        """
        sents = [text[sl] for sl in self._slices_from_text(text)]
        if realign_boundaries:
            sents = self._realign_boundaries(sents)
            return sents

    def _slices_from_text(self, text):
        last_break = 0
        for match in self._lang_vars.period_context_re().finditer(text):
            context = match.group() + match.group('after_tok')
            if self.text_contains_sentbreak(context):
                yield slice(last_break, match.end())
                if match.group('next_tok'):
                    # next sentence starts after whitespace
                    last_break = match.start('next_tok')
                else:
                    # next sentence starts at following punctuation
                    last_break = match.end()
        yield slice(last_break, len(text))

    def _realign_boundaries(self, sents):
        """
        Attempts to realign punctuation that falls after the period but
        should otherwise be included in the same sentence.

        For example: "(Sent1.) Sent2." will otherwise be split as::

            ["(Sent1.", ") Sent1."].

        This method will produce::

            ["(Sent1.)", "Sent2."].
        """
        realign = 0
        for s1, s2 in _pair_iter(sents):
            s1 = s1[realign:]
            if not s2:
                if s1:
                    yield s1
                continue

            m = self._lang_vars.re_boundary_realignment.match(s2)
            if m:
                yield s1 + m.group(0).strip()
                realign = m.end()
            else:
                realign = 0
                if s1:
                    yield s1

    def text_contains_sentbreak(self, text):
        """
        Returns True if the given text includes a sentence break.
        """
        found = False  # used to ignore last token
        for t in self._annotate_tokens(self._tokenize_words(text)):
            if found:
                return True
            if t.sentbreak:
                found = True
        return False

    def sentences_from_text_legacy(self, text):
        """
        Given a text, generates the sentences in that text. Annotates all
        tokens, rather than just those with possible sentence breaks. Should
        produce the same results as ``sentences_from_text``.
        """
        tokens = self._annotate_tokens(self._tokenize_words(text))
        return self._build_sentence_list(text, tokens)

    def sentences_from_tokens(self, tokens):
        """
        Given a sequence of tokens, generates lists of tokens, each list
        corresponding to a sentence.
        """
        tokens = iter(self._annotate_tokens(self._Token(t) for t in tokens))
        sentence = []
        for aug_tok in tokens:
            sentence.append(aug_tok.tok)
            if aug_tok.sentbreak:
                yield sentence
                sentence = []
        if sentence:
            yield sentence

    def _annotate_tokens(self, tokens):
        """
        Given a set of tokens augmented with markers for line-start and
        paragraph-start, returns an iterator through those tokens with full
        annotation including predicted sentence breaks.
        """
        # Make a preliminary pass through the document, marking likely
        # sentence breaks, abbreviations, and ellipsis tokens.
        tokens = self._annotate_first_pass(tokens)

        # Make a second pass through the document, using token context
        # information to change our preliminary decisions about where
        # sentence breaks, abbreviations, and ellipsis occurs.
        tokens = self._annotate_second_pass(tokens)

        return tokens

    def _build_sentence_list(self, text, tokens):
        """
        Given the original text and the list of augmented word tokens,
        construct and return a tokenized list of sentence strings.
        """
        # Most of the work here is making sure that we put the right
        # pieces of whitespace back in all the right places.

        # Our position in the source text, used to keep track of which
        # whitespace to add:
        pos = 0

        # A regular expression that finds pieces of whitespace:
        WS_REGEXP = re.compile(r'\s*')

        sentence = ''
        for aug_tok in tokens:
            tok = aug_tok.tok

            # Find the whitespace before this token, and update pos.
            ws = WS_REGEXP.match(text, pos).group()
            pos += len(ws)

            # Some of the rules used by the punkt word tokenizer
            # strip whitespace out of the text, resulting in tokens
            # that contain whitespace in the source text.  If our
            # token doesn't match, see if adding whitespace helps.
            # If so, then use the version with whitespace.
            if text[pos:pos+len(tok)] != tok:
                pat = '\s*'.join(re.escape(c) for c in tok)
                m = re.compile(pat).match(text,pos)
                if m: tok = m.group()

            # Move our position pointer to the end of the token.
            assert text[pos:pos+len(tok)] == tok
            pos += len(tok)

            # Add this token.  If it's not at the beginning of the
            # sentence, then include any whitespace that separated it
            # from the previous token.
            if sentence:
                sentence += ws
            sentence += tok

            # If we're at a sentence break, then start a new sentence.
            if aug_tok.sentbreak:
                yield sentence
                sentence = ''

        # If the last sentence is emtpy, discard it.
        if sentence:
            yield sentence

    # ////////////////////////////////////////////////////////////
    # { Customization Variables
    # ////////////////////////////////////////////////////////////

    PUNCTUATION = tuple(';:,.!?')

    # ////////////////////////////////////////////////////////////
    # { Annotation Procedures
    # ////////////////////////////////////////////////////////////

    def _annotate_second_pass(self, tokens):
        """
        Performs a token-based classification (section 4) over the given
        tokens, making use of the orthographic heuristic (4.1.1), collocation
        heuristic (4.1.2) and frequent sentence starter heuristic (4.1.3).
        """
        for t1, t2 in _pair_iter(tokens):
            self._second_pass_annotation(t1, t2)
            yield t1

    def _second_pass_annotation(self, aug_tok1, aug_tok2):
        """
        Performs token-based classification over a pair of contiguous tokens
        updating the first.
        """
        # Is it the last token? We can't do anything then.
        if not aug_tok2:
            return

        tok = aug_tok1.tok
        if not aug_tok1.period_final:
            # We only care about words ending in periods.
            return

        typ = aug_tok1.type_no_period
        next_tok = aug_tok2.tok
        next_typ = aug_tok2.type_no_sentperiod
        tok_is_initial = aug_tok1.is_initial

        # [4.1.2. Collocation Heuristic] If there's a
        # collocation between the word before and after the
        # period, then label tok as an abbreviation and NOT
        # a sentence break. Note that collocations with
        # frequent sentence starters as their second word are
        # excluded in training.
        if (typ, next_typ) in self._params.collocations:
            aug_tok1.sentbreak = False
            aug_tok1.abbr = True
            return REASON_KNOWN_COLLOCATION

        # [4.2. Token-Based Reclassification of Abbreviations] If
        # the token is an abbreviation or an ellipsis, then decide
        # whether we should *also* classify it as a sentbreak.
        if ((aug_tok1.abbr or aug_tok1.ellipsis) and
                (not tok_is_initial)):
            # [4.1.1. Orthographic Heuristic] Check if there's
            # orthogrpahic evidence about whether the next word
            # starts a sentence or not.
            is_sent_starter = self._ortho_heuristic(aug_tok2)
            if is_sent_starter is True:
                aug_tok1.sentbreak = True
                return REASON_ABBR_WITH_ORTHOGRAPHIC_HEURISTIC

            # [4.1.3. Frequent Sentence Starter Heruistic] If the
            # next word is capitalized, and is a member of the
            # frequent-sentence-starters list, then label tok as a
            # sentence break.
            if ( aug_tok2.first_upper and
                 next_typ in self._params.sent_starters):
                aug_tok1.sentbreak = True
                return REASON_ABBR_WITH_SENTENCE_STARTER

        # [4.3. Token-Based Detection of Initials and Ordinals]
        # Check if any initials or ordinals tokens that are marked
        # as sentbreaks should be reclassified as abbreviations.
        if tok_is_initial or typ == '##number##':

            # [4.1.1. Orthographic Heuristic] Check if there's
            # orthogrpahic evidence about whether the next word
            # starts a sentence or not.
            is_sent_starter = self._ortho_heuristic(aug_tok2)

            if is_sent_starter is False:
                aug_tok1.sentbreak = False
                aug_tok1.abbr = True
                if tok_is_initial:
                    return REASON_INITIAL_WITH_ORTHOGRAPHIC_HEURISTIC
                else:
                    return REASON_NUMBER_WITH_ORTHOGRAPHIC_HEURISTIC

            # Special heuristic for initials: if orthogrpahic
            # heuristc is unknown, and next word is always
            # capitalized, then mark as abbrev (eg: J. Bach).
            if (is_sent_starter == 'unknown' and tok_is_initial and
                aug_tok2.first_upper and
                    not (self._params.ortho_context[next_typ] & _ORTHO_LC)):
                aug_tok1.sentbreak = False
                aug_tok1.abbr = True
                return REASON_INITIAL_WITH_SPECIAL_ORTHOGRAPHIC_HEURISTIC

        return

    def _ortho_heuristic(self, aug_tok):
        """
        Decide whether the given token is the first token in a sentence.
        """
        # Sentences don't start with punctuation marks:
        if aug_tok.tok in self.PUNCTUATION:
            return False

        ortho_context = self._params.ortho_context[aug_tok.type_no_sentperiod]

        # If the word is capitalized, occurs at least once with a
        # lower case first letter, and never occurs with an upper case
        # first letter sentence-internally, then it's a sentence starter.
        if (aug_tok.first_upper and
            (ortho_context & _ORTHO_LC) and
                not (ortho_context & _ORTHO_MID_UC)):
            return True

        # If the word is lower case, and either (a) we've seen it used
        # with upper case, or (b) we've never seen it used
        # sentence-initially with lower case, then it's not a sentence
        # starter.
        if (aug_tok.first_lower and
            ((ortho_context & _ORTHO_UC) or
                not (ortho_context & _ORTHO_BEG_LC))):
            return False

        # Otherwise, we're not sure.
        return 'unknown'


def regexp_span_tokenize(s, regexp):
    r"""
    Return the offsets of the tokens in *s*, as a sequence of ``(start, end)``
    tuples, by splitting the string at each successive match of *regexp*.

    :param s: the string to be tokenized
    :type s: str
    :param regexp: regular expression that matches token separators
    :type regexp: str
    :rtype: iter(tuple(int, int))
    """
    left = 0
    for m in finditer(regexp, s):
        right, nxt = m.span()
        if right != 0:
            yield left, right
        left = nxt
    yield left, len(s)


def convert_regexp_to_nongrouping(pattern):

    # Sanity check: back-references are not allowed!
    for s in re.findall(r'\\.|\(\?P=', pattern):
        if s[1] in '0123456789' or s == '(?P=':
            raise ValueError('Regular expressions with back-references '
                             'are not supported: %r' % pattern)

    # This regexp substitution function replaces the string '('
    # with the string '(?:', but otherwise makes no changes.
    def subfunc(m):
        return re.sub('^\((\?P<[^>]*>)?$', '(?:', m.group())

    # Scan through the regular expression.  If we see any backslashed
    # characters, ignore them.  If we see a named group, then
    # replace it with "(?:".  If we see any open parens that are part
    # of an extension group, ignore those too.  But if we see
    # any other open paren, replace it with "(?:")
    return re.sub(r'''(?x)
        \\.           |  # Backslashed character
        \(\?P<[^>]*>  |  # Named group
        \(\?          |  # Extension group
        \(               # Grouping parenthasis''', subfunc, pattern)


class RegexpTokenizer(TokenizerI):
    """
    A tokenizer that splits a string using a regular expression, which
    matches either the tokens or the separators between tokens.

    :type pattern: str
    :param pattern: The pattern used to build this tokenizer.
        (This pattern may safely contain grouping parentheses.)
    :type gaps: bool
    :param gaps: True if this tokenizer's pattern should be used
        to find separators between tokens; False if this
        tokenizer's pattern should be used to find the tokens
        themselves.
    :type discard_empty: bool
    :param discard_empty: True if any empty tokens `''`
        generated by the tokenizer should be discarded.  Empty
        tokens can only be generated if `_gaps == True`.
    :type flags: int
    :param flags: The regexp flags used to compile this
        tokenizer's pattern.  By default, the following flags are
        used: `re.UNICODE | re.MULTILINE | re.DOTALL`.

    """
    def __init__(self, pattern, gaps=False, discard_empty=True,
                 flags=re.UNICODE | re.MULTILINE | re.DOTALL):
        # If they gave us a regexp object, extract the pattern.
        pattern = getattr(pattern, 'pattern', pattern)

        self._pattern = pattern
        self._gaps = gaps
        self._discard_empty = discard_empty
        self._flags = flags
        self._regexp = None

        # Remove grouping parentheses -- if the regexp contains any
        # grouping parentheses, then the behavior of re.findall and
        # re.split will change.
        nongrouping_pattern = convert_regexp_to_nongrouping(pattern)

        try:
            self._regexp = re.compile(nongrouping_pattern, flags)
        except re.error as e:
            raise ValueError('Error in regular expression %r: %s' %
                             (pattern, e))

    def tokenize(self, text):
        # If our regexp matches gaps, use re.split:
        if self._gaps:
            if self._discard_empty:
                return [tok for tok in self._regexp.split(text) if tok]
            else:
                return self._regexp.split(text)

        # If our regexp matches tokens, use re.findall:
        else:
            return self._regexp.findall(text)

    def span_tokenize(self, text):
        if self._gaps:
            for left, right in regexp_span_tokenize(text, self._regexp):
                if not (self._discard_empty and left == right):
                    yield left, right
        else:
            for m in re.finditer(self._regexp, text):
                yield m.span()

    def __repr__(self):
        return ('%s(pattern=%r, gaps=%r, discard_empty=%r, flags=%r)' %
                (self.__class__.__name__, self._pattern, self._gaps,
                 self._discard_empty, self._flags))


# Natural Language Toolkit: Tokenizers
#
# Copyright (C) 2001-2013 NLTK Project
# Author: Edward Loper <edloper@gmail.com>
#         Michael Heilman <mheilman@cmu.edu> (re-port from http://www.cis.upenn.edu/~treebank/tokenizer.sed)
#
# URL: <http://nltk.sourceforge.net>
# For license information, see LICENSE.TXT
#
# Penn Treebank Tokenizer
#
# The Treebank tokenizer uses regular expressions to tokenize text as in Penn Treebank.
# This implementation is a port of the tokenizer sed script written by Robert McIntyre
# and available at http://www.cis.upenn.edu/~treebank/tokenizer.sed.

class TreebankWordTokenizer(TokenizerI):
    """
    The Treebank tokenizer uses regular expressions to tokenize text as in Penn Treebank.
    This is the method that is invoked by ``word_tokenize()``.  It assumes that the
    text has already been segmented into sentences, e.g. using ``sent_tokenize()``.

    This tokenizer performs the following steps:

    - split standard contractions, e.g. ``don't`` -> ``do n't`` and ``they'll`` -> ``they 'll``
    - treat most punctuation characters as separate tokens
    - split off commas and single quotes, when followed by whitespace
    - separate periods that appear at the end of line

        >>> from wanish.tokenizers import TreebankWordTokenizer
        >>> s = '''Good muffins cost $3.88\\nin New York.  Please buy me\\ntwo of them.\\nThanks.'''
        >>> TreebankWordTokenizer().tokenize(s)
        ['Good', 'muffins', 'cost', '$', '3.88', 'in', 'New', 'York.', 'Please', 'buy', 'me', 'two', 'of', 'them.', 'Thanks', '.']
        >>> s = "They'll save and invest more."
        >>> TreebankWordTokenizer().tokenize(s)
        ['They', "'ll", 'save', 'and', 'invest', 'more', '.']
    """

    # List of contractions adapted from Robert MacIntyre's tokenizer.
    CONTRACTIONS2 = [re.compile(r"(?i)\b(can)(not)\b"),
                     re.compile(r"(?i)\b(d)('ye)\b"),
                     re.compile(r"(?i)\b(gim)(me)\b"),
                     re.compile(r"(?i)\b(gon)(na)\b"),
                     re.compile(r"(?i)\b(got)(ta)\b"),
                     re.compile(r"(?i)\b(lem)(me)\b"),
                     re.compile(r"(?i)\b(mor)('n)\b"),
                     re.compile(r"(?i)\b(wan)(na) ")]
    CONTRACTIONS3 = [re.compile(r"(?i) ('t)(is)\b"),
                     re.compile(r"(?i) ('t)(was)\b")]
    CONTRACTIONS4 = [re.compile(r"(?i)\b(whad)(dd)(ya)\b"),
                     re.compile(r"(?i)\b(wha)(t)(cha)\b")]

    def tokenize(self, text):
        # starting quotes
        text = re.sub(r'^\"', r'``', text)
        text = re.sub(r'(``)', r' \1 ', text)
        text = re.sub(r'([ (\[{<])"', r'\1 `` ', text)

        # punctuation
        text = re.sub(r'([:,])([^\d])', r' \1 \2', text)
        text = re.sub(r'\.\.\.', r' ... ', text)
        text = re.sub(r'[;@#$%&]', r' \g<0> ', text)
        text = re.sub(r'([^\.])(\.)([\]\)}>"\']*)\s*$', r'\1 \2\3 ', text)
        text = re.sub(r'[?!]', r' \g<0> ', text)

        text = re.sub(r"([^'])' ", r"\1 ' ", text)

        # parens, brackets, etc.
        text = re.sub(r'[\]\[\(\)\{\}\<\>]', r' \g<0> ', text)
        text = re.sub(r'--', r' -- ', text)

        # add extra space to make things easier
        text = " " + text + " "

        # ending quotes
        text = re.sub(r'"', " '' ", text)
        text = re.sub(r'(\S)(\'\')', r'\1 \2 ', text)

        text = re.sub(r"([^' ])('[sS]|'[mM]|'[dD]|') ", r"\1 \2 ", text)
        text = re.sub(r"([^' ])('ll|'LL|'re|'RE|'ve|'VE|n't|N'T) ", r"\1 \2 ",
                      text)

        for regexp in self.CONTRACTIONS2:
            text = regexp.sub(r' \1 \2 ', text)
        for regexp in self.CONTRACTIONS3:
            text = regexp.sub(r' \1 \2 ', text)

        # We are not using CONTRACTIONS4 since
        # they are also commented out in the SED scripts
        # for regexp in self.CONTRACTIONS4:
        #     text = regexp.sub(r' \1 \2 \3 ', text)

        return text.split()