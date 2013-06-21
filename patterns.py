# encoding: utf-8
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab
"""
Library for simplifying common text matching/searching operations, as
well as providing a way of easily doing approximate / fuzzy searches.

Owain Jones [github.com/doomcat]
"""

import re

p_cmd_line_regex = re.compile(r'/(.*)/(.*)$')
p_cmd_flag_regex = re.compile(r'(\w+(?:\:\w+)?),?')
p_regex_regex = re.compile(r'\b(?<!\\)(?<!P\<)[0-9A-Za-z]{2,}\b')
p_word_regex = re.compile(r'[0-9A-Za-z]+')


class FixedPattern(object):
    """Base pattern-matching class."""

    # Flags
    ICASE = 1  # case-insensitive
    WHOLE = 2  # whole string has to match pattern

    def __init__(self, pattern, flags=0):
        self.pattern = pattern
        self.flags = flags

    def matches(self, string):
        """Returns a tuple containing a boolean (whether the string
           matches the pattern or not) and a MatchObject. For
           FixedPatterns the second element is None."""
        pattern = self.pattern
        if self.has(FixedPattern.ICASE):
            pattern = pattern.lower()
            string = string.lower()
        if self.has(FixedPattern.WHOLE):
            return (pattern == string, None)
        return (pattern in string, None)

    def has_flag(self, flag):
        """Check if an instance has a certain flag set"""
        return self.flags & flag == flag


class RegExPattern(FixedPattern):
    """Regular-expression wrapper class."""

    # Extra flags
    MULTI = 3    # multi-line expression
    DOTALL = 4   # dot ('.') character matches everything
    UNICODE = 5
    VERBOSE = 6  # allow multi-line, whitespaced, commented regexes

    @staticmethod
    def _f2rf(flags):
        """Convert our types of flags into re. flags"""
        rf = 0
        translations = {
            1: re.IGNORECASE,
            3: re.MULTILINE,
            4: re.DOTALL,
            5: re.UNICODE,
            6: re.VERBOSE
        }
        for t in translations:
            if flags & t == t:
                rf |= translations[t]

        return rf

    def _compile(self):
        return re.compile(self.pattern, RegExPattern._f2rf(self.flags))

    def __init__(self, pattern, flags=0):
        super(RegExPattern, self).__init__(pattern, flags)
        if self.has_flag(FixedPattern.WHOLE):
            self.pattern = "^%s$" % self.pattern
        self._pattern = self._compile()

    def matches(self, string):
        """Returns a tuple containing a boolean (whether the string
           matches the pattern or not) and a MatchObject."""
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

    DEFAULT_DISTANCE = 3  # default levenshtein distance threshold

    @staticmethod
    def levenshtein(s1, s2):
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

    def __init__(self, pattern, flags=0, max_dist=DEFAULT_DISTANCE):
        super(RegExPattern, self).__init__(pattern, flags)
        self.max_dist = max_dist
        self.words = dict()
        for i, word in enumerate(p_regex_regex.findall(pattern)):
            pattern = pattern.replace(word, r'\w+')
            self.words[i] = word
        if self.has_flag(FixedPattern.WHOLE):
            pattern = "^%s$" % pattern
        self.pattern = pattern
        self._pattern = self._compile()

    def distance(self, string):
        d = 0
        for i, word in enumerate(p_word_regex.findall(string)):
            word1 = self.words[i]
            word2 = word
            if self.has_flag(FixedPattern.ICASE):
                word1 = word1.lower()
                word2 = word2.lower()
            if i not in self.words.keys():
                d += len(word2)
            else:
                d += FuzzyRegExPattern.levenshtein(word1, word2)
        return d

    def matches(self, string):
        match = self.match(string)
        within_distance = (self.distance(string) <= self.max_dist)
        return (within_distance & (match is not None), match)


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
    flag_result = p_cmd_flag_regex.findall(result.group(2))
    flags = {
        "i": FixedPattern.ICASE, "icase": FixedPattern.ICASE,
        "m": RegExPattern.MULTI, "multi": RegExPattern.MULTI,
        "d": RegExPattern.DOTALL, "dotall": RegExPattern.DOTALL,
        "u": RegExPattern.UNICODE, "unicode": RegExPattern.UNICODE,
        "v": RegExPattern.VERBOSE, "verbose": RegExPattern.VERBOSE,
        "w": FixedPattern.WHOLE, "whole": FixedPattern.WHOLE
    }
    f = flag
    for c in flag_result:
        if c in flags.keys():
            f |= flags[c]
    regex = result.group(1)
    for r in flag_result:
        if r.startswith('a') or r.startswith('approx'):
            try:
                dist = int(r.split(':')[1])
            except IndexError:
                dist = FuzzyRegExPattern.DEFAULT_DISTANCE
            return FuzzyRegExPattern(regex, flags=f, max_dist=dist)
    return RegExPattern(regex, flags=f)
