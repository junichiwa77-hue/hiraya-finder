#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ひらや探し — 巡回スクリプト
=========================================
各ソースを「アダプタ」として実装し、出力を共通スキーマに正規化して
docs/data.json にまとめる。GitHub Actions から定期実行する想定。

共通スキーマ（1物件 = dict）:
  id        : str   ソース内で一意。重複排除のキー
  title     : str
  url       : str   掲載元の詳細ページ
  area      : str   "埼玉" | "宇都宮・栃木"
  city      : str   例 "栃木県宇都宮市"
  source    : str   表示用のソース名
  price     : int|None   万円。不明なら None
  note      : str   price が None のときの表示（"応相談" など）
  area_m2   : float|None
  layout    : str|None   "3DK" など
  built     : int|None    築年（西暦）
  hiraya    : bool        平屋と判定できたか
  image     : str|None

first_seen は本体側で「初めて見つけた日時」を付与するので
アダプタは付けなくてよい。

新しいソースを足すときは Adapter を継承して fetch() を書き、
ADAPTERS に1行足すだけ。
"""

from __future__ import annotations
import json, re, time, datetime, pathlib, sys
from dataclasses import dataclass, field, asdict

import requests
from bs4 import BeautifulSoup

try:
    import feedparser
except ImportError:
    feedparser = None

# ---- 設定 -------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent
OUT  = ROOT / "docs" / "data.json"
JST  = datetime.timezone(datetime.timedelta(hours=9))
UA   = "hiraya-finder/1.0 (personal use; +https://github.com/)"
REQUEST_GAP = 2.0   # 秒。掲載元に負荷をかけないため毎リクエスト後に待つ

# 拾いたい条件
HIRAYA_WORDS = ("平屋", "平家", "ひらや")
SAITAMA_WORDS = ("埼玉", "さいたま", "川越", "秩父", "所沢", "熊谷", "春日部")
TOCHIGI_WORDS = ("宇都宮", "栃木")


def http_get(url: str) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    time.sleep(REQUEST_GAP)
    return r


def classify_area(text: str) -> str | None:
    if any(w in text for w in TOCHIGI_WORDS):
        return "宇都宮・栃木"
    if any(w in text for w in SAITAMA_WORDS):
        return "埼玉"
    return None


def looks_hiraya(text: str) -> bool:
    return any(w in text for w in HIRAYA_WORDS)


# ---- アダプタ基底 -----------------------------------------------------
@dataclass
class Item:
    id: str
    title: str
    url: str
    area: str
    source: str
    city: str = ""
    price: int | None = None
    note: str = "価格応談"
    area_m2: float | None = None
    layout: str | None = None
    built: int | None = None
    hiraya: bool = True
    image: str | None = None


class Adapter:
    name = "base"
    def fetch(self) -> list[Item]:
        raise NotImplementedError


# ---- ① 物件ファン（RSS） ---------------------------------------------
# キュレーションメディア。WordPress の RSS をキーワードで絞るのが一番きれい。
# 公開 RSS のみを読む / 全文スクレイプはしない。
class BukkenFanRSS(Adapter):
    name = "物件ファン"
    FEED = "https://bukkenfan.jp/feed/"

    def fetch(self) -> list[Item]:
        if feedparser is None:
            print("  feedparser 未インストールのためスキップ", file=sys.stderr)
            return []
        out: list[Item] = []
        feed = feedparser.parse(self.FEED, agent=UA)
        for e in feed.entries:
            blob = f"{e.get('title','')} {e.get('summary','')}"
            area = classify_area(blob)
            if not area or not looks_hiraya(blob):
                continue
            out.append(Item(
                id=f"bukkenfan-{abs(hash(e.link)) % 10**8}",
                title=e.title.strip(),
                url=e.link,
                area=area,
                source=self.name,
                hiraya=True,
            ))
        return out


# ---- ② 自治体の空き家バンク（HTML） — 雛形 ---------------------------
# サイトごとに構造が違うので、CSS セレクタを現物に合わせて埋める。
# robots.txt を尊重し、間隔を空けて巡回すること。
class CityAkiyaBank(Adapter):
    """1自治体分のテンプレート。実URL・セレクタを差し替えて使う。"""
    def __init__(self, name, list_url, area, city,
                 row_sel, title_sel, link_sel, base=""):
        self.name = name
        self.list_url = list_url
        self.area = area
        self.city = city
        self.row_sel, self.title_sel, self.link_sel = row_sel, title_sel, link_sel
        self.base = base

    def fetch(self) -> list[Item]:
        out: list[Item] = []
        soup = BeautifulSoup(http_get(self.list_url).text, "html.parser")
        for row in soup.select(self.row_sel):
            title_el = row.select_one(self.title_sel)
            link_el  = row.select_one(self.link_sel)
            if not (title_el and link_el):
                continue
            title = title_el.get_text(strip=True)
            href  = link_el.get("href", "")
            url   = href if href.startswith("http") else self.base + href
            out.append(Item(
                id=f"{self.name}-{abs(hash(url)) % 10**8}",
                title=title, url=url, area=self.area,
                source=self.name, city=self.city,
                hiraya=looks_hiraya(title),
            ))
        return out


# ---- 登録（ここに足していく） ----------------------------------------
ADAPTERS: list[Adapter] = [
    BukkenFanRSS(),
    # 例（実物に合わせて row/title/link セレクタを調整して有効化）:
    # CityAkiyaBank(
    #     name="宇都宮市空き家バンク",
    #     list_url="https://（宇都宮市バンクの一覧URL）",
    #     area="宇都宮・栃木", city="栃木県宇都宮市",
    #     row_sel=".property-list .item",
    #     title_sel=".title", link_sel="a",
    #     base="https://（ドメイン）",
    # ),
]


# ---- マージ＆書き出し -------------------------------------------------
def load_existing() -> dict:
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"updated": None, "items": []}


def main() -> None:
    prev = load_existing()
    seen_first = {i["id"]: i.get("first_seen") for i in prev.get("items", [])}
    now_iso = datetime.datetime.now(JST).isoformat(timespec="seconds")

    fresh: dict[str, dict] = {}
    for ad in ADAPTERS:
        try:
            got = ad.fetch()
            print(f"[{ad.name}] {len(got)} 件")
        except Exception as ex:  # 1ソースが落ちても全体は止めない
            print(f"[{ad.name}] 失敗: {ex}", file=sys.stderr)
            got = []
        for it in got:
            d = asdict(it)
            d["first_seen"] = seen_first.get(it.id, now_iso)  # 既出なら初出日を維持
            fresh[it.id] = d

    # 今回見つからなかった既存物件も、しばらくは残しておく（掲載が一時的に消えることがあるため）
    for old in prev.get("items", []):
        fresh.setdefault(old["id"], old)

    items = sorted(fresh.values(),
                   key=lambda x: x.get("first_seen") or "", reverse=True)
    OUT.write_text(
        json.dumps({"updated": now_iso, "items": items},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"→ {OUT} に {len(items)} 件を書き出し")


if __name__ == "__main__":
    main()
