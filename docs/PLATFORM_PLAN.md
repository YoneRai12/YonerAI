# ORA Platform Plan (Draft)

Last updated: 2026-02-08

Related:
- `docs/PLATFORM_REVIEW_AND_RISKS.md` (devil's advocate review / risks)

## 目的
- ORAを「配布型のローカルAI秘書 (Node)」として成立させる。
- 同じ体験を iOS / Mac / Web / PC から使えるようにする (Clients)。
- ユーザーのPCが無い/弱い/オフライン時は、課金でクラウド実行に切り替えられるようにする (Cloud)。
- 将来の商業化に耐える形で、運用・権限・監査・課金の土台を固める。

## やりたいこと整理 (1-5)
共通: ORA Core (会話 -> 計画 -> ツール実行 -> 監査/メモリ -> 応答)

1. 自分のPCで生きるAI (Local Power)
- ローカル前提。速度/自由度最優先。外部公開は不要。

2. 自分だけの秘書 (Private)
- プライバシー最優先。外部公開は最小。アクセスは自分だけ。

3. みんなも使える秘書 (Shared)
- 友達/コミュニティが使える。荒らし対策・権限・コスト管理・監査が必要。

4. 商業AIプラットフォーム (Commercial SaaS)
- 認証/課金/監視/SLO/法務/サポートが本体。運用できる形が必要。

5. 配布型「自分専用マルチプラットフォームAI」(Node + Clients)
- ユーザーが自分のPCにORAを入れたら、そのPCを拠点にiOS/Web/Mac/PCから同じ秘書として使える。
- さらに周りの友達に共有(ただし権限は制限)できる。
- 4(商業)と接続できる: PCが弱い/無い時はクラウド課金に切替。

結論:
- 今やっている主軸は「5」。
- 「4」は5の上に載る(認証/課金/運用)ので、早い段階から前提だけは入れておく。

## ターゲットアーキテクチャ (最終形のイメージ)
### コンポーネント
- ORA Node (ユーザーPC):
  - ローカルのツール実行(ブラウザ操作/ファイル/生成/ローカル統合)
  - ローカルDB/メモリ/ログ(ユーザーのデータは原則ここ)
  - 外からの接続は「直接受け」より「外向き常時接続」を推奨
  - 原則: ユーザーデータの保管と実行の主体(ここが真実)

- ORA Clients (あなたが配布するUI):
  - iOSORA / MacORA / WebORA / DesktopORA
  - Node もしくは Cloud へ接続するだけ(体験を揃える)

- ORA Relay (クラウド):
  - 認証、ペアリング、端末一覧、通知、セッション中継(WebSocket等)
  - 役割: 「中継と認証」まで(実行はしない)
  - 方針: 会話/ファイル等の中身は原則扱わない(暗号文中継/E2EE寄り)
  - ユーザーにポート開放やCloudflare設定を要求しない(配布性が上がる)

- ORA Cloud (クラウド実行/課金対象):
  - 役割: 「実行(課金対象)」のみ
  - モデル呼び出し/外部API実行/ジョブ実行、使用量メーター、請求イベント
  - GPUは当面持たない(最新モデルはAPIで使うのが合理的)

### 実行パス(概略)
- 通常: Client -> Relay -> Node (ローカルで実行)
- 代替: Client -> Relay -> Cloud (課金で実行)

## Trust Boundary / 境界 (最重要)
前提:
- Node: 実行とデータの主体(ユーザーのPC)
- Relay: 接続/認証/課金状態などのメタデータ(クラウド)。ただし中身は見ない方針
- Cloud: 明示的に「クラウド実行」に切り替えた処理だけを実行(課金対象)

方針:
- Relayは平文を持たない設計に寄せる(将来の法務/プライバシー負担を軽くする)
- 最初のMVPで完全E2EEをやり切れない場合でも、少なくとも「中身を保存しない」「監査はメタデータ中心」を固定する

## 脅威モデル (Threat Model)
攻撃者(例):
- ゲスト(悪意/荒らし)
- 乗っ取られたクライアント端末
- 漏れたトークン/セッション
- Relay侵害
- LAN内盗聴者/中間者

守るもの(例):
- PCの操作権(最重要)
- ファイル/ローカル資産
- ブラウザセッション(ログイン状態、Cookie)
- APIキー/認証情報
- 会話ログ/メモリ、生成物
- 課金/請求の整合性

代表的な失敗(例):
- トークン漏洩 -> PC遠隔操作
- プロンプト注入 -> 危険ツール実行
- ログ/メモリ混線 -> プライバシー事故

仕組みで固定する対策:
- 危険ツールはデフォルト禁止(shared/guest)
- Approvals(承認)はHIGH以上で必須、CRITICALは原則禁止(共有)
- トークンは最小権限・期限付き・失効可能(発行/失効を監査)
- リモート操作は別チャネル承認(Ownerの端末で最終確認)に寄せる

## データと鍵 (Data & Keys)
識別:
- Nodeは `instance_id` を持つ(PCごとに一意)
- Clientは `device_id` を持つ(端末ごとに一意)

分離:
- `profile=private/shared` で状態ディレクトリ完全分離(DB/ログ/メモリ/secret)

トークン/鍵の基本方針:
- トークンは平文保存しない(ハッシュ化 or OSの暗号化ストレージ)
- 期限/ローテ/失効を前提にする(漏れても止血できる)

E2EE寄りの設計方針(将来/優先):
- ペアリングで鍵交換(QR/ワンタイムコード)
- Relayは暗号文だけを中継(中身は見ない)
- Cloud保存はオプション。既定はNodeのみ保存、鍵はユーザー側保持が基本

## 配布と更新 (Distribution & Update)
配布型Nodeは「更新できない=死」になりやすいので最初から入れる。
- Nodeの自動更新(最低でも通知 + ワンクリック更新)
- バイナリ署名(改ざん対策)
- Client/NodeのAPIバージョン管理(SemVer、互換期間の定義)
- ロールバック(壊れた時に戻せる)

## ドメイン/公開戦略
前提: 1つのドメイン配下にサブドメインを切る。ドメイン数はユーザー数に比例しない。

推奨(例):
- `app.example.com` : WebORA (ログイン/設定/履歴)
- `relay.example.com` : Relay (中継)
- `api.example.com` : Cloud API (課金)
- `docs.example.com` : ドキュメント
- `status.example.com` : 稼働状況

サブドメインの自動追加:
- 基本はワイルドカードDNSで「追加不要」にする(例: `*.app.example.com`)。
- 追加が必要な場合はDNS API(Cloudflare等)で自動作成。

## 課金方針 (C: 月額 + 従量)
- 月額:
  - Relay利用(安全なリモートアクセス/端末管理/通知/ペアリング)
- 従量:
  - Cloud実行(外部APIコスト + 実行リソース)

## 複数プロバイダ戦略 (前提)
目的:
- 複数AIを切り替え、役割別に使い分けてオーケストレーションする。
- 単一プロバイダ障害/値上げ/制限の影響を減らす。

現実的な進め方:
- まず「OpenAI互換」(OpenAI互換APIのプロバイダ含む)を設定だけで差し替え可能にする。
- Anthropic等の非互換は「専用アダプタ」を後で足す。
- お金を燃やさないため、APIキーが無いプロバイダは自動無効化。テストはモック/ローカルで回す。

## 分離/隔離 (Private/Shared両立のための最低条件)
やりたいこと(自分用 + 友達共有 + 将来商業)を同じコードで成立させるには、最低でも以下を分離する。

- 権限(できること):
  - owner(本人) / guest(共有) / sub-admin(任意) で実行可能ツールを分ける
  - HIGH/CRITICAL は承認(Approvals)を必須にして暴発を止める

- データ(見えるもの):
  - user_id / role / guild_id 単位でメモリ/履歴/ログ/生成物を分離

- 実行プロファイル(起動モード):
  - `private` と `shared` を最低限用意して、DB/状態/トークン/許可ツールを完全分離

## 直近の課題メモ (開発・運用)
- 外部公開URLはQuick Tunnelだと不安定(保証なし、URLが変わる)なので、配布型(Node)ではRelay方式が本命。
- ただし現状の開発/検証ではCloudflare Tunnelが便利なので「デバッグ用途」として残す。

## マイルストーン案 (実装順)
M0. Nodeとして「自分だけ」で安定稼働
- 再現性: セットアップ手順、ruff/pytest、ログの見方
- 安全: 外部公開はデフォルトOFF、必要時だけON

M1. `private/shared` プロファイル化
- DB/ログ/メモリの分離
- Guest権限とツール制限の整理

M2. Relay MVP
- NodeがRelayへ外向き接続
- Client(Web)がRelay経由でNodeに繋がる
- ペアリング(ワンタイムコード/QR)とトークンローテ

M2の最小要件(迷いを減らすために固定):
- Transport: Webクライアントを前提にWebSocketを最優先
- セッション: NodeがRelayへ常時WS接続、ClientもRelayへWS接続、Relayがルーティング
- ペアリング: ワンタイムコード or QR、成功後にOwnerトークン発行
- セキュリティ: まずOwner-onlyで安定させる(shared/guestは後回し)
- 方針: Relayが中身を保存しない(監査は接続/発行/失効などのメタデータ中心)
- 監査: ペアリング成功/失敗、トークン発行/失効、接続履歴を保持

M3. Cloud切替 (従量)
- 同一APIで Node/Cloud を切替できるルーティング
- Usage集計(メーター)と請求の基礎

M4. 商用化の最低ライン
- 認証(アカウント)、課金(月額+従量)、監視/アラート、利用規約/プライバシー方針

## オープンな意思決定 (あとで詰める)
- Relay方式の実装選択:
  - WebSocket常時接続、gRPC、またはHTTP/2ストリーム等
- Clientの優先順位:
  - まずWebORA、その後iOS/Mac
- データの同期:
  - Nodeローカルに残すのが原則。Cloudに保存するのはオプションにするか。
- 共有(ゲスト)の境界:
  - ゲストに許可する最小ツールセットと、承認必須ラインの確定

暫定の推奨(実装が分岐しないように仮置き):
- sharedの範囲: 友達だけ(小規模)を前提にする。不特定多数は別プロダクト扱い
- guestの許可: 読み取り中心 + 承認付きの限定操作(自由操作は事故りやすい)
- データ同期: 既定はNodeのみ保存。Cloud保存はONにした人だけ(バックアップ/同期オプション)

---

## EN Quick Summary
- ORA should become a distributable "Node" running on each user's PC, accessible from Web/iOS/Mac clients.
- Add a Relay/Auth plane under a single domain (subdomains), with monthly subscription for relay access and usage-based billing for cloud execution.
- Keep inference via external APIs (no GPU hosting initially). Build provider abstraction first (OpenAI-compatible via config; add non-compatible adapters later).
- Support both private and shared usage via strict separation: permissions, data isolation, and run profiles (`private`/`shared`).
- Clarify trust boundaries: Node holds data and executes; Relay authenticates and routes (prefer ciphertext / do not store content); Cloud executes only explicit paid workloads.
- Add threat model + key management + update strategy early to avoid shared-mode incidents and unpatchable node deployments.
