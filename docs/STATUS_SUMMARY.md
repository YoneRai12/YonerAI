# ORA Status Summary (Private Memo)

Date: 2026-02-08

このメモは「いま何ができていて、何が解決されて、次に何をやると何が手に入るか」を迷子にならない形でまとめたもの。

## 目的（いま作っているもの）

配布型 ORA を作っている。

- 各ユーザーが **自分のPCに ORA（Node）を入れる**
- そのPCが「秘書の本体」になり、**スマホ/WEB/Discord から同じ秘書を使える**
- ポート開放や固定IPを要求しない（Node が外へ繋ぎっぱなしの方式）

## 登場人物（最小の言い方）

- Node: ユーザーPCで動く本体（データ、ツール実行、承認、監査）
- Client: UI（依頼を出して結果を見るだけのフロントエンド）
  - 対応ターゲット: Web / iOS / Android / Windows / macOS / Discord（必要なら Linux も）
- Relay: 中継サーバ。Client と Node を繋ぐだけ（できれば本文を保持しない）

## ここまでの到達点（意味でまとめ）

### M1: private/shared 分離（混ざらない）

- `ORA_PROFILE=private|shared` で **DB/ログ/メモリ/secret を物理分離**
- `instance_id` を固定して、配布後も「このPCのNode」を識別できる

結果:
- private と shared が **混ざって事故る**系を消した

### M1.5: Approvals（暴発しない）

- HIGH/CRITICAL のツールは勝手に実行されない
- **別チャネル承認**（Owner DM + owner-only `/approve` + Web API）
- TTL（期限）/ CRITICAL code / args すり替え防止（`args_hash`）/ code秘匿 / 乱打レート制限

結果:
- 「危険操作が会話の流れで暴発する」系を止血できた

### M3: shared/guest 規約（設定ミスで開かない）

- ツール実行直前の 1 箇所で shared の規約を強制
- shared + guest: allowlist（`ORA_SHARED_GUEST_ALLOWED_TOOLS`）で「見える/叩ける」を固定
- shared + guest: CRITICAL デフォルト禁止（`ORA_SHARED_ALLOW_CRITICAL=0`）
- 未知ツールが LOW 扱いにならないよう HIGH に倒す

結果:
- 配布先での「うっかり危険ツール開放」を潰した

## Relay（外から繋ぐ回路）

### M2: Relay MVP（繋がる）

仕組み（ざっくり）:

1. Node コネクタが Relay に WebSocket で常時接続（アウトバウンド）
2. Client も Relay に接続
3. Relay が Client の要求を Node に転送
4. Node コネクタがローカル Web API（例: `127.0.0.1:8000`）を叩いて結果を返す

現状の最小ドキュメント:
- `docs/RELAY_MVP.md`

### M2.5: Relay Hardening（外で崩れない方向）

外で壊れやすい典型に先回りして対策済み:

- mux 入口（`id -> Future` 待ち合わせ）で混線しない
- pairing code をワンタイム化（奪われても多重侵入しにくい）
- pending 上限（`ORA_RELAY_MAX_PENDING`）
- id 衝突拒否（`id_in_use`）
- per-request timeout（`ORA_RELAY_CLIENT_TIMEOUT_SEC`）
- Node 切断時の掃除（pending fail + pair_offer削除）
- **timeout/例外でも必ず pending が片付く**（`try...finally`）
- WebSocketフレーム/メッセージ上限を uvicorn 側にも適用（`ws_max_size`）

## いま「完成した」と言えること

- Node 側: 混ざらない（private/shared）、暴発しない（Approvals + 規約）
- Relay 側: 繋がる、混線しない、溜まらない、巨大メッセージで死ににくい
- 外部公開前: ドメイン無しでもローカル/IP直叩き/一時トンネルで検証できる

## 次にやること（一本道）

### Step 1: shared E2E 証拠取り（1回）

目的:
- allowlist → 承認 → 実行/ブロック が現実に噛んでる証拠を取る
- 後で事故っても「Relayの問題か / Nodeの問題か」が切り分けやすくなる

### Step 2: Relay ローカル 1 往復

目的:
- 中継が最低限成立している確認
- 1リクエスト後に pending が増え続けないこと（戻ること）を確認

### Step 3: VPS に Relay を置く（`ws://IP:PORT`）

目的:
- インターネット越しの不安定さで崩れないかを見る
- ドメイン無しでできる段階（コスパ良い）

### Step 4: ドメイン + TLS（wss）で入口固定

目的:
- ブラウザ/iOSで “普通に使える” 入口になる
- ここで初めてドメインが効いてくる（中が固まってから買うのが燃えにくい）

## ドメイン購入（結論）

ドメインは「買った瞬間に進む」ものではなく、**入口を固定する工程**の道具。
いまの主戦場（承認/規約/中継の耐久）では必須ではない。
