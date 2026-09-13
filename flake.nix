{
  description = "Development shell for substack-exporter";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forEachSystem = nixpkgs.lib.genAttrs systems;
    in {
      devShells = forEachSystem (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (ps: with ps; [
            beautifulsoup4
            flask
            html2text
            markdown
            m3u8
            pytest
            requests
            selenium
            tqdm
          ]);
        in {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.chromium
              pkgs.chromedriver
            ];

            shellHook = ''
              export CHROME_BIN="''${CHROME_BIN:-${pkgs.chromium}/bin/chromium}"
              export CHROMEDRIVER="''${CHROMEDRIVER:-${pkgs.chromedriver}/bin/chromedriver}"
            '';
          };
        });
    };
}
