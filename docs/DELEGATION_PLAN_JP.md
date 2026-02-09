# ORA 委任用 実装計画書（Gemini/他AIでも実装できる粒度）

作成日: 2026-02-09  
Repo: `c:\Users\YoneRai12\Desktop\ORADiscordBOT-main3`

このドキュメントは「決めることが残らない」レベルまで分解した実装計画です。別AIに渡しても、設計判断なしで実装タスクとして進められることを目的にしています。

---

## 0. いま作ってるもの（1行）

ORAは配布型のAI秘書で、各ユーザーのPC上に **Node（本体）** を置き、**Relay（中継）** を介して **Client（Web/iOS/Android/Windows/macOS/Discord等）** から同じ秘書にアクセスできる構成。危険操作は **Policy + Approvals** で止め、ダウンロードが失敗しても安全なフォールバックで評価を続行できる。

---

## 1. 絶対ルール（安全 + リポジトリ運用）

1. `.env` や鍵/トークンは絶対にコミットしない。
1. `reference_clawdbot` はサブモジュールなので、親repoでステージしない（dirtyに見えても触らない）。
1. インターネットから落としたコードを勝手に実行しない。Sandboxは「静的検査のみ」。
1. Routerは勝手に能力を広げない（`web_download` やリモートブラウザ操作を暗黙で選ばない）。
1. 新しい挙動は必ず `.env` フラグでON/OFFできるようにして、デフォルトは安全側。

push前の推奨ステージ（事故防止）:

```powershell
git add README.md README_JP.md AGENTS.md docs/ src/ core/ tests/ .env.example
```

---

## 2. 現状の事実（何が既にできているか）

### 2.1 役割

1. Node: ユーザーPCで動く本体（データ保持、ツール実行、承認、監査）
1. Client: UI（Web/iOS/Android/Windows/macOS/Discordなど）
1. Relay: 中継サーバ（ClientとNodeを繋ぐ）。本文は永続化しない方針。

### 2.2 既に入ってるガード

1. うっかりダウンロード抑止: `ORA_ROUTER_REQUIRE_EXPLICIT_DOWNLOAD=1`
1. GitHub比較/評価はSANDBOXへ: `ORA_ROUTER_AUTO_SANDBOX_GITHUB_REVIEW=1`（ただし `web_download` は出さない）
1. Sandbox ZIPダウンロード失敗時フォールバック: `ORA_SANDBOX_FALLBACK_ON_DOWNLOAD_FAIL=1`（GitHub API read-only）
1. Ownerの承認QoL: `ORA_PRIVATE_OWNER_APPROVALS`, `ORA_OWNER_APPROVALS` など
1. READMEの図はSVG固定（GitHubのMermaidテーマ差で読めない問題を回避）

---

## 3. “加減（Dial）”のルール（ダウンロード vs 評価継続）

目的: 「会話を読んで良い感じに動く」体験を保ちつつ、事故を起こさない。

### 3.1 意図を3種類に分ける

1. 評価/比較: 解析が目的。ダウンロードは必須ではない。
1. 静的検証/スキャン: Sandbox静的検査が適切。
1. ダウンロード/保存: 明示された時だけ許可。

### 3.2 決め打ちのルール（実装側はここを守る）

1. 明示がない限り `web_download` は選ばない。
1. GitHub URL + 「比較/評価/review」なら SANDBOX を優先する。
1. SANDBOXのZIPダウンロードが失敗しても、GitHub API read-onlyに落として評価を継続する。
1. フォールバックでも「危険側（別サイト巡回/実行/保存）」には勝手に拡大しない。

---

## 4. 次のマイルストーン（順番固定）

1. M2.6: Relayの硬化（keepalive、切断掃除、Node認証）
1. M2.7: クライアント互換の固定（request_id mux仕様、後方互換）
1. M2.8: マルチプラットフォームClient最小セット（同一プロトコル + 薄いUI）
1. M3+: E2EE段階導入（Relayが本文を見ない）

---

## 5. Work Packages（別AIに渡す単位）

各WPは「変更ファイル」「手順」「Done条件」「テスト」が揃ってる状態にする。

### WP-A: Relay keepalive + 切断掃除（M2.6）

目的:

1. WSが中間機器で落ちにくい（ping/pong）
1. 切断時にpendingが残らない（リークしない）

対象:

1. `src/relay/app.py`
1. `src/services/relay_node.py`
1. `tests/`

Done:

1. 切断後 `pending==0` が保証される
1. 外で長時間動かしてもメモリが増え続けない

### WP-B: Node認証（M2.6）

目的:

1. 偽Node接続を防ぐ（`/ws/node` に認証を入れる）

決め打ち:

1. Relayは「平文secretを保存しない」（hashだけ保持）
1. ペアリング成功時にNode secretを1回だけ返す（将来の拡張）

Done:

1. 認証無し/不正は拒否

### WP-C: フォールバック表示のUX（M2.6）

目的:

1. 「ダウンロード失敗したけどread-onlyで続けた」をユーザーに明確に伝える

対象:

1. `src/cogs/handlers/chat_handler.py`

Done:

1. `fallback_used` がtrueの時に、Discord返信が分かりやすい

### WP-D: プロトコル仕様の固定（M2.7）

成果物:

1. `docs/PROTOCOL.md` を唯一の正として維持
1. JS/Pythonの最小サンプル（できれば）

Done:

1. Web/iOS/Android/Windows/macOSで同じメッセージ形式が使える

### WP-E: Mermaid図のSVG自動生成（任意）

目的:

1. READMEの図が常に見える（GitHubレンダラ差に依存しない）

成果物:

1. `.github/workflows/diagrams.yml`

---

## 6. 受け入れ基準（チェックリスト）

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m pytest -q
```

動作面（例）:

1. 「GitHub2URL + 比較/評価」→ `sandbox_compare_repos`（`web_download`は出ない）
1. SandboxのZIPが失敗しても評価は継続（read-onlyフォールバック）

---

## 7. Geminiに渡すコピペ（テンプレ）

```text
あなたは ORA repo の WP-<X> を実装します。
制約:
- .env は触らない（.env.example のみ）
- reference_clawdbot サブモジュールはステージしない
- 新しい挙動は env フラグで制御、デフォルトは安全側
- pytest -q / ruff check . が通るまで直す

対象WP:
<ここにWP本文を貼る>
```

---

## 8. Owner向けおすすめ `.env`（使い勝手の改善）

1. 自分だけ（private）:
1. `ORA_PROFILE=private`
1. `ORA_PRIVATE_OWNER_APPROVALS=critical_only`

1. 共有（shared）:
1. `ORA_SHARED_OWNER_APPROVALS=high`（sharedではownerでもバイパスしない方が事故らない）
1. `ORA_SHARED_GUEST_ALLOWED_TOOLS=...`（明示allowlist）
1. 必要なら `ORA_SHARED_GUEST_APPROVAL_MIN_SCORE=60`（MEDIUMは承認なしにできる）

---

## 9. 既知のリスク（TODO）

1. `Healer` がローカルLLMに繋ぎに行って失敗するログが出る場合がある（無効化/フォールバック設計が必要）
1. Relayは今は平文を中継できる（E2EEは将来）
1. shared/guestの運用は、公開範囲が広がるほど荒らし対策/課金/監査が本体になる

