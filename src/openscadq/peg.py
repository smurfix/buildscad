#######################################################################
# Name: openscadq/peg.py
# Purpose: This module is a variation of the original peg.py.
#   The syntax is slightly changed to be more readable.
# Copyright: (c) 2024 Matthias Urlichs <matthias@urlichs.de>
# Copyright: (c) 2014-2017 Igor R. Dejanovic <igor DOT dejanovic AT gmail DOT com>
# License: MIT License
#######################################################################

from pathlib import Path

from arpeggio import (
    EOF,
    Not,
    OneOrMore,
    Optional,
    ParserPython,
    ZeroOrMore,
    visit_parse_tree,
)
from arpeggio import RegExMatch as _

from arpeggio.peg import ParserPEG as ParserPEGOrig
from arpeggio.peg import PEGVisitor

__all__ = ['Parser']

# Lexical invariants
ASSIGNMENT = "="
ORDERED_CHOICE = "|"
ZERO_OR_MORE = "*"
ONE_OR_MORE = "+"
OPTIONAL = "?"
UNORDERED_GROUP = "#"
AND = "&"
NOT = "!"
OPEN = "("
CLOSE = ")"

# PEG syntax rules
def peggrammar():       return OneOrMore(rule), EOF
def rule():             return rule_name, ASSIGNMENT, ordered_choice
def ordered_choice():   return sequence, ZeroOrMore(ORDERED_CHOICE, sequence)
def sequence():         return OneOrMore(prefix)
def prefix():           return Optional([AND, NOT]), sufix
def sufix():            return expression, Optional([OPTIONAL,
                                                     ZERO_OR_MORE,
                                                     ONE_OR_MORE,
                                                     UNORDERED_GROUP])
def expression():       return [regex, rule_crossref,
                                (OPEN, ordered_choice, CLOSE),
                                str_match], Not(ASSIGNMENT)

# PEG Lexical rules
def regex():            return [("r'", _(r'''[^'\\]*(?:\\.[^'\\]*)*'''), "'"),
                                ('r"', _(r'''[^"\\]*(?:\\.[^"\\]*)*'''), '"')]
def rule_name():        return _(r"[a-zA-Z_]([a-zA-Z_]|[0-9])*")
def rule_crossref():    return rule_name
def str_match():        return _(r'''(?s)('[^'\\]*(?:\\.[^'\\]*)*')|'''
                                     r'''("[^"\\]*(?:\\.[^"\\]*)*")''')
def comment():          return _("//[^\n]*", multiline=False)


class Parser(ParserPEGOrig):

    def __init__(self, *args, debug=False, **kwargs):
        """
        Constructs parser from textual PEG definition.

        Args:
            language_def (str): A string describing language grammar using
                PEG notation.
            root_rule_name(str): The name of the root rule.
            comment_rule_name(str): The name of the rule for comments.
        """
        language_def = (Path(__file__).parent / "openscad.peg").read_text()
        self.__debug = debug
        super().__init__(language_def, "Input", "Comment", *args, **kwargs)

    def _from_peg(self, language_def):
        parser = ParserPython(peggrammar, comment, reduce_tree=False,
                              debug=False)
        parser.root_rule_name = self.root_rule_name
        parse_tree = parser.parse(language_def)

        res = visit_parse_tree(parse_tree, PEGVisitor(self.root_rule_name,
                                                       self.comment_rule_name,
                                                       self.ignore_case))
        self.debug = self.__debug
        return res
