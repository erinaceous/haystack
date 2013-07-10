#!/usr/bin/env python2
# encoding: utf-8
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab
"""
Search for a fixed string or a regular expression in a text file.
Whenever an instance is found, backtrack (or go forwards) to find what
request/job/file/pass/whatever was affected (find a related line), using
another fixed string or regular expression.

(Use it to find the filenames associated with a specific kind of error
in giant log files!)

Regular expressions can contain named captures - (?P<name>pattern),
which can be referred to in the output format, for example:
$ haystack.py --first "ana_run exited with unknown status" \\
              --second "/finished processing (?P<pass_name>[\w\.]+)/" \\
              -o "{file}:{second_line_num} -> {pass_name}" -f
              /tmp/workspace/*/*.log

Can also filter out some common spelling mistakes (even inside regular
expressions) by using the 'a' flag at the end of your regex, 'a'
standing for 'approximate'. This expands some literal alphabet
characters in the regex, so if your pattern is '/color/ia' it will
match lines like 'color', 'COLOUR', 'COLLOR', 'Colur' etc.
(This works nicely with awkward words like 'successfully')

TODO: Improve 'approximate search': incorporate patterns.py
TODO: Fix the stdin input: Right now it hangs when it should be reading
      from stdin?
TODO: More streaming of files, less loading whole files at a time. Use
      the readline module!
TODO: Multiple patterns (1-9). Each can have multiple options:
      $ haytack -1 "first pattern" "alt. first pattern" \\
        -2 "middle" -3 "top" "alt. top"

Owain Jones [github.com/doomcat]
"""
__version__ = "1.0"

import gc
import os
import re
import sys
import argparse

gc.disable()  # lol lol lol lol

try:
    from termcolor import colored
    colored = colored
except ImportError:
    from xtermcolor import colorize
    colored = colorize
except ImportError:
    def c(string, color):
        return string
    colored = c

output_format = r"{file}:{first_line_num},{second_line_num}"
output_format += r" {first_line} -> {second_line}"
regex_type = type(re.compile(''))
format_regex = re.compile('\{(\w+)?(\:(\w+))?\}')


def expand_for_typos(string):
    """
    Expand a string into a regular expression fragment based on common
    typos and misspellings. E.g. wrong vowels, too many consonants etc.
    (Works only for English speakers only I guess)
    """
    output = string
    output = re.sub('colou?r', 'colou?r', output, flags=re.IGNORECASE)
    for s in ['[SsZz]+', '[Tt]+', '[CcKk]+', '[Ll]+', '[EeIi]', '[OoUu]',
              '[Nn]+', '[Ff]+']:
        output = re.sub(s, s, output, flags=re.IGNORECASE)
    return output


def format(string, dictionary):
    """
    Formats a string by replacing instances of {variable} with the
    contents of those variables. If a variable referred to is not found,
    just omit it from the string. This is different to str.format()
    which throws a KeyError in such cases.
    """
    for variable in re.findall(format_regex, string):
        variable, suffix, color = variable
        value = ''
        if variable in dictionary.keys():
            value = dictionary[variable]
        value = str(value)
        if color != '':
            value = colored(value, color)
        string = string.replace('{' + variable + suffix + '}', value)
    return string


def get_file(path):
    """
    Looks for a path. If path is not a file or can't be read for any
    reason, returns an empty list. If path is '-', return
    sys.stdin.readlines(). Otherwise, return list of lines in that file.
    """
    if path == '-':
        return sys.stdin.readlines()
    try:
        return open(path, 'r').readlines()
    except:
        return []


def search(input, first_pattern, second_pattern, output_format=output_format,
           instant=False, forwards=False, max_results=-1, context=True):
    """
    Searches for instances of 'first_pattern' -- if a line contains that
    fixed string or regular expression, then backtrack back up the file
    until another line is found that contains another string/pattern
    ('second_pattern') and then adds either the matching line or the
    matching part of that line to a list.
    If one of the input paths is simpy '-', then that will be treated as
    a request to read from stdin.

    Arguments:
    input:    The file to read
    first_pattern:   A fixed string or regular expression to try and
                     match each line against.
    second_pattern:  Another fixed string/regex that will be searched
                     for when an instance of first_pattern is found.
    output_format:   The format to output the matching lines in. The
                     string you pass to this argument will be formatted
                     -- '{second_line}\n' will print each line that
                     contains a match.
                     '{file}:{second_line_num} {second_line}\n' will
                     print the name of the log, the line number on which
                     the second pattern was found, and the line itself.
    instant:   If True, don't append results to a list. Just print them
               to stdout straight away.
    forwards:  If True, search forwards from a matching first_pattern
               line to find a line that matches second_pattern, rather
               than backtracking back up the file.
    max_results:  Maximum number of results to return. Function will
                  stop searching as soon as this number is reached.
    context:    If True, add all lines between the first and second
                match as a variable '{context}' that can be used in the
                output format string

    Returns:   A list of matches (in whatever format you give it by
               defining the string formatting in 'output_format').
               If 'instant' is True, the list will be empty.
    """

    line = 0
    lines = get_file(input)
    matches = []
    first_pattern_regex = type(first_pattern) == regex_type
    second_pattern_regex = type(second_pattern) == regex_type
    groups = {'results': 0}

    # Search for a match based on second_pattern.
    def _backtrack(line):
        if forwards is True:
            line += 1
        else:
            line -= 1
        while line >= 0 and line < len(lines):
            if forwards is True:
                groups['context'] += "\n" + lines[line]
            else:
                groups['context'] = lines[line] + "\n" + groups['context']

            groups['second_line'] = lines[line]
            groups['second_line_num'] = line
            if second_pattern_regex:
                second_pattern_results = re.match(second_pattern, lines[line])
                if second_pattern_results is not None:
                    second_pattern_groups = {key: val for key, val in
                                             second_pattern_results.groupdict()
                                             .iteritems()}
                    groups.update(second_pattern_groups)
                    match = format(output_format, groups)
                    if instant:
                        print match,
                    else:
                        matches.append(match)
                    groups['results'] += 1
                    return
            elif second_pattern in lines[line]:
                match = format(output_format, groups)
                if instant:
                    print match,
                else:
                    matches.append(match)
                return
            if forwards is True:
                line += 1
            else:
                line -= 1

    def _found_result(line):
        if second_pattern is not None:
            groups['context'] = lines[line]
            _backtrack(line)
        else:
            match = format(output_format, groups)
            if instant:
                print match,
            else:
                matches.append(match)
            groups['results'] += 1

    while line < len(lines):
        lines[line] = lines[line].rstrip()
        results = groups['results']
        if max_results > -1 and groups['results'] >= max_results:
            return
        groups.clear()
        groups.update({'file': input, 'first_line': lines[line],
                       'first_line_num': line, 'results': results})
        if first_pattern_regex:
            first_pattern_results = re.match(first_pattern, lines[line])
            if first_pattern_results is not None:
                groups.update({
                    key: val for key, val
                    in first_pattern_results.groupdict().iteritems()
                })
                _found_result(line)
        elif first_pattern in lines[line]:
            _found_result(line)
        line += 1

    return matches


def get_regex(input):
    """
    Decide whether a string is a regular expression (of the form
    /pattern/flags) e.g. /^foo.*bar$/i would look for lines starting
    with foo, ending with bar, and would ignore case.
    (i==re.IGNORECASE, u==re.UNICODE, m=re.MULTILINE, d==re.DOTALL,
     a=='approximate search')
    'approximate search' simply expands literal characters in the
    regular expression to account for common typos.

    Returns a tuple of the form (is_regex, {'pattern': 'flags'}), where
    is_regex is True if a regex was detected, False otherwise.
    {'pattern'} is the pattern with the surrounding slashes removed, and
    {'flags'} is the regular expression flags (to be passed to flags=
    arguments in re.* functions)
    The regex dict is NoneType if no regular expression was detected.
    If the input is None, this will also return (False, None).
    """
    if input is None:
        return (False, None)
    flags = {
        "i": re.IGNORECASE,
        "m": re.MULTILINE,
        "d": re.DOTALL,
        "u": re.UNICODE
    }
    flag = 0
    result = re.match(r'^/(.*)/(\w*)$', input)
    if result is None:
        return (False, None)
    for c in result.group(2):
        if c in flags.keys():
            flag |= flags[c]
    regex = result.group(1)
    if 'a' in result.group(2):
        # Oh my lord, I am about to search for literal characters in a
        # regular expression using a regular expression. [inception horn]
        for word in re.findall(r'\b(?<!\\)[A-Za-z]{2,}\b', regex):
            regex = regex.replace(word, expand_for_typos(word))
    return (result is not None, {"pattern": regex, "flags": flag})


def main(files, first, second, output_format=output_format,
         instant=False, forwards=False, no_color=False, max_results=-1):
    """
    Function main
    Loops through a list of files calling search() on them.
    """

    # Detect and compile any regular expressions
    l = locals()
    for pattern in ['first', 'second']:
        is_regex, regex = get_regex(l[pattern])
        if is_regex:
            l[pattern] = re.compile(regex['pattern'], flags=regex['flags'])

    first_pattern = l['first']
    second_pattern = l['second']

    # Make sure newlines and tabs are formatted properly
    output_format = output_format.replace('\\t', '\t').replace('\\n', '\n')

    # Loop over all the files
    if files == []:
        files.append('-')
    for input in files:
        if os.path.isfile(input) is False:
            continue
        matches = search(input, first_pattern, second_pattern,
                         output_format, instant, forwards,
                         max_results)
        if instant is False and len(matches) > 0:
            print ''.join(matches)


def _run():
    helps = {
        "forwards": "Only search for a match of second_pattern " +
                    "forwards from the first pattern. Default is to " +
                    "search backwards up the file.",
        "first_pattern": "Pattern to search for. Can be a fixed " +
                         "string, or a regular expression, enclosed " +
                         "in forward slashes: /pattern/i (the 'i' " +
                         "tells it to be case insensitive when matching).",
        "second_pattern": "Second pattern to search for. Can be a fixed " +
                          "string or a regular expression, same as " +
                          "first_pattern. If omitted, haystack will " +
                          "print the results of matching the first " +
                          "pattern, behaving like the 'grep' tool does.",
        "output_format": "The format to print the search results in. " +
                         "Uses variable expansion, variables are " +
                         "enclosed in curly braces {} - e.g. {first_line}. " +
                         "Can use named captures from the regular " +
                         "expression search patterns, e.g. " +
                         "(?P<filename>) can be referenced in the " +
                         "output as {filename}.",
        "instant": "Print results as soon as they are found.",
        "files": "Paths to text files to search through. Can specify " +
                 "multiple files. You can differentiate between files " +
                 "by including {file} in the output_format. If no " +
                 "files are given, haystack expects input from stdin.",
        "no_color": "Disable colour in the output.",
        "max_results": "Only find the first N results from each file."
    }

    parser = argparse.ArgumentParser(
        description=__doc__, version=__version__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-o", "--output_format", default=output_format,
                              help=helps["output_format"])
    parser.add_argument("-i", "--instant", default=False,
                              action="store_true", help=helps["instant"])
    parser.add_argument("-f", "--forwards", default=False,
                              action="store_true", help=helps["forwards"])
    parser.add_argument("--first", help=helps["first_pattern"])
    parser.add_argument("--second", help=helps["second_pattern"],
                        default=None)
    parser.add_argument("-n", "--no-color", help=helps["no_color"],
                              action="store_true", default=False)
    parser.add_argument("-r", "--max-results", help=helps["max_results"],
                              type=int, default=-1)
    parser.add_argument("files", nargs="*", help=helps["files"])
    args = parser.parse_args()

    # Call main on every input given
    main(**args.__dict__)

    if args.no_color:
        def colored(string, color):
            return string


if __name__ == "__main__":
    _run()
