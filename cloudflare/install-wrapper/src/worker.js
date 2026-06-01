const TRUSTED_INSTALL_SCRIPT_URL =
  "https://raw.githubusercontent.com/YoneRai12/YonerAI/62ca47c792f7eae693f9346a8cc34fadc17b8c31/install.ps1";
const TRUSTED_INSTALL_SCRIPT_SHA256 =
  "e2990bd0cbc35da35388f7338246ca6eaba557f4990606a25bd127c64bc1ba03";

const INSTALL_WRAPPER = String.raw`$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$url = "https://raw.githubusercontent.com/YoneRai12/YonerAI/62ca47c792f7eae693f9346a8cc34fadc17b8c31/install.ps1"
$expected = "e2990bd0cbc35da35388f7338246ca6eaba557f4990606a25bd127c64bc1ba03"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("yonerai-bootstrap-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
  $script = Join-Path $tmp "install.ps1"

  Invoke-RestMethod $url -OutFile $script

  $actual = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) {
    throw "install.ps1 hash mismatch. Refusing to execute bootstrap."
  }

  $scriptText = Get-Content -LiteralPath $script -Raw
  if ($scriptText -notmatch "Installer skeleton" -or $scriptText -notmatch "install.ps1 is still plan-only") {
    throw "install.ps1 is not the expected plan-only bootstrap. Refusing to launch."
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
  "Installer bootstrap is fetched from the pinned trusted source below; release assets are not served by install.yonerai.com.",
  `Source: ${TRUSTED_INSTALL_SCRIPT_URL}`,
  `SHA256: ${TRUSTED_INSTALL_SCRIPT_SHA256}`,
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
