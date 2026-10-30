"""레퍼런스 이미지 수집 (위키미디어 커먼즈, 자유 라이선스만).

    python3 motionspec/refs/collect.py search [named]   # 항목마다 한 번 검색, 썸네일을 cache/에 받음
    python3 motionspec/refs/collect.py sheets [named]   # 묶음별 후보 대조표(contact sheet)를 만듦
    python3 motionspec/refs/collect.py pick [named]     # picks 파일(고른 후보 번호)로 refs 파일 작성

기본은 카테2(queries.tsv → refs.json), named는 명자세(named_queries.tsv → named_refs.json).
명자세는 원어·영어·한국어 검색어로 각각 한 번씩 찾아 후보를 합치고, 모두 비면 그 항목은 넘어간다.
저장소에는 이미지 파일을 넣지 않고 원본 주소·작가·라이선스만 refs 파일에 남긴다.
필요한 접속: commons.wikimedia.org, upload.wikimedia.org
"""
import csv, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
API = "https://commons.wikimedia.org/w/api.php"
UA = "motionspec-refs/0.1 (https://github.com/jeong-haneul/motion)"
THUMB_W = 250
SETS = {
    # 이름: (검색어 파일, 열 두 개, 캐시 폴더, 썸네일 접두(None이면 받지 않음), 후보 수, picks 파일, refs 파일)
    # 명자세는 썸네일 서버의 요청 제한 때문에 썸네일 없이 파일 제목·설명으로 고른다
    "cat2": ("queries.tsv", ("카테1", "카테2"), CACHE, "", 8, "picks.tsv", "refs.json"),
    "named": ("named_queries.tsv", ("명카테1", "명카테2"), os.path.join(CACHE, "named"), None, 6,
              "named_picks.tsv", "named_refs.json"),
}
SET = SETS["cat2"]
N_CAND = SET[4]
FREE = re.compile(r"^(CC0|Public domain|PD|CC BY(-SA)? [\d.]+)", re.I)


def get(url, tries=6):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or k == tries - 1:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 5 * 2 ** k)


def rows():
    with open(os.path.join(HERE, SET[0]), encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def key_of(r):
    a, b = SET[1]
    return f"{r[a]} > {r[b]}"


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def thumb_url(url):
    # thumb.wikimedia.org 대신 upload.wikimedia.org의 표준 폭 썸네일 경로를 쓴다
    head, _, rest = url.partition("/wikipedia/commons/")
    if not rest:
        return None
    name = rest.rsplit("/", 1)[-1]
    return f"{head}/wikipedia/commons/thumb/{rest}/{THUMB_W}px-{name}"


QUERY_COLS = (("원어검색어", "원어"), ("검색어", "en"), ("한국어검색어", "ko"))


def search_row(r):
    """행의 검색어 열들(원어·영어·한국어)로 각각 검색해 겹치지 않게 합친다."""
    qs = [(r.get(col, "").strip(), lang if lang != "원어" else (r.get("언어") or "원어"))
          for col, lang in QUERY_COLS if col in r]
    qs = [(q, l) for q, l in qs if q and q != "-"]
    if len(qs) <= 1:
        return [dict(c, lang=qs[0][1]) for c in search(qs[0][0])] if qs else []
    per = max(2, N_CAND // len(qs) + 1)
    seen, out = set(), []
    for q, lang in qs:
        for c in search(q)[:per]:
            if c["title"] not in seen:
                seen.add(c["title"])
                out.append(dict(c, lang=lang, query=q))
    return out[:N_CAND]


def search(query):
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": N_CAND * 3,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": THUMB_W,
    })
    pages = json.loads(get(f"{API}?{q}")).get("query", {}).get("pages", {})
    out = []
    for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not FREE.match(lic):
            continue
        url = (ii.get("url") or "").split("?")[0]
        out.append({
            "title": p["title"], "page": ii.get("descriptionurl"), "url": url,
            "thumb": thumb_url(url), "license": lic,
            "author": strip_html(meta.get("Artist", {}).get("value")),
            "desc": strip_html(meta.get("ImageDescription", {}).get("value"))[:200],
        })
        if len(out) == N_CAND:
            break
    return out


def cmd_search():
    os.makedirs(os.path.join(SET[2], "thumbs"), exist_ok=True)
    if SET[3] is None:
        print("썸네일 없이 검색만 한다")
    path = os.path.join(SET[2], "candidates.json")
    cands = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for i, r in enumerate(rows()):
        key = key_of(r)
        if key in cands:
            continue
        try:
            cs = search_row(r)
        except Exception as e:
            print(f"[{i}] {key}: 검색 실패 {e}")
            continue
        for j, c in enumerate(cs if SET[3] is not None else []):
            fn = os.path.join(SET[2], "thumbs", f"{SET[3]}{i:04d}_{j}.jpg")
            if c["thumb"] and not os.path.exists(fn):
                try:
                    open(fn, "wb").write(get(c["thumb"]))
                except Exception as e:
                    print(f"[{i}] 썸네일 실패 {c['title']}: {e}")
            c["file"] = os.path.relpath(fn, HERE)
        cands[key] = cs
        json.dump(cands, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[{i}] {key}: 후보 {len(cs)}개")
        time.sleep(1.5 if SET[3] is not None else 0.8)


def cmd_sheets():
    from PIL import Image, ImageDraw, ImageFont
    cands = json.load(open(os.path.join(SET[2], "candidates.json"), encoding="utf-8"))
    os.makedirs(os.path.join(SET[2], "sheets"), exist_ok=True)
    font = ImageFont.load_default()
    for f in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if os.path.exists(f):
            font = ImageFont.truetype(f, 18)
            break
    cell, label = 200, 260
    by_cat1 = {}
    for i, r in enumerate(rows()):
        a, b = SET[1]
        by_cat1.setdefault(r[a], []).append((i, r[b], cands.get(key_of(r), [])))
    for c1, items in by_cat1.items():
        for part in range(0, len(items), 12):
            chunk = items[part:part + 12]
            sheet = Image.new("RGB", (label + cell * N_CAND, cell * len(chunk)), "white")
            d = ImageDraw.Draw(sheet)
            for y, (i, c2, cs) in enumerate(chunk):
                d.text((6, y * cell + 8), f"{i:04d}", fill="black", font=font)
                for k in range(0, len(c2), 12):
                    d.text((6, y * cell + 32 + k * 2), c2[k:k + 12], fill="black", font=font)
                for j, c in enumerate(cs):
                    fn = os.path.join(HERE, c.get("file", ""))
                    if not os.path.exists(fn):
                        continue
                    im = Image.open(fn).convert("RGB")
                    im.thumbnail((cell - 8, cell - 8))
                    x0 = label + j * cell
                    sheet.paste(im, (x0 + 4, y * cell + 4))
                    d.text((x0 + 6, y * cell + 6), str(j), fill="red", font=font)
            safe = re.sub(r"[/:\s]+", "_", c1)
            out = os.path.join(SET[2], "sheets", f"{safe}_{part // 12 + 1}.jpg")
            sheet.save(out, quality=80)
            print(out)


def cmd_pick():
    cands = json.load(open(os.path.join(SET[2], "candidates.json"), encoding="utf-8"))
    picks = {}
    pp = os.path.join(HERE, SET[5])
    if os.path.exists(pp):
        for line in open(pp, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                k, v = line.rstrip("\n").split("\t")[:2]
                picks[k] = v
    refs, missing = {}, []
    for r in rows():
        key = key_of(r)
        cs, v = cands.get(key, []), picks.get(key, "")
        if v == "" or v == "-" or not cs:
            missing.append(key)
            continue
        c = cs[int(v)]
        refs[key] = {k: c[k] for k in ("title", "page", "url", "license", "author")}
    json.dump(refs, open(os.path.join(HERE, SET[6]), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{SET[6]}: {len(refs)}개, 고르지 못함 {len(missing)}개")
    for k in missing:
        print("  -", k)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        SET = SETS[sys.argv[2]]
        N_CAND = SET[4]
    {"search": cmd_search, "sheets": cmd_sheets, "pick": cmd_pick}[sys.argv[1]]()
