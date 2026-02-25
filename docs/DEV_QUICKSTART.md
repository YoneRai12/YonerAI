# DEV_QUICKSTART

対象範囲: 公開リポジトリ `YonerAI`
最終更新対象: docs-only
信頼できる一次ソース: `README.md`, `docs/ENV_FILES.md`

## 1) 開発環境（Windows）
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

## 2) ローカル起動（代表）
```powershell
python main.py
```

必要に応じて Web/API 入口:
```powershell
uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

## 3) テスト
```powershell
.\.venv\Scripts\python -m pytest -q
```

## 4) Git 運用ポリシー（公開/私用分離）
- `origin` への直接 push は行わない。
- 公開向けは `public` remote、私用バックアップ/運用向けは `private` remote を使う。
- main へ直接 commit しない。機能ブランチ + PR で統合する。

## 5) 公開禁止物（必須）
- `.env` / `.env.*`（`.env.example`のみ可）
- 鍵ファイル、資格情報JSON、トークンを含むログ/ダンプ
- 端末ローカル絶対パスを含む一時ファイル

## 6) route_score v1 方針（運用前提）
- 単一軸 `route_score` (0..1) で実行深度を切り替える。
- 初期は保守的閾値を採用し、運用ログで較正する。
- 高リスク判定時は安全側へ強制フォールバックする。

## 7) 最小の開発サイクル
1. ブランチ作成
2. 最小差分で実装
3. pytest
4. シークレットスキャン
5. PR

## 参照
- `docs/AI_STATE.md`
- `docs/ARCH_V5.md`
- `docs/DECISION_CHAT_SDK.md`
