# encoding: utf-8
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab
"""
Library for simplifying common text matching/searching operations, as
well as providing a way of easily doing approximate / fuzzy searches.

Owain Jones [github.com/doomcat]
"""

import re

p_cmd_line_regex = re.compile(r'/(.*)/((\w)\:?(\d+)?,?)*$')
p_regex_regex = re.compile(r'\b(?<!\\)(?<!P\<)[0-9A-Za-z]{2,}\b')
p_word_regex = re.compile(r'[0-9A-Za-z]+')


class FixedPattern(object):
    """Base pattern-matching class."""

    # Flags
    CASEI = 1  # case-insensitive
    WHOLE = 2  # whole string has to match pattern

    def __init__(self, pattern, flags=0):
        self.pattern = pattern
        self.flags = flags

    def matches(self, string):
        pattern = self.pattern
        if self.flags & FixedPattern.CASEI == FixedPattern.CASEI:
            pattern = pattern.lower()
            string = string.lower()
        if self.flags & FixedPattern.WHOLE == FixedPattern.WHOLE:
            return (pattern == string, None)
        return (pattern in string, None)

    def has(self, flag):
        """Check if an instance has a certain flag set"""
        return self.flags & flag == flag


class RegExPattern(FixedPattern):
    """Regular-expression wrapper class."""

    # Extra flags
    MULTI = 3    # multi-line expression
    DOTALL = 4   # dot ('.') character matches everything
    UNICODE = 5
    VERBOSE = 6  # allow multi-line, whitespaced, commented regexes

    @classmethod
    def _f2rf(cls, flags):
        """Convert our types of flags into re. flags"""
        rf = 0
        if flags & RegExPattern.CASEI == RegExPattern.CASEI:
            rf |= re.IGNORECASE
        if flags & RegExPattern.MULTI == RegExPattern.MULTI:
            rf |= re.MULTILINE
        if flags & RegExPattern.DOTALL == RegExPattern.DOTALL:
            rf |= re.DOTALL
        if flags & RegExPattern.UNICODE == RegExPattern.UNICODE:
            rf |= re.UNICODE
        if flags & RegExPattern.VERBOSE == RegExPattern.VERBOSE:
            rf |= re.VERBOSE
        return rf

    def _compile(self):
        return re.compile(self.pattern, RegExPattern._f2rf(self.flags))

    def __init__(self, pattern, flags=0):
        super(RegExPattern, self).__init__(pattern, flags)
        if self.has(FixedPattern.WHOLE):
            self.pattern = "^%s$" % self.pattern
        self._pattern = self._compile()

    def matches(self, string):
        match = self._pattern.match(string)
        return (match is not None, match)

    def match(self, string):
        return self._pattern.match(string)

    def search(self, string):
        return self._pattern.search(string)

    def findall(self, string):
        return self._pattern.findall(string)


class FuzzyRegExPattern(RegExPattern):
    """Stub class."""

    DISTANCE = 3  # default levenshtein distance threshold

    @classmethod
    def levenshtein(cls, s1, s2):
        """Calculates the Levenshtein Distance between two strings.
           Lifted in its entirety from Wikibooks' Levenshtein entry:
           http://bit.ly/bkXrER
        """
        if len(s1) < len(s2):
            return FuzzyRegExPattern.levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def __init__(self, pattern, flags=0, max_dist=DISTANCE):
        super(RegExPattern, self).__init__(pattern, flags)
        self.max_dist = max_dist
        self.words = dict()
        for i, word in enumerate(p_regex_regex.findall(pattern)):
            pattern = pattern.replace(word, r'\w+')
            self.words[i] = word
        if self.has(FixedPattern.WHOLE):
            pattern = "^%s$" % pattern
        self.pattern = pattern
        print self.pattern
        self._pattern = self._compile()

    def distance(self, string):
        d = 0
        for i, word in enumerate(p_word_regex.findall(string)):
            if i not in self.words.keys():
                d += len(word)
            else:
                d += FuzzyRegExPattern.levenshtein(self.words[i], word)
        return d

    def matches(self, string):
        match = self.match(string)
        return (((self.distance(string) <= self.max_dist) &
                 (match is not None)),
                match)


def from_string(string, flag=0):
    """Parses a string to find out what kind of pattern it is.
       Anything not beginning and ending with forward slash (/) is
       treated as a fixed string.
       Anything that DOES begin and end with '/' is treated as a regex.
       Anything past the ending '/' is treated as a flag for the regex.
       Flag 'a' makes the pattern a FuzzyRegExPattern.
    """
    if string is None:
        return None
    result = re.match(p_cmd_line_regex, string)
    if result is None:
        return FixedPattern(string, flags=flag)
    flags = {
        "i": RegExPattern.CASEI,
        "m": RegExPattern.MULTI,
        "d": RegExPattern.DOTALL,
        "u": RegExPattern.UNICODE,
        "v": RegExPattern.VERBOSE,
        "w": FixedPattern.WHOLE
    }
    print result.groups()
    f = flag
    for c in result.group(2):
        if c in flags.keys():
            f |= flags[c]
    regex = result.group(1)
    if 'a' in result.group(2):
        return FuzzyRegExPattern(regex, flags=f)
    return RegExPattern(regex, flags=f)
