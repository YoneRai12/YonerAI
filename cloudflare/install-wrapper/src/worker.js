const GITHUB_LATEST_BASE_URL =
  "https://github.com/YoneRai12/YonerAI/releases/latest/download";
const TRUSTED_INSTALL_SCRIPT_SHA256_BY_TAG = {
  "v0.8.1": "a52c3f918bd45e7fe87b7a396c80b879ede4bccdf16a7efdf05320388eaa9fea",
};
const TRUSTED_INSTALL_RELEASE_TAG = "v0.8.1";
const TRUSTED_INSTALL_SCRIPT_SHA256 =
  TRUSTED_INSTALL_SCRIPT_SHA256_BY_TAG[TRUSTED_INSTALL_RELEASE_TAG];

const INSTALL_WRAPPER = String.raw`$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$tag = "v0.8.1"
$expected = "a52c3f918bd45e7fe87b7a396c80b879ede4bccdf16a7efdf05320388eaa9fea"
$base = "https://github.com/YoneRai12/YonerAI/releases/download/$tag"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("yonerai-bootstrap-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
  $script = Join-Path $tmp "install.ps1"
  $sidecar = Join-Path $tmp "install.ps1.sha256"

  Invoke-RestMethod "$base/install.ps1" -OutFile $script
  Invoke-RestMethod "$base/install.ps1.sha256" -OutFile $sidecar

  $sidecarExpected = ((Get-Content -LiteralPath $sidecar -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($sidecarExpected -notmatch "^[a-f0-9]{64}$") {
    throw "install.ps1 sidecar SHA256 is invalid."
  }
  if ($sidecarExpected -ne $expected) {
    throw "install.ps1 sidecar does not match the trusted wrapper digest."
  }

  $actual = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) {
    throw "install.ps1 hash mismatch. Refusing to execute bootstrap."
  }

  $scriptText = Get-Content -LiteralPath $script -Raw
  if ($scriptText -notmatch "Invoke-VerifiedLocalBootstrap" -or $scriptText -match "install.ps1 is still plan-only") {
    throw "install.ps1 is not an executable bootstrap. Refusing to launch."
  }

  & (Get-Process -Id $PID).Path -NoProfile -ExecutionPolicy Bypass -File $script -Execute -Launch
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
  "The wrapper executes only the currently embedded trusted stable tag.",
  `Source: ${GITHUB_LATEST_BASE_URL}`,
  `Trusted tag: ${TRUSTED_INSTALL_RELEASE_TAG}`,
  `Trusted SHA256: ${TRUSTED_INSTALL_SCRIPT_SHA256}`,
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
