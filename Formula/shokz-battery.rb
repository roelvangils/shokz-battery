class ShokzBattery < Formula
  desc "Check your Shokz headset battery level from the command line"
  homepage "https://github.com/roelvangils/shokz-battery"
  url "https://github.com/roelvangils/shokz-battery/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "604aa2348bb36edb4efdbb51edc9c4206e95275ee01f0106f5d609bf1b1b20bc"
  license "MIT"

  depends_on :macos

  def install
    bin.install "shokz-battery.py" => "shokz-battery"
  end

  test do
    # Just test that the script runs (will fail without Shokz Connect logs, but that's OK)
    system "#{bin}/shokz-battery", "--version"
  end
end
