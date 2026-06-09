"""Deterministic romaji-to-kana baseline conversion.

Offline-only: no network, no provider keys, no file access. Tokens that do not
fully map to kana (English words, mixed-case words, URLs) are left unchanged so
mixed Japanese/English paragraphs survive conversion.
"""

from __future__ import annotations


# Longest-match-first syllable table (Hepburn plus common Kunrei spellings).
_SYLLABLES: dict[str, str] = {
    # youon (3-letter first for longest match)
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ",
    "sha": "しゃ", "shu": "しゅ", "sho": "しょ", "shi": "し",
    "sya": "しゃ", "syu": "しゅ", "syo": "しょ",
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ", "chi": "ち",
    "tya": "ちゃ", "tyu": "ちゅ", "tyo": "ちょ",
    "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ",
    "mya": "みゃ", "myu": "みゅ", "myo": "みょ",
    "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ",
    "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ",
    "ja": "じゃ", "ju": "じゅ", "jo": "じょ", "ji": "じ",
    "jya": "じゃ", "jyu": "じゅ", "jyo": "じょ",
    "zya": "じゃ", "zyu": "じゅ", "zyo": "じょ",
    "bya": "びゃ", "byu": "びゅ", "byo": "びょ",
    "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ",
    "dya": "ぢゃ", "dyu": "ぢゅ", "dyo": "ぢょ",
    "tsu": "つ", "thi": "てぃ", "dhi": "でぃ",
    "fa": "ふぁ", "fi": "ふぃ", "fe": "ふぇ", "fo": "ふぉ",
    "va": "ゔぁ", "vi": "ゔぃ", "vu": "ゔ", "ve": "ゔぇ", "vo": "ゔぉ",
    "wha": "うぁ", "whi": "うぃ", "whe": "うぇ", "who": "うぉ",
    # basic rows
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "sa": "さ", "si": "し", "su": "す", "se": "せ", "so": "そ",
    "ta": "た", "ti": "ち", "tu": "つ", "te": "て", "to": "と",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "hu": "ふ", "fu": "ふ", "he": "へ", "ho": "ほ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "wa": "わ", "wi": "ゐ", "we": "ゑ", "wo": "を",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "za": "ざ", "zi": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "da": "だ", "di": "ぢ", "du": "づ", "de": "で", "do": "ど",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "xa": "ぁ", "xi": "ぃ", "xu": "ぅ", "xe": "ぇ", "xo": "ぉ",
    "xtu": "っ", "xya": "ゃ", "xyu": "ゅ", "xyo": "ょ",
}

_PUNCT: dict[str, str] = {
    ",": "、", ".": "。", "?": "？", "!": "！", "-": "ー",
    "[": "「", "]": "」", "~": "〜",
}

_VOWELS = set("aiueo")
_SOKUON_CONSONANTS = set("kstpcgzjdbfhmyrw")
_MAX_SYLLABLE = 3


def convert_token(token: str) -> str | None:
    """Convert one all-lowercase romaji token to kana.

    Returns None when the token cannot be fully converted (treat as
    non-Japanese and leave unchanged).
    """
    out: list[str] = []
    i = 0
    n = len(token)
    while i < n:
        ch = token[i]
        if ch in _PUNCT:
            out.append(_PUNCT[ch])
            i += 1
            continue
        # n' -> ん (Hepburn separator: kin'en)
        if ch == "n" and i + 1 < n and token[i + 1] == "'":
            out.append("ん")
            i += 2
            continue
        # nn: Hepburn double-n before a vowel/y keeps the second n for the
        # next syllable (konnichiha -> こんにちは); otherwise both are ん.
        if ch == "n" and i + 1 < n and token[i + 1] == "n":
            if i + 2 < n and (token[i + 2] in _VOWELS or token[i + 2] == "y"):
                out.append("ん")
                i += 1
            else:
                out.append("ん")
                i += 2
            continue
        # n before a non-vowel, non-y consonant or at end -> ん
        if ch == "n" and (i + 1 >= n or (token[i + 1] not in _VOWELS and token[i + 1] != "y")):
            out.append("ん")
            i += 1
            continue
        # sokuon: doubled consonant (kk, tt, pp, but not nn)
        if (
            ch in _SOKUON_CONSONANTS
            and i + 1 < n
            and token[i + 1] == ch
        ):
            out.append("っ")
            i += 1
            continue
        # tch -> っち (matcha)
        if ch == "t" and token[i : i + 3] == "tch":
            out.append("っ")
            i += 1
            continue
        matched = False
        for size in range(min(_MAX_SYLLABLE, n - i), 0, -1):
            piece = token[i : i + size]
            kana = _SYLLABLES.get(piece)
            if kana is not None:
                out.append(kana)
                i += size
                matched = True
                break
        if not matched:
            return None
    return "".join(out)


def convert_text(text: str, *, dictionary: dict[str, str] | None = None) -> str:
    """Convert a romaji paragraph; non-convertible tokens stay unchanged.

    `dictionary` maps a lowercase romaji token to a preferred Japanese
    replacement and is applied before kana conversion (exact token match).
    """
    words = dictionary or {}
    out_tokens: list[str] = []
    for token in text.split(" "):
        if not token:
            out_tokens.append(token)
            continue
        replaced = words.get(token.lower())
        if replaced is not None:
            out_tokens.append(replaced)
            continue
        if token.isascii() and token == token.lower():
            kana = convert_token(token)
            out_tokens.append(kana if kana is not None else token)
        else:
            out_tokens.append(token)
    return " ".join(out_tokens)
