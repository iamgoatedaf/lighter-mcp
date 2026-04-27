# Homebrew formula for lighter-mcp.
#
# Live in a separate tap repository (e.g. ``iamgoatedaf/homebrew-tap``) so
# users can ``brew install iamgoatedaf/tap/lighter-mcp``. Keep this file in
# the main repo as the canonical source; the release workflow can sync it.
#
# Generating the resource list (one-time and after each minor version bump):
#
#     brew install pipx homebrew/core/python@3.12
#     pipx install homebrew-pypi-poet
#     poet -f lighter-mcp >> Formula/lighter-mcp.rb
#
# The ``resource`` blocks below are placeholders — fill them with the
# actual tarball URLs and SHA-256 checksums from PyPI before publishing.

class LighterMcp < Formula
  include Language::Python::Virtualenv

  desc "Safety-first MCP server exposing Lighter perpetual-DEX trading to AI agents"
  homepage "https://github.com/iamgoatedaf/lighter-mcp"
  url "https://files.pythonhosted.org/packages/source/l/lighter-mcp/lighter_mcp-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_REAL_SDIST_SHA256"
  license "MIT"
  head "https://github.com/iamgoatedaf/lighter-mcp.git", branch: "main"

  depends_on "python@3.12"

  # NOTE: regenerate via ``poet -f lighter-mcp`` after dependency bumps.
  resource "mcp" do
    url "https://files.pythonhosted.org/packages/source/m/mcp/mcp-1.2.0.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic/pydantic-2.6.0.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      lighter-mcp installed.

      Wire it into your agent (Cursor / Claude / Codex / Claude Desktop)
      and clone the upstream lighter-agent-kit with one command:

          lighter-mcp init

      The first run installs the kit at ~/.lighter/lighter-agent-kit and
      writes a default readonly config at ~/.lighter/lighter-mcp/config.toml.
      Live trading remains OFF until you edit that config explicitly.
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/lighter-mcp version")
    # ``init --no-install-kit --no-doctor --no-scaffolds`` is hermetic and
    # exercises detection + config generation against a fake kit path.
    fake_kit = testpath/"fake-kit"
    (fake_kit/"scripts").mkpath
    (fake_kit/"scripts/query.py").write("#!/usr/bin/env python3\nprint('{}')\n")
    system bin/"lighter-mcp", "init",
           "--kit-path", fake_kit,
           "--install-root", testpath/".lighter/lighter-mcp",
           "--no-install-kit",
           "--no-doctor",
           "--no-scaffolds",
           "--agents", "cursor"
    assert_predicate testpath/".lighter/lighter-mcp/config.toml", :exist?
  end
end
