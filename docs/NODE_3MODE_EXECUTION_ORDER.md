# NODE 3-Mode Execution Order

目的: public YonerAI を 3-mode の配布版 Node product に寄せるための実行順序を固定する。

前提:
- まだ物理 split はしない
- 先に contract と profile を固める
- public/private integration は protocol/contract に限定する

## 1. Contracts freeze

やること:
- relay protocol freeze
- Core SSE contract freeze
- files contract freeze
- auth claims freeze
- capability manifest schema freeze

Done:
- docs と schema が揃う
- cross-repo import なしで synthetic request を組める

## 2. Safe skills extraction

やること:
- public skills を package 単位で切り出せる形に整理
- 最初は safe read skill から始める
- risk/approval/manifest 境界を確認

Done:
- `src/skills/` を common package に見立てても runtime が壊れない
- 代表 safe skill の synthetic test が通る

## 3. Profile scaffolding

やること:
- `official-managed-lite`
- `official-hybrid-private`
- `full-private-self-host`
の mode/profile schema を実体化
- capability manifest と permission overlay を mode 単位で固定

Done:
- mode_id ごとに enabled_skills / connectors / permissions を切り替えられる
- env ではなく declarative profile が正本になる

## 4. Private-only migration

やること:
- official web app
- official app shell
- relay service runtime
- admin/commercial runtime
- ops/deploy/tunnel automation
を private repo 側の ownership に固定

Done:
- public 側から private module import が消える
- official surfaces が private runtime のみで成立する

## 5. Full-private-self-host

やること:
- official dependency なしで完結する public Node product を先に仕上げる
- local db, local web, owner-only shell, local files を完成させる

Done:
- self-host profile だけで product が起動する
- private repo が無くても主要フローが成立する

## 6. Hybrid

やること:
- optional relay
- optional official files/service dependency
- verified extension/install policy
を追加

Done:
- local-first で動きつつ、必要時だけ official services を使える
- cross-repo integration は contract のみ

## 7. Managed-lite hardening

やること:
- official-managed-lite の surface を最小化
- admin/dev gating を hardened
- commercial/ops/monitoring を private 側で閉じる

Done:
- managed-lite は最小 capability で運用できる
- official dependency が required の理由が明文化される

## Safest first extraction

最初に抜くべき slice は `src/skills/` の safe read skill 群。

理由:
- capability boundary が比較的明確
- UI/runtime ownership と分離しやすい
- relay/admin/official app の private 依存を持ち込みにくい
- synthetic request で安全に検証しやすい
