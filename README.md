# shu-strokes

The stroke data and dictionary extract used by **Shu**, an iPad kanji writing trainer. It is KanjiVG's stroke order data converted to compact JSON, with a tag for how each stroke should end (tome, hane, harai) and a flag for endings that Japanese handwriting rules leave open, plus a trimmed dictionary and JLPT and school-grade deck lists.

This repository exists because the data is adapted from Creative Commons ShareAlike sources, and our changes are shared under the same terms. The Shu app itself is a separate, closed-source product; it reads these files as plain resources.

## Licence

**CC BY-SA 4.0** (see `LICENSE`). You may copy, adapt and redistribute this data, including commercially, if you credit the sources below and share your adaptations under the same licence.

## Credits

**Stroke data.** KanjiVG (https://kanjivg.tagaini.net) copyright © 2009-2026 Ulrich Apel. It is released under the Creative Commons Attribution-Share Alike 3.0 license. This repository adapts release r20260714. ShareAlike 3.0 permits adaptations under a later version with the same elements, so our adaptation is CC BY-SA 4.0.

**Dictionary.** This package uses the JMdict/EDICT and KANJIDIC dictionary files. These files are the property of the Electronic Dictionary Research and Development Group, and are used in conformance with the Group's licence.
- The KANJIDIC Project: https://www.edrdg.org/wiki/index.php/KANJIDIC_Project
- The JMdict/EDICT Project: https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project
- EDRDG licence: https://www.edrdg.org/edrdg/licence.html

**JLPT levels.** From Jonathan Waller's JLPT kanji lists (tanos.co.uk), CC BY. tanos.co.uk no longer resolves, so the lists are read from the verbatim snapshot of Waller's decks in the OpenJLPT repository, pinned to commit `0d1d3410bec90bd4098a7c72de820543cb4f707c` (https://github.com/evanclan/OpenJLPT). The JLPT has published no official kanji lists since 2010; these levels are estimates.

**Jōyō list.** The 2,136 Jōyō kanji (Cabinet Notice No. 2 of 2010) are taken from KANJIDIC2's grade field (grades 1 to 6 and 8). Japanese government notices are not protected by copyright (Copyright Act, Article 13).

## What we changed

- **Format.** Each character's KanjiVG strokes are kept as the original SVG path strings, with the stroke type and the stroke number position, in one JSON file. No path was redrawn.
- **Ending tags.** Every stroke is tagged with the ending a teacher expects: `tome` (stop), `hane` (flick), `harai` (sweep), `harai_r` (the rightward sweep ㇏) or `dot`.
- **Free flags.** Strokes whose ending the Agency for Cultural Affairs' 2016 handwriting guideline (常用漢字表の字体・字形に関する指針) leaves open are flagged so they are never graded.
- **Dictionary.** KANJIDIC2 is trimmed to English meanings, Jōyō on and kun readings, grade, stroke count and frequency rank. Fields with other rights holders (SKIP codes, Four Corner codes and the like) are dropped. Up to three common words per kanji come from JMdict (entries with a news1, ichi1 or spec1 priority).
- **Decks.** Hiragana, katakana, JLPT N5 to N1, school grades 1 to 6 and secondary school, each ordered by grade, then stroke count, then frequency.

## Files

| File | What |
|---|---|
| `data/strokes.json` | Strokes and ending tags for 2,302 characters (2,136 Jōyō kanji and 166 kana), 22,841 strokes |
| `data/kanji.json` | Dictionary facts, kana romaji and the deck lists |
| `data/endings.csv` | The ending tags as a table: `char, stroke, type, ending, free` |
| `scripts/build_data.py` | Rebuilds both JSON files from the original sources (Python 3 standard library only) |

### strokes.json

```json
{"format": 1, "source": "...",
 "chars": {"永": [{"d": "M45.5,13.25c5.12,2.4,8.62,5.75,10.75,9", "t": "㇔", "e": "dot", "f": 0, "n": [36.8, 13.5]}, ...]}}
```

Strokes are in writing order. `d` is the KanjiVG path in its 109 × 109 box, `t` the KanjiVG stroke type, `e` the ending, `f` 1 when the ending is free, and `n` the stroke number's position.

### kanji.json

```json
{"format": 1,
 "kanji": {"永": {"m": ["eternity", "long", "lengthy"], "on": ["エイ"], "kun": ["なが.い"], "g": 5, "s": 5, "fr": 846, "j": 2,
                  "w": [["永遠", "えいえん", "eternity"], ...]}},
 "kana": {"あ": "a", ...},
 "decks": [{"id": "n5", "title": "JLPT N5", "chars": "一二三..."}, ...]}
```

`m` meanings, `on` and `kun` readings, `g` grade (8 is secondary school), `s` stroke count, `fr` frequency rank, `j` JLPT level (Waller), `w` common words as word, reading, gloss.

## How endings are tagged

From the KanjiVG stroke type (Unicode CJK Strokes):

| Ending | Stroke types |
|---|---|
| `dot` | ㇔ |
| `harai` | ㇒ ㇓ ㇇ ㇋ ㇥ ㇀ |
| `harai_r` | ㇏ ㇝ |
| `hane` | ㇁ ㇂ ㇃ ㇆ ㇈ ㇉ ㇌ ㇖ ㇚ ㇟ ㇠ ㇡ ㇢ ㇤ ㇙ ㇊ |
| `tome` | every other type (㇐ ㇑ ㇕ ㇗ ㇛ ㇜ ㇞ and so on) |

A type with alternatives (for example `㇆/㇚`) lists the form in this position first. When one alternative is a hook and another is not, the drawn path decides: `hane` if the path ends in a hook, otherwise the first unhooked alternative.

**Free endings (351 strokes).** The central vertical of the 木 family (木 禾 米 来 末 未 本 朱 東 束 果 采 and related elements), whose foot may stop or flick; and the last sweep of 木, 禾, 米, 耒 and 釆 used as a left radical, which shortens to a stop or a dot. See `free_flags()` in the script.

## Deck sizes

| Deck | Characters |
|---|---|
| Hiragana | 81 |
| Katakana | 81 |
| JLPT N5 | 79 |
| JLPT N4 | 166 |
| JLPT N3 | 367 |
| JLPT N2 | 367 |
| JLPT N1 | 985 |
| Grade 1 to 6 | 80, 160, 200, 202, 193, 191 |
| Secondary school | 1,110 |

The N1 count is lower than the roughly 1,235 often quoted, because Waller's N1 deck in the snapshot holds 985 Jōyō kanji. Every Jōyō kanji is still covered by the grade decks.

## Rebuilding

```
python3 scripts/build_data.py --cache /path/to/cache --out data
```

The script downloads KanjiVG r20260714, KANJIDIC2, JMdict_e and the Waller snapshot into the cache on first run.
