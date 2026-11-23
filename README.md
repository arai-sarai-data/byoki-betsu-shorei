# 病気の分野別・入院患者数

その病気で入院した患者は、どの病院に何人いたか。国のDPC調査の公開データを、病気の分野ごとに病院別で並べました。

公開ページ：https://arai-sarai-data.github.io/byoki-betsu-shorei/

## 仕組み

- `fetch.py` が公式の公開データを取得・検証・集計し、`docs/data/` に JSON を書き出します。
- GitHub Actions（`.github/workflows/update.yml`）が毎月2日に自動で実行し、GitHub Pages に公開します。
- 元データの形式が想定と違うときは **数字を推測で埋めずに停止** します（前回の正しいデータが表示され続けます）。停止した理由は Actions のログに `データ検証で停止しました` として出ます。

## 最初の設定（1回だけ）

1. このフォルダの中身を `arai-sarai-data/byoki-betsu-shorei` リポジトリ（Public）に置く。
2. Settings → Pages → Build and deployment の Source を **GitHub Actions** にする。
3. Settings → Actions → General → Workflow permissions を **Read and write permissions** にする。
4. Actions タブ → `update` → **Run workflow** で初回のデータ取得を実行する。

## 出典

- 厚生労働省が毎年公開しているDPC退院患者調査の結果から、病気の分野（MDC）ごとの年間の退院患者数を、病院別に探せるようにしたものです

各データの利用条件に従い、出典を明記して加工・公開しています（`docs/about.html`）。
