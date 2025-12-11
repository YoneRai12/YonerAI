# Google 連携セットアップガイド

ORA Bot で Google ログインと Google Drive 連携を使用するための設定手順です。

## 1. Google Cloud Console でのプロジェクト作成

1.  [Google Cloud Console](https://console.cloud.google.com/) にアクセスします。
2.  新しいプロジェクトを作成します（例: `ORA-Discord-Bot`）。

## 2. API の有効化

1.  左メニューの「API とサービス」>「ライブラリ」を選択します。
2.  以下の API を検索して**有効化**します。
    *   **Google Drive API** (画像の保存に使用)
    *   **Cloud Vision API** (画像の物体・人物認識に使用)

## 3. OAuth 同意画面の設定

1.  左メニューの「API とサービス」>「OAuth 同意画面」を選択します。
2.  User Type は「**外部 (External)**」を選択して「作成」をクリックします。
3.  **アプリ情報**:
    *   アプリ名: `ORA Bot` など
    *   ユーザーサポートメール: 自分のメールアドレス
4.  **デベロッパーの連絡先情報**: 自分のメールアドレス
5.  「保存して次へ」をクリックします。
6.  **スコープ**:
    *   「スコープを追加または削除」をクリック。
    *   以下のスコープを選択して追加します：
        *   `.../auth/userinfo.email`
        *   `.../auth/userinfo.profile`
        *   `openid`
        *   `.../auth/drive.file` (Google Drive API を有効化すると表示されます)
    *   「保存して次へ」をクリックします。
7.  **テストユーザー**:
    *   「ADD USERS」をクリックし、自分の Google アカウント（メールアドレス）を追加します。
    *   ※これをしないと、認証時に「このアプリは Google で確認されていません」と表示され、ログインできない場合があります。

## 4. 認証情報 (Client ID / Secret) の作成

1.  左メニューの「API とサービス」>「認証情報」を選択します。
2.  「認証情報を作成」>「**OAuth クライアント ID**」を選択します。
3.  **アプリケーションの種類**: 「**ウェブ アプリケーション**」を選択。
4.  **名前**: `ORA Web Auth` など。
5.  **承認済みのリダイレクト URI**:
    *   「URI を追加」をクリック。
    *   Bot を動かしている環境の URL を入力します。
    *   ローカルで動かす場合: `http://localhost:8000/auth/discord`
    *   本番環境の場合: `https://your-domain.com/auth/discord`
6.  「作成」をクリックします。
7.  **クライアント ID** と **クライアント シークレット** が表示されるので、コピーします。

## 5. Cloud Vision API 用のサービスアカウント設定

画像認識機能（Vision API）を使用するには、サービスアカウントキーが必要です。

1.  左メニューの「IAM と管理」>「**サービスアカウント**」を選択します。
2.  「**サービスアカウントを作成**」をクリックします。
3.  **サービスアカウント名**: `ora-vision-sa` など。
4.  「作成して続行」をクリック。
5.  **ロール**: 「**Cloud Vision API ユーザー**」を選択して「続行」>「完了」。
6.  作成されたサービスアカウントをクリックし、「**キー**」タブを開きます。
7.  「**鍵を追加**」>「**新しい鍵を作成**」を選択します。
8.  キーのタイプで「**JSON**」を選択し、「作成」をクリックします。
9.  JSONファイルが自動的にダウンロードされます。
10. このファイルを Bot のプロジェクトフォルダ（`src` フォルダと同じ階層）に配置し、名前を `service-account.json` に変更します（または任意の名前）。

## 6. 環境変数の設定

`.env` ファイルに以下の情報を追記・確認してください。

```env
# Google Auth (ユーザー連携用)
GOOGLE_CLIENT_ID=あなたのクライアントID
GOOGLE_CLIENT_SECRET=あなたのクライアントシークレット
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/discord

# Google Cloud Vision (画像認識用)
GOOGLE_APPLICATION_CREDENTIALS=service-account.json
```

※ `GOOGLE_APPLICATION_CREDENTIALS` には、先ほど配置した JSON ファイルのパス（相対パスまたは絶対パス）を指定します。

