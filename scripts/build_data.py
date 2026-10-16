#!/usr/bin/env python3
"""Build Shu's bundled data: App/Shu/KanjiData/strokes.json and kanji.json.

Python 3 standard library only. Run from anywhere:

    python3 scripts/build_data.py [--cache DIR] [--out DIR] [--endings-csv FILE]

Sources (downloaded into the cache directory on first run, then reused):

  KanjiVG r20260714, "main" zip (files with kvg attributes)
    https://github.com/KanjiVG/kanjivg/releases/download/r20260714/kanjivg-20260714-main.zip
    Copyright (C) 2009-2026 Ulrich Apel, CC BY-SA 3.0. https://kanjivg.tagaini.net
  KANJIDIC2 (EDRDG), CC BY-SA 4.0
    http://www.edrdg.org/kanjidic/kanjidic2.xml.gz
  JMdict_e (EDRDG), CC BY-SA 4.0
    http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz
  JLPT N5 to N1 kanji lists by Jonathan Waller (tanos.co.uk, CC BY). tanos.co.uk no
  longer resolves, so we read the verbatim snapshot of Waller's "kanji-char-eng" Anki
  decks committed in the OpenJLPT repo (sources/waller/, extracted card by card with no
  cleaning; OpenJLPT's NOTICE.md credits Waller, CC BY, as the source of every level),
  pinned to commit 0d1d3410bec90bd4098a7c72de820543cb4f707c:
    https://raw.githubusercontent.com/evanclan/OpenJLPT/0d1d3410bec90bd4098a7c72de820543cb4f707c/sources/waller/kanji-eng-n5.json
    (and n4, n3, n2, n1)
  The Jōyō list (Cabinet Notice No. 2 of 2010) is taken from KANJIDIC2's grade field:
  grades 1 to 6 and 8 are exactly the 2,136 Jōyō kanji.

Output is CC BY-SA 4.0 (adapted from the sources above). See the shu-strokes dataset
README for the format and the stroke ending rules implemented in ending_for() and
free_flags() below.
"""

import argparse
import csv
import gzip
import io
import json
import math
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = str(Path(__file__).resolve().parent.parent / ".data-cache")

KVG_URL = "https://github.com/KanjiVG/kanjivg/releases/download/r20260714/kanjivg-20260714-main.zip"
KANJIDIC_URL = "http://www.edrdg.org/kanjidic/kanjidic2.xml.gz"
JMDICT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"
WALLER_COMMIT = "0d1d3410bec90bd4098a7c72de820543cb4f707c"
WALLER_URL = "https://raw.githubusercontent.com/evanclan/OpenJLPT/" + WALLER_COMMIT + "/sources/waller/kanji-eng-n{n}.json"

SOURCE_LINE = ("KanjiVG r20260714, copyright (C) 2009-2026 Ulrich Apel, CC BY-SA 3.0. "
               "Adapted by Shu (format conversion and stroke ending tags), CC BY-SA 4.0.")

KVG_NS = "{http://kanjivg.tagaini.net}"
SVG_NS = "{http://www.w3.org/2000/svg}"

# ---------------------------------------------------------------- kana

HIRAGANA = [chr(c) for c in range(0x3041, 0x3094)]   # ぁ .. ん
KATAKANA = [chr(c) for c in range(0x30A1, 0x30F4)]   # ァ .. ン

ROMAJI_BASE = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "を": "wo", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
    "っ": "tsu", "ゃ": "ya", "ゅ": "yu", "ょ": "yo", "ゎ": "wa",
    "ゐ": "wi", "ゑ": "we",
}
GOJUON = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
VOICED = "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ"
SMALL = "ぁぃぅぇぉっゃゅょゎ"


def kata(s):
    return "".join(chr(ord(c) + 0x60) for c in s)


def kana_map():
    m = {}
    for h in HIRAGANA:
        m[h] = ROMAJI_BASE[h]
    for k in KATAKANA:
        m[k] = ROMAJI_BASE[chr(ord(k) - 0x60)]
    return m


def kana_deck_order(katakana=False):
    s = GOJUON + VOICED + SMALL
    return kata(s) if katakana else s


# ---------------------------------------------------------------- downloads

def fetch(url, cache, name):
    path = Path(cache) / name
    if not path.exists() or path.stat().st_size == 0:
        print("download", url, file=sys.stderr)
        req = urllib.request.Request(url, headers={"User-Agent": "shu-build-data/1"})
        with urllib.request.urlopen(req, timeout=600) as r, open(str(path) + ".part", "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        os.replace(str(path) + ".part", path)
    return path


# ---------------------------------------------------------------- KANJIDIC2

def load_kanjidic(path):
    out = {}
    with gzip.open(path) as f:
        for _, el in ET.iterparse(f):
            if el.tag != "character":
                continue
            lit = el.findtext("literal")
            g = el.findtext("misc/grade")
            sc = el.find("misc/stroke_count")
            fr = el.findtext("misc/freq")
            on, kun, mean = [], [], []
            for rm in el.findall("reading_meaning/rmgroup"):
                for r in rm.findall("reading"):
                    t = r.get("r_type")
                    if t in ("ja_on", "ja_kun"):
                        (on if t == "ja_on" else kun).append((r.text, r.get("r_status") == "jy"))
                for m in rm.findall("meaning"):
                    if m.get("m_lang") is None:
                        mean.append(m.text)
            out[lit] = {
                "g": int(g) if g else None,
                "s": int(sc.text) if sc is not None else None,
                "fr": int(fr) if fr else None,
                "on": on, "kun": kun, "m": mean,
            }
            el.clear()
    return out


def pick_readings(rs, n=3):
    """Prefer r_status="jy" (Jōyō) readings when the file marks any; then readings
    without a leading affix marker '-'. Keep KANJIDIC's order otherwise."""
    if any(jy for _, jy in rs):
        rs = [r for r in rs if r[1]]
    order = sorted(range(len(rs)), key=lambda i: (rs[i][0].startswith("-"), i))
    seen, out = set(), []
    for i in order:
        r = rs[i][0]
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out[:n]


# ---------------------------------------------------------------- stroke geometry

NUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
TOK = re.compile(r"[MmCcSsLlZz]|" + NUM.pattern)


def parse_path(d):
    """Cubic segments ((x0,y0),(x1,y1),(x2,y2),(x3,y3)) from an SVG path (M C S L Z)."""
    tokens = TOK.findall(d)
    segs, i, cmd = [], 0, None
    cur = start = (0.0, 0.0)
    last_ctrl = None
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                if cur != start:
                    segs.append((cur, cur, start, start))
                cur = start
            continue

        def nums(n):
            nonlocal i
            vals = [float(v) for v in tokens[i:i + n]]
            i += n
            return vals

        if cmd in "Mm":
            x, y = nums(2)
            if cmd == "m":
                x, y = cur[0] + x, cur[1] + y
            cur = start = (x, y)
            cmd = "L" if cmd == "M" else "l"
            last_ctrl = None
        elif cmd in "Cc":
            a = nums(6)
            if cmd == "c":
                a = [a[k] + cur[k % 2] for k in range(6)]
            segs.append((cur, (a[0], a[1]), (a[2], a[3]), (a[4], a[5])))
            last_ctrl, cur = (a[2], a[3]), (a[4], a[5])
        elif cmd in "Ss":
            a = nums(4)
            if cmd == "s":
                a = [a[k] + cur[k % 2] for k in range(4)]
            p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
            segs.append((cur, p1, (a[0], a[1]), (a[2], a[3])))
            last_ctrl, cur = (a[0], a[1]), (a[2], a[3])
        elif cmd in "Ll":
            x, y = nums(2)
            if cmd == "l":
                x, y = cur[0] + x, cur[1] + y
            segs.append((cur, cur, (x, y), (x, y)))
            cur = (x, y)
            last_ctrl = None
        else:
            raise ValueError("unsupported path command %r in %r" % (cmd, d))
    return segs


def bez(s, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = s
    u = 1 - t
    return (u ** 3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3,
            u ** 3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3)


def polyline(d, step=0.5):
    segs = parse_path(d)
    pts = []
    for s in segs:
        approx = sum(math.dist(bez(s, k / 8), bez(s, (k + 1) / 8)) for k in range(8))
        n = max(2, int(approx / step))
        pts.extend(bez(s, k / n) for k in range(n))
    pts.append(segs[-1][3])
    out = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, out[-1]) > 0.05:
            out.append(p)
    return out


def has_end_hook(d):
    """True when the model path ends in a hook: a short tail (under 16 units and
    under 30% of the stroke) that leaves the body at a sharp angle (over about 75 deg).
    Used to settle KanjiVG types that offer a hooked and an unhooked alternative."""
    pts = polyline(d)
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    total = cum[-1]
    if total < 6:
        return False
    end = pts[-1]
    for i in range(len(pts) - 2, 0, -1):
        tail = total - cum[i]
        if tail < 2.0:
            continue
        if tail > min(16.0, 0.3 * total):
            break
        j = i
        while j > 0 and cum[i] - cum[j] < 5.0:
            j -= 1
        vin = (pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
        vout = (end[0] - pts[i][0], end[1] - pts[i][1])
        la, lb = math.hypot(*vin), math.hypot(*vout)
        if la < 1e-6 or lb < 1e-6:
            continue
        if (vin[0] * vout[0] + vin[1] * vout[1]) / (la * lb) < 0.25:
            return True
    return False


# ---------------------------------------------------------------- endings

# Unicode CJK Strokes block (U+31C0..U+31E5), by name:
#   tome    ㇐ H, ㇑ S, ㇕ HZ, ㇗ SZ, ㇄ SW, ㇅ HZZ, ㇍ HZW, ㇎ HZZZ, ㇘ SWZ, ㇛ PD, ㇜ PZ,
#           ㇞ SZZ, ㇣ Q
#   dot     ㇔ D
#   harai   ㇒ P, ㇓ SP, ㇇ HP, ㇋ HZZP, ㇥ SZP, ㇀ T (rising flick)
#   harai_r ㇏ N, ㇝ TN (the flat rightward sweep)
#   hane    every stroke whose name ends in G (gou, hook): ㇁ WG, ㇂ XG, ㇃ BXG, ㇆ HZG,
#           ㇈ HZWG, ㇉ SZWG, ㇌ HPWG, ㇖ HG, ㇚ SG, ㇟ SWG, ㇠ HXWG, ㇡ HZZZG, ㇢ PG,
#           ㇤ HXG; and the turned rising strokes ㇙ ST and ㇊ HZT (stop, then flick up).
DOT = set("㇔")
HARAI = set("㇒㇓㇇㇋㇥㇀")
HARAI_R = set("㇏㇝")
HANE = set("㇁㇂㇃㇆㇈㇉㇌㇖㇚㇟㇠㇡㇢㇤㇙㇊")
ENDINGS = ("tome", "hane", "harai", "harai_r", "dot")


def ending_of_base(t):
    """Ending for a single KanjiVG type such as '㇑a' (suffix letters ignored)."""
    c = t[:1]
    if c in DOT:
        return "dot"
    if c in HARAI_R:
        return "harai_r"
    if c in HARAI:
        return "harai"
    if c in HANE:
        return "hane"
    return "tome"


def ending_for(kvg_type, d):
    """Seed ending for one stroke from its kvg:type.

    A type with alternatives ('㇒/㇚') lists the form in this position first and the
    stroke's other form second. When one alternative is a hook and another is not, the
    model path decides: hane if the drawn path ends in a hook, otherwise the first
    unhooked alternative. Otherwise the first alternative is used."""
    t = kvg_type or ""
    opts = [o for o in t.split("/") if o]
    if not opts:
        return "tome"
    ends = [ending_of_base(o) for o in opts]
    if len(opts) > 1 and "hane" in ends and any(e != "hane" for e in ends):
        if has_end_hook(d):
            return "hane"
        return next(e for e in ends if e != "hane")
    return ends[0]


# ---------------------------------------------------------------- free strokes

# Elements written with a central vertical whose foot meets a left and a right sweep.
# Per the Bunkachō guideline (常用漢字表の字体・字形に関する指針, 2016) 木 and 来 may end that
# vertical with a stop or a flick; we treat the whole family the same way.
KI_FAMILY = set("木禾米来末未本朱東束果采耒朿柬巣乗栗呆某柔楽査困釆")
# Elements whose last sweep shortens to a stop or dot when used as a left radical.
KI_LEFT = set("木禾米耒釆")


def free_flags(strokes):
    """strokes: list of dicts with keys d, t, anc (ancestor <g> attrs, innermost first),
    pts (polyline). Returns a list of 0/1 free flags."""
    flags = [0] * len(strokes)

    def family_group(s, names):
        for depth, g in enumerate(s["anc"]):
            if g.get("element") in names or g.get("original") in names:
                return g["id"]
        return None

    # (a) the central vertical of a 木-family element, where both sweeps branch from it
    for i, s in enumerate(strokes):
        if not s["t"].startswith("㇑"):
            continue
        gid = family_group(s, KI_FAMILY)
        if gid is None:
            continue
        pts = s["pts"]
        ys = [p[1] for p in pts]
        y_bot = max(ys)
        left = right = False
        for o in strokes[i + 1:]:
            x0, y0 = o["pts"][0]
            if not (min(ys) < y0 < y_bot - 4):
                continue
            # x of the vertical at the sweep's start height
            vx = min(pts, key=lambda p: abs(p[1] - y0))[0]
            if abs(x0 - vx) > 5.5:
                continue
            e = o["end"]
            dx = o["pts"][-1][0] - x0
            if e == "harai" and dx < 0:
                left = True
            elif e in ("harai_r", "dot", "tome") and dx > 0:
                right = True
        if left and right:
            flags[i] = 1

    # (b) the last stroke of 木/禾/米 (and 耒, 釆) used as a left radical, where the
    # rightward sweep is written short as a stop or dot
    for i, s in enumerate(strokes):
        if not (s["t"].startswith("㇏") or s["t"].startswith("㇔")):
            continue
        for g in s["anc"]:
            if (g.get("element") in KI_LEFT or g.get("original") in KI_LEFT) and g.get("position") == "left":
                members = [k for k, o in enumerate(strokes) if g["id"] in [a["id"] for a in o["anc"]]]
                if members and members[-1] == i:
                    flags[i] = 1
                break
    return flags


# ---------------------------------------------------------------- KanjiVG

def read_kvg(zf, ch):
    name = "kanji/%05x.svg" % ord(ch)
    try:
        raw = zf.read(name)
    except KeyError:
        return None
    root = ET.fromstring(raw)
    parent = {c: p for p in root.iter() for c in p}
    paths = []
    for el in root.iter(SVG_NS + "path"):
        m = re.search(r"-s(\d+)$", el.get("id", ""))
        if not m:
            continue
        anc = []
        p = parent.get(el)
        while p is not None and p.tag == SVG_NS + "g":
            a = {"id": p.get("id", "")}
            for k in ("element", "original", "position", "part", "radical"):
                v = p.get(KVG_NS + k)
                if v is not None:
                    a[k] = v
            anc.append(a)
            p = parent.get(p)
        paths.append((int(m.group(1)), el.get("d"), el.get(KVG_NS + "type") or "", anc))
    paths.sort(key=lambda x: x[0])
    nums = []
    for g in root.iter(SVG_NS + "g"):
        if g.get("id", "").startswith("kvg:StrokeNumbers_"):
            for t in g.iter(SVG_NS + "text"):
                m = re.search(r"matrix\(\s*1\s+0\s+0\s+1\s+([-\d.]+)\s+([-\d.]+)\s*\)", t.get("transform", ""))
                nums.append((int(t.text), float(m.group(1)), float(m.group(2))))
    numpos = {n: (x, y) for n, x, y in nums}
    strokes = []
    for k, (n, d, t, anc) in enumerate(paths):
        if n != k + 1:
            raise ValueError("%s: stroke numbering gap at %d" % (ch, n))
        x, y = numpos.get(n, (None, None))
        strokes.append({"d": d, "t": t, "anc": anc, "n": [round(x, 1), round(y, 1)] if x is not None else None})
    return strokes


def build_strokes(zf, chars, is_kana):
    out, endings_rows = {}, []
    for ch in chars:
        strokes = read_kvg(zf, ch)
        if strokes is None:
            continue
        for s in strokes:
            s["pts"] = polyline(s["d"])
            s["end"] = ending_for(s["t"], s["d"])
        flags = [0] * len(strokes) if is_kana(ch) else free_flags(strokes)
        rec = []
        for i, s in enumerate(strokes):
            r = {"d": s["d"], "t": s["t"], "e": s["end"], "f": flags[i]}
            if s["n"] is not None:
                r["n"] = s["n"]
            rec.append(r)
            endings_rows.append((ch, i + 1, s["t"], s["end"], flags[i]))
        out[ch] = rec
    return out, endings_rows


# ---------------------------------------------------------------- JMdict

PRI_OK = {"news1", "ichi1", "spec1"}
WORD_OK = re.compile("^[\\u3041-\\u3096\\u30A1-\\u30FA\\u30FC\\u4E00-\\u9FFF\\u3005]+$")


def load_words(path, kanji_set, joyo):
    """kanji -> sorted list of (key, word, reading, gloss)."""
    by_kanji = {k: {} for k in kanji_set}
    with gzip.open(path) as f:
        for _, el in ET.iterparse(f):
            if el.tag != "entry":
                continue
            seq = int(el.findtext("ent_seq"))
            rels = el.findall("r_ele")
            gloss = None
            for sense in el.findall("sense"):
                g = sense.find("gloss")
                if g is not None and g.text:
                    gloss = g.text
                    break
            for k in el.findall("k_ele"):
                keb = k.findtext("keb")
                pris = [p.text for p in k.findall("ke_pri")]
                if not (PRI_OK & set(pris)) or gloss is None:
                    continue
                if not (2 <= len(keb) <= 4) or not WORD_OK.match(keb):
                    continue
                reb = None
                for r in rels:
                    if r.find("re_nokanji") is not None:
                        continue
                    restr = [x.text for x in r.findall("re_restr")]
                    if not restr or keb in restr:
                        reb = r.findtext("reb")
                        break
                if reb is None:
                    continue
                nf = min([int(p[2:]) for p in pris if p.startswith("nf")] or [99])
                all_joyo = all(c in joyo for c in keb if 0x4E00 <= ord(c) <= 0x9FFF)
                key = (0 if all_joyo else 1, len(keb), nf, -len(pris), seq)
                for c in set(keb):
                    if c in by_kanji:
                        prev = by_kanji[c].get(keb)
                        if prev is None or key < prev[0]:
                            by_kanji[c][keb] = (key, keb, reb, trim(gloss, 40))
            el.clear()
    return {k: sorted(v.values()) for k, v in by_kanji.items()}


def trim(s, n):
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1]
    sp = cut.rfind(" ")
    if sp > n // 2:
        cut = cut[:sp]
    return cut.rstrip(" ,;:(-") + "\u2026"


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--out", default=str(ROOT / "App" / "Shu" / "KanjiData"))
    ap.add_argument("--endings-csv", default=None, help="also write the per-stroke endings table")
    args = ap.parse_args()
    Path(args.cache).mkdir(parents=True, exist_ok=True)
    Path(args.out).mkdir(parents=True, exist_ok=True)

    kvg_zip = fetch(KVG_URL, args.cache, "kanjivg-20260714-main.zip")
    kd_path = fetch(KANJIDIC_URL, args.cache, "kanjidic2.xml.gz")
    jm_path = fetch(JMDICT_URL, args.cache, "JMdict_e.gz")
    waller = {}
    for n in (5, 4, 3, 2, 1):
        p = fetch(WALLER_URL.format(n=n), args.cache, "waller-kanji-n%d.json" % n)
        waller[n] = [c["front"].strip() for c in json.loads(p.read_text(encoding="utf-8"))]

    kd = load_kanjidic(kd_path)
    joyo = [c for c, v in kd.items() if v["g"] in (1, 2, 3, 4, 5, 6, 8)]
    print("Jōyō kanji from KANJIDIC2 grades:", len(joyo), file=sys.stderr)
    if len(joyo) != 2136:
        print("WARNING: expected 2,136 Jōyō kanji", file=sys.stderr)
    joyo_set = set(joyo)

    kana = HIRAGANA + KATAKANA
    kana_set = set(kana)
    with zipfile.ZipFile(kvg_zip) as zf:
        chars, endings_rows = build_strokes(zf, kana + joyo, lambda c: c in kana_set)

    missing = [c for c in joyo + kana if c not in chars]
    for c in missing:
        print("WARNING: no KanjiVG file for", c, "U+%04X" % ord(c), file=sys.stderr)
    nstrokes = sum(len(v) for v in chars.values())
    print("strokes.json: %d chars (%d kanji, %d kana), %d strokes, %d free" % (
        len(chars), sum(1 for c in chars if c in joyo_set), sum(1 for c in chars if c in kana_set),
        nstrokes, sum(r[4] for r in endings_rows)), file=sys.stderr)
    for c in chars:
        if c in joyo_set and kd[c]["s"] and kd[c]["s"] != len(chars[c]):
            print("note: %s KanjiVG has %d strokes, KANJIDIC2 says %d" % (c, len(chars[c]), kd[c]["s"]),
                  file=sys.stderr)

    strokes_doc = {"format": 1, "source": SOURCE_LINE, "chars": chars}
    (Path(args.out) / "strokes.json").write_text(
        json.dumps(strokes_doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    if args.endings_csv:
        with open(args.endings_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["char", "stroke", "type", "ending", "free"])
            w.writerows(endings_rows)

    # JLPT: a kanji listed at more than one level keeps the easiest (highest N).
    jlpt = {}
    for n in (1, 2, 3, 4, 5):
        for c in waller[n]:
            jlpt[c] = n
    dropped = sorted(c for c in jlpt if c not in chars)
    if dropped:
        print("JLPT kanji outside the Jōyō set, dropped (%d): %s" % (len(dropped), "".join(dropped)), file=sys.stderr)

    kanji_in = [c for c in joyo if c in chars]
    words = load_words(jm_path, set(kanji_in), joyo_set)

    kanji = {}
    for c in kanji_in:
        v = kd[c]
        e = {"m": v["m"][:3], "on": pick_readings(v["on"]), "kun": pick_readings(v["kun"]),
             "g": v["g"], "s": v["s"]}
        if v["fr"]:
            e["fr"] = v["fr"]
        if c in jlpt:
            e["j"] = jlpt[c]
        e["w"] = [[w, r, g] for _, w, r, g in words.get(c, [])[:3]]
        kanji[c] = e

    def order(cs):
        return sorted(cs, key=lambda c: (kanji[c]["g"], kanji[c]["s"], kanji[c].get("fr", 9999), ord(c)))

    decks = [
        {"id": "hiragana", "title": "Hiragana", "chars": kana_deck_order()},
        {"id": "katakana", "title": "Katakana", "chars": kana_deck_order(katakana=True)},
    ]
    for n in (5, 4, 3, 2, 1):
        decks.append({"id": "n%d" % n, "title": "JLPT N%d" % n,
                      "chars": "".join(order([c for c in kanji if kanji[c].get("j") == n]))})
    for g in (1, 2, 3, 4, 5, 6):
        decks.append({"id": "g%d" % g, "title": "Grade %d" % g,
                      "chars": "".join(order([c for c in kanji if kanji[c]["g"] == g]))})
    decks.append({"id": "g8", "title": "Secondary school",
                  "chars": "".join(order([c for c in kanji if kanji[c]["g"] == 8]))})
    for dk in decks:
        print("deck %-9s %4d" % (dk["id"], len(dk["chars"])), file=sys.stderr)

    no_words = [c for c in kanji if not kanji[c]["w"]]
    print("kanji without a common word: %d" % len(no_words), file=sys.stderr)

    kanji_doc = {"format": 1, "kanji": kanji, "kana": kana_map(), "decks": decks}
    (Path(args.out) / "kanji.json").write_text(
        json.dumps(kanji_doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for name in ("strokes.json", "kanji.json"):
        print("wrote %s (%d bytes)" % (Path(args.out) / name, (Path(args.out) / name).stat().st_size),
              file=sys.stderr)


if __name__ == "__main__":
    main()
