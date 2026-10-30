"""카테2별 레퍼런스 이미지 수집 (위키미디어 커먼즈, 자유 라이선스만).

    python3 motionspec/refs/collect.py search   # 카테2마다 후보 검색, 썸네일을 cache/에 받음
    python3 motionspec/refs/collect.py sheets   # 카테1별 후보 대조표(contact sheet)를 cache/sheets/에 만듦
    python3 motionspec/refs/collect.py pick     # picks.tsv(카테2별 고른 후보 번호)로 refs.json 작성

저장소에는 이미지 파일을 넣지 않고 원본 주소·작가·라이선스만 refs.json에 남긴다.
필요한 접속: commons.wikimedia.org, upload.wikimedia.org
"""
import csv, json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
API = "https://commons.wikimedia.org/w/api.php"
UA = "motionspec-refs/0.1 (posture label reference collection)"
N_CAND = 6
THUMB_W = 256
FREE = re.compile(r"^(CC0|Public domain|PD|CC BY(-SA)? [\d.]+)", re.I)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def rows():
    with open(os.path.join(HERE, "queries.tsv"), encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


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
        out.append({
            "title": p["title"], "page": ii.get("descriptionurl"), "url": ii.get("url"),
            "thumb": ii.get("thumburl"), "license": lic,
            "author": strip_html(meta.get("Artist", {}).get("value")),
        })
        if len(out) == N_CAND:
            break
    return out


def cmd_search():
    os.makedirs(os.path.join(CACHE, "thumbs"), exist_ok=True)
    path = os.path.join(CACHE, "candidates.json")
    cands = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for i, r in enumerate(rows()):
        key = f"{r['카테1']} > {r['카테2']}"
        if key in cands:
            continue
        try:
            cs = search(r["검색어"])
        except Exception as e:
            print(f"[{i}] {key}: 검색 실패 {e}")
            continue
        for j, c in enumerate(cs):
            fn = os.path.join(CACHE, "thumbs", f"{i:03d}_{j}.jpg")
            if c["thumb"] and not os.path.exists(fn):
                try:
                    open(fn, "wb").write(get(c["thumb"]))
                except Exception as e:
                    print(f"[{i}] 썸네일 실패 {c['title']}: {e}")
            c["file"] = os.path.relpath(fn, HERE)
        cands[key] = cs
        json.dump(cands, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[{i}] {key}: 후보 {len(cs)}개")
        time.sleep(0.5)


def cmd_sheets():
    from PIL import Image, ImageDraw, ImageFont
    cands = json.load(open(os.path.join(CACHE, "candidates.json"), encoding="utf-8"))
    os.makedirs(os.path.join(CACHE, "sheets"), exist_ok=True)
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
        by_cat1.setdefault(r["카테1"], []).append((i, r["카테2"], cands.get(f"{r['카테1']} > {r['카테2']}", [])))
    for c1, items in by_cat1.items():
        for part in range(0, len(items), 12):
            chunk = items[part:part + 12]
            sheet = Image.new("RGB", (label + cell * N_CAND, cell * len(chunk)), "white")
            d = ImageDraw.Draw(sheet)
            for y, (i, c2, cs) in enumerate(chunk):
                d.text((6, y * cell + 8), f"{i:03d} {c2}", fill="black", font=font)
                for j, c in enumerate(cs):
                    fn = os.path.join(HERE, c.get("file", ""))
                    if not os.path.exists(fn):
                        continue
                    im = Image.open(fn).convert("RGB")
                    im.thumbnail((cell - 8, cell - 8))
                    x0 = label + j * cell
                    sheet.paste(im, (x0 + 4, y * cell + 4))
                    d.text((x0 + 6, y * cell + 6), str(j), fill="red", font=font)
            out = os.path.join(CACHE, "sheets", f"{c1}_{part // 12 + 1}.jpg")
            sheet.save(out, quality=80)
            print(out)


def cmd_pick():
    cands = json.load(open(os.path.join(CACHE, "candidates.json"), encoding="utf-8"))
    picks = {}
    pp = os.path.join(HERE, "picks.tsv")
    if os.path.exists(pp):
        for line in open(pp, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                k, v = line.rstrip("\n").split("\t")[:2]
                picks[k] = v
    refs, missing = {}, []
    for r in rows():
        key = f"{r['카테1']} > {r['카테2']}"
        cs, v = cands.get(key, []), picks.get(key, "")
        if v == "" or v == "-" or not cs:
            missing.append(key)
            continue
        c = cs[int(v)]
        refs[key] = {k: c[k] for k in ("title", "page", "url", "license", "author")}
    json.dump(refs, open(os.path.join(HERE, "refs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"refs.json: {len(refs)}개, 고르지 못함 {len(missing)}개")
    for k in missing:
        print("  -", k)


if __name__ == "__main__":
    {"search": cmd_search, "sheets": cmd_sheets, "pick": cmd_pick}[sys.argv[1]]()
