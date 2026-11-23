"""病気の分野別・症例数の多い病院：厚生労働省「DPC退院患者調査」の公開データ
（MDC別医療機関別件数・施設概要表）から、病気の分野（MDC：主要診断群）ごとの年間の退院患者数を病院別に並べる。

医療広告にならないよう、病院の評価・推薦はせず、国の公開データの件数をそのまま示す。
病院から金銭・紹介料を受け取らない。"""
import io
import re
from collections import defaultdict

from lib import oc

INDEX = "https://www.mhlw.go.jp/stf/shingi/shingi-chuo.html?tid=128164"
MDC = {"01": "神経系", "02": "眼科系", "03": "耳鼻咽喉科系", "04": "呼吸器系", "05": "循環器系", "06": "消化器系・肝臓・胆道・膵臓",
       "07": "筋骨格系", "08": "皮膚・皮下組織", "09": "乳房", "10": "内分泌・栄養・代謝", "11": "腎・尿路系・男性生殖器系",
       "12": "女性生殖器系・産褥期・異常妊娠分娩", "13": "血液・造血器・免疫臓器", "14": "新生児・先天性奇形",
       "15": "小児疾患", "16": "外傷・熱傷・中毒", "17": "精神疾患", "18": "その他"}


def report_page():
    html = oc.decode(oc.get(INDEX))
    # リンク文字は「資料」で、調査名はリンクの手前に書かれている（ページの上が最新）
    for u, text, before in oc.anchors(INDEX, r"mhlw\.go\.jp/stf/shingi2/", html):
        ctx = before[-100:] + text
        if "退院患者調査" in ctx and "結果報告" in ctx:
            m = re.findall(r"(?:令和|平成)(?:\d+|元)年度", ctx)
            return u, (m[-1] if m else "")
    raise oc.DataError("退院患者調査の結果報告ページが見つかりません")


def sheets(url):
    import openpyxl
    b = oc.get(url, timeout=600)
    if url.endswith(".zip"):
        out = []
        for k, v in oc.unzip(b).items():
            if k.lower().endswith((".xlsx", ".xlsm")):
                out += sheets_b(v)
        return out
    return sheets_b(b)


def sheets_b(b):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(b), read_only=True, data_only=True)
    return [list(ws.iter_rows(values_only=True)) for ws in wb.worksheets]


def header(rows, word):
    for i, r in enumerate(rows[:20]):
        if r and any(word in str(c or "") for c in r):
            return i, [re.sub(r"\s", "", str(c or "")) for c in r]
    return None, None


def run():
    page, year = report_page()
    oc.log("report", year, page)
    files = oc.anchors(page, r"\.(xlsx|zip)$")
    def find(*words):
        for u, text, before in files:
            t = text + " " + before[-60:]
            if all(w in t for w in words):
                return u
        return None
    u_fac = find("施設概要")
    u_mdc = find("MDC別", "医療機関別") or find("ＭＤＣ別", "医療機関別")
    oc.check(u_fac and u_mdc, "施設概要表・MDC別医療機関別件数のファイルが見つかりません")

    # 施設概要表：告示番号/通番 → 施設名・都道府県・病床数
    fac = {}
    for rows in sheets(u_fac):
        hi, h = header(rows, "施設名")
        if hi is None:
            continue
        i_name = next(i for i, x in enumerate(h) if "施設名" in x)
        i_key = next((i for i, x in enumerate(h) if "告示番号" in x), None)
        i_tsu = next((i for i, x in enumerate(h) if "通番" in x), None)
        i_pref = next((i for i, x in enumerate(h) if "都道府県" in x), None)
        i_bed = next((i for i, x in enumerate(h) if "病床" in x and "総" in x), None) or \
            next((i for i, x in enumerate(h) if "病床" in x), None)
        for r in rows[hi + 1:]:
            if not r or not r[i_name]:
                continue
            key = str(r[i_tsu] if i_tsu is not None else r[i_key]).strip()
            fac[key] = {"name": str(r[i_name]).strip(),
                        "pref": str(r[i_pref]).strip() if i_pref is not None else "",
                        "beds": oc.num(r[i_bed]) if i_bed is not None else None}
    oc.check(len(fac) > 3000, "施設概要表の施設数が少なすぎます(%d)" % len(fac))

    # MDC別医療機関別件数
    counts = defaultdict(dict)
    names = {}
    for rows in sheets(u_mdc):
        hi, h = header(rows, "施設名")
        if hi is None:
            continue
        i_name = next(i for i, x in enumerate(h) if "施設名" in x)
        i_tsu = next((i for i, x in enumerate(h) if "通番" in x), None) or next((i for i, x in enumerate(h) if "告示番号" in x), None)
        cols = {}
        for i, x in enumerate(h):
            m = re.search(r"(?:MDC|ＭＤＣ)?(\d\d)", x) if ("MDC" in x or "ＭＤＣ" in x or re.fullmatch(r"\d\d", x)) else None
            if m and m.group(1) in MDC:
                cols[m.group(1)] = i
        if len(cols) < 15:
            continue
        # 見出しはMDCごとに「件数」「割合」の2列。見出しの位置の前後から、整数で1より大きい値が入っている列（＝件数）を選ぶ
        sample = [r for r in rows[hi + 1:hi + 300] if r and r[i_name]]
        def is_count(i):
            vals = [oc.num(r[i]) for r in sample if i < len(r)]
            vals = [v for v in vals if v is not None]
            return bool(vals) and max(vals) > 1 and all(float(v).is_integer() for v in vals)
        for m, i in list(cols.items()):
            for j in (i, i - 1, i + 1, i - 2):
                if 0 <= j < len(h) and is_count(j):
                    cols[m] = j
                    break
        for r in rows[hi + 1:]:
            if not r or not r[i_name]:
                continue
            key = str(r[i_tsu]).strip() if i_tsu is not None else str(r[i_name]).strip()
            names[key] = str(r[i_name]).strip()
            for m, i in cols.items():
                v = oc.num(r[i])
                if v is not None:
                    counts[key][m] = v
    oc.check(len(counts) > 3000, "MDC別件数を読み取れた病院が少なすぎます(%d)" % len(counts))
    # 「件数（割合）」の表なので、割合の列を件数と取り違えていないか確かめる（割合なら最大でも100以下）
    tops = sorted((max(c.values()) for c in counts.values() if c), reverse=True)
    oc.check(tops and tops[0] > 1000, "件数ではなく割合の列を読んでいる可能性があります（最大値 %s）" % (tops[:1],))
    oc.check(all(float(v).is_integer() for c in list(counts.values())[:200] for v in c.values()),
             "件数の列に小数が含まれています（割合の列の可能性）")
    by_name = {v["name"]: v for v in fac.values()}
    for key in counts:
        if key not in fac or fac[key]["name"] != names.get(key):
            fac[key] = by_name.get(names.get(key), {"name": names.get(key, key), "pref": "", "beds": None})
    matched = sum(1 for k in counts if fac[k].get("pref"))
    oc.check(matched / len(counts) > 0.9, "施設概要表と件数表の病院が対応しません(%d/%d)" % (matched, len(counts)))

    meth = ("厚生労働省「%sDPC退院患者調査」の公開データ（MDC別医療機関別件数）です。1年間に退院した患者のうち、"
            "医療資源を最も投入した病名の分野（MDC）ごとの件数で、件数が10未満の場合は公表されていません（「—」）。"
            "件数が多いことは治療成績の良さを意味するものではありません。受診先は主治医と相談して決めてください。"
            "本サイトは病院から金銭を受け取っておらず、特定の病院を推奨するものではありません。" % year)
    R = []
    for m, label in MDC.items():
        rows = []
        for key, c in counts.items():
            if m not in c:
                continue
            f = fac.get(key, {})
            rows.append({"name": f.get("name") or key, "pref": f.get("pref", ""), "n": c[m], "beds": f.get("beds")})
        rows.sort(key=lambda x: -x["n"])
        if not rows:
            continue
        R.append({"id": "m" + m, "tab": label, "title": "%s の病気で入院した患者が多い病院（%s）" % (label, year),
                  "desc": "MDC%s（%s）の年間退院患者数。都道府県の列でも並べ替えられます。" % (m, label), "rows": rows,
                  "trend": oc.trend(rows, "pref", 50, "病院", "病院"), "method": meth,
                  "columns": [{"key": "name", "label": "病院"}, {"key": "pref", "label": "都道府県"},
                              {"key": "n", "label": "年間退院患者数", "type": "num", "bar": True},
                              {"key": "beds", "label": "病床数", "type": "num"}],
                  "share_label": "name", "share_value": "n"})
    search = []
    for key, c in counts.items():
        f = fac.get(key, {})
        top = sorted(c.items(), key=lambda kv: -kv[1])[:4]
        search.append({"n": f.get("name") or key, "s": f.get("pref", ""),
                       "k": [[MDC[k], "%d人" % v] for k, v in top]})
    meta = {"data_period": year,
            "stats": [{"label": "データのある病院", "value": len(counts), "unit": "施設"},
                      {"label": "病気の分野（MDC）", "value": len(R), "unit": "分野"}],
            "sources": [{"name": "%sDPC退院患者調査の結果報告" % year, "org": "厚生労働省", "url": page,
                         "license": "公共データ利用規約", "retrieved": oc.today()}]}
    oc.write(meta, R, search=search)


if __name__ == "__main__":
    oc.main(run)
