{
  description = "AVream (Android webcam/mic bridge for Linux)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";

  outputs = { self, nixpkgs }:
    let
      lib = nixpkgs.lib;
      systems = [ "x86_64-linux" ];
      forAllSystems = f: lib.genAttrs systems (system: f system);
    in {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          pythonEnv = pkgs.python3.withPackages (ps: with ps; [ aiohttp pygobject3 ]);
          version = lib.strings.removeSuffix "\n" (builtins.readFile ./src/avreamd/VERSION);
          helper = pkgs.rustPlatform.buildRustPackage {
            pname = "avream-helper";
            inherit version;
            src = ./helper;
            cargoLock.lockFile = ./helper/Cargo.lock;
          };
        in {
          avream = pkgs.stdenv.mkDerivation {
            pname = "avream";
            inherit version;
            src = ./.;

            nativeBuildInputs = [ pkgs.makeWrapper ];
            buildInputs = [ pythonEnv pkgs.gtk4 pkgs.libadwaita pkgs.polkit ];

            dontConfigure = true;

            buildPhase = ''
              runHook preBuild
              bash scripts/generate-dist-docs.sh
              runHook postBuild
            '';

            installPhase = ''
              runHook preInstall

              install -D -m0644 packaging/systemd/user/avreamd.service $out/lib/systemd/user/avreamd.service
              install -D -m0644 packaging/systemd/user/avreamd.env $out/lib/systemd/user/avreamd.env
              install -D -m0644 packaging/polkit/io.avream.helper.policy $out/share/polkit-1/actions/io.avream.helper.policy
              install -D -m0644 packaging/desktop/io.avream.AVream.desktop $out/share/applications/io.avream.AVream.desktop
              install -D -m0644 packaging/desktop/io.avream.AVream.appdata.xml $out/share/metainfo/io.avream.AVream.appdata.xml
              install -D -m0644 packaging/desktop/io.avream.AVream.svg $out/share/icons/hicolor/scalable/apps/io.avream.AVream.svg
              install -D -m0644 dist/README_USER.md $out/share/doc/avream/README_USER.md
              install -D -m0644 dist/CLI_README.md $out/share/doc/avream/CLI_README.md
              install -D -m0755 ${helper}/bin/avream-helper $out/libexec/avream-helper
              install -D -m0755 scripts/avream-passwordless-setup.sh $out/bin/avream-passwordless-setup

              mkdir -p $out/lib/avream/python
              cp -r src/avreamd $out/lib/avream/python/
              cp -r ui/src/avream_ui $out/lib/avream/python/

              makeWrapper ${pythonEnv}/bin/python3 $out/bin/avreamd \
                --set PYTHONPATH "$out/lib/avream/python" \
                --add-flags "-m" --add-flags "avreamd.main"

              makeWrapper ${pythonEnv}/bin/python3 $out/bin/avream \
                --set PYTHONPATH "$out/lib/avream/python" \
                --add-flags "-m" --add-flags "avreamd.cli"

              makeWrapper ${pythonEnv}/bin/python3 $out/bin/avream-ui \
                --set PYTHONPATH "$out/lib/avream/python" \
                --add-flags "-m" --add-flags "avream_ui.main"

              runHook postInstall
            '';

            meta = with lib; {
              description = "Use your Android phone as webcam and microphone on Linux";
              homepage = "https://github.com/Kacoze/avream";
              license = licenses.mit;
              platforms = [ "x86_64-linux" ];
            };
          };

          default = self.packages.${system}.avream;
        }
      );

      checks = forAllSystems (system: {
        avream = self.packages.${system}.avream;
      });

      apps = forAllSystems (system: {
        avream = {
          type = "app";
          program = "${self.packages.${system}.avream}/bin/avream";
        };
        avreamd = {
          type = "app";
          program = "${self.packages.${system}.avream}/bin/avreamd";
        };
        avream-ui = {
          type = "app";
          program = "${self.packages.${system}.avream}/bin/avream-ui";
        };
      });

      defaultPackage = forAllSystems (system: self.packages.${system}.avream);
    };
}
