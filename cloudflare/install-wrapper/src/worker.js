const GITHUB_LATEST_BASE_URL =
  "https://github.com/YoneRai12/YonerAI/releases/latest/download";

const INSTALL_WRAPPER = String.raw`$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$base = "https://github.com/YoneRai12/YonerAI/releases/latest/download"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("yonerai-bootstrap-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
  $script = Join-Path $tmp "install.ps1"
  $sidecar = Join-Path $tmp "install.ps1.sha256"

  Invoke-RestMethod "$base/install.ps1" -OutFile $script
  Invoke-RestMethod "$base/install.ps1.sha256" -OutFile $sidecar

  $expected = ((Get-Content -LiteralPath $sidecar -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($expected -notmatch "^[a-f0-9]{64}$") {
    throw "install.ps1 sidecar SHA256 is invalid."
  }

  $actual = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) {
    throw "install.ps1 hash mismatch. Refusing to execute bootstrap."
  }

  $scriptText = Get-Content -LiteralPath $script -Raw
  if ($scriptText -notmatch "Invoke-VerifiedLocalBootstrap" -or $scriptText -match "install.ps1 is still plan-only") {
    throw "install.ps1 is not an executable bootstrap. Refusing to launch."
  }

  & powershell -NoProfile -ExecutionPolicy Bypass -File $script -Execute -Launch
}
finally {
  if (Test-Path -LiteralPath $tmp) {
    Remove-Item -LiteralPath $tmp -Recurse -Force
  }
}
`;

const TEXT_HEADERS = {
  "content-type": "text/plain; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

const NOT_FOUND_TEXT = [
  "YonerAI installer wrapper only.",
  "Installer assets are served by GitHub Releases, not install.yonerai.com.",
  `Source: ${GITHUB_LATEST_BASE_URL}`,
  "",
].join("\n");

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("method not allowed\n", {
        status: 405,
        headers: { ...TEXT_HEADERS, allow: "GET, HEAD" },
      });
    }
    if (url.pathname === "/") {
      return new Response(request.method === "HEAD" ? null : INSTALL_WRAPPER, {
        status: 200,
        headers: TEXT_HEADERS,
      });
    }
    return new Response(request.method === "HEAD" ? null : NOT_FOUND_TEXT, {
      status: 404,
      headers: TEXT_HEADERS,
    });
  },
};
