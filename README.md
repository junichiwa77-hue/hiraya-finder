# ひらや探し

埼玉と宇都宮（栃木）の中古・空き家の**平屋**を集める、自分専用のキュレーションサイト。
巡回スクリプトが各ソースを定期的に見に行き、`docs/data.json` を更新する。
通知はなく、好きなときに公開URLを開いて眺める使い方。

```
hiraya-finder/
├─ docs/
│  ├─ index.html   ← サイト本体（data.json を読んで一覧表示）
│  └─ data.json    ← 物件データ（crawler.py が上書き）
├─ crawler.py      ← 巡回スクリプト（アダプタ方式）
├─ requirements.txt
└─ .github/workflows/crawl.yml  ← 毎日 07:00 JST に自動実行
```

## 仕組み

```
crawler.py（GitHub Actionsが定期実行）
   ├─ 物件ファンRSS / 自治体バンク / … を巡回
   ├─ 共通スキーマに正規化 → IDで重複排除（初出日は維持）
   └─ docs/data.json を更新してコミット
         ↓
GitHub Pages が docs/ を配信 → ブラウザで開く
```

## 公開（GitHub Pages）

1. このフォルダを GitHub リポジトリに push
2. Settings → Pages → Source を **Deploy from a branch**、ブランチ `main` / フォルダ `/docs` に設定
3. `https://<ユーザー名>.github.io/hiraya-finder/` で開ける

## 巡回の追加・調整

`crawler.py` の `ADAPTERS` に1行足すだけで対象を増やせる。

- **物件ファン**：公開RSS（`/feed/`）をキーワードで絞る。実装済み。
- **自治体の空き家バンク**：`CityAkiyaBank` に一覧URLとCSSセレクタを入れて有効化。サイトごとに構造が違うので現物を見て調整する。
- 拾う条件は `TAG_WORDS`（平屋・古民家のキーワード）/ `SAITAMA_WORDS` / `TOCHIGI_WORDS` で変更。平屋でも古民家でもない物件は対象外。

ローカル実行：

```bash
pip install -r requirements.txt
python crawler.py        # docs/data.json が更新される
```

## マナーと注意

- 大手ポータル（SUUMO・アットホーム等）は利用規約で自動取得を禁じている場合が多い。それらは各サイトの「新着お知らせメール」を使うのが安全。このスクリプトは公開RSSと、公共性の高い自治体バンクを控えめな間隔（既定2秒）で巡回する前提。
- 各ソースの robots.txt と利用規約は導入前に確認すること。
- 物件の最新状況・価格は必ず掲載元で確認する。
