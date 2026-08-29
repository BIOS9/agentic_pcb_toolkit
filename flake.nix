{
  description = "pcbkit — agent-driven PCB design toolkit";

  # Pinned by revision in flake.lock, never by name. On this machine the
  # nixpkgs *channel* provides KiCad 9.0.7 while the nixpkgs *flake* provides
  # 10.0.5: two references that both look like "nixpkgs" already disagree by a
  # major version, and pcbkit's file-format pins depend on which one wins.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forEach = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # Everything pcbkit needs from outside itself.
      toolsFor = pkgs: with pkgs; [ kicad ngspice jre freerouting python314 uv git ];

      # Consumed by pcbkit/core/toolchain.py. Defined once and shared by the
      # devShell and the check apps: `nix run` does not enter a devShell, so
      # duplicating this is how CI ends up unpinned while claiming otherwise.
      envFor = pkgs: {
        PCBKIT_TOOLCHAIN = "nix";
        PCBKIT_KICAD_SYMBOLS = "${pkgs.kicad.libraries.symbols}/share/kicad/symbols";
        PCBKIT_KICAD_FOOTPRINTS = "${pkgs.kicad.libraries.footprints}/share/kicad/footprints";
        PCBKIT_KICAD_3DMODELS = "${pkgs.kicad.libraries.packages3d}/share/kicad/3dmodels";
        PCBKIT_KICAD_TEMPLATES = "${pkgs.kicad.libraries.templates}/share/kicad/template";
      };

      exportsFor = pkgs:
        nixpkgs.lib.concatStringsSep "\n"
          (nixpkgs.lib.mapAttrsToList (k: v: ''export ${k}="${v}"'') (envFor pkgs));

      # pcbnew is a C++ extension, not a pip package, so no venv can import it.
      # Nix puts it in kicad-base's site-packages rather than on any
      # interpreter's default path, so name both explicitly: guessing a
      # `kicad-python3` wrapper silently fell back to a python without the
      # bindings, and doctor reported the environment broken.
      pcbnewExport = pkgs: ''
        export PCBKIT_PCBNEW_PYTHON="${pkgs.python314}/bin/python3"
        export PCBKIT_PCBNEW_PYTHONPATH="${pkgs.kicad.base}/${pkgs.python314.sitePackages}"
      '';
    in
    {
      devShells = forEach (pkgs: {
        default = pkgs.mkShell ({
          packages = toolsFor pkgs;
          shellHook = ''
            ${pcbnewExport pkgs}
            echo "pcbkit devshell — kicad ${pkgs.kicad.version}, python ${pkgs.python314.version}"
          '';
        } // envFor pkgs);
      });

      apps = forEach (pkgs:
        let
          # One definition of "the checks", run identically by a developer and
          # by CI. A second copy in workflow YAML would be a second source of
          # truth and would drift, which is the failure CR-004 names.
          app = name: body: pkgs.writeShellApplication {
            inherit name;
            runtimeInputs = toolsFor pkgs;
            text = ''
              ${exportsFor pkgs}
              ${pcbnewExport pkgs}
              ${body}
            '';
          };
          checks = app "pcbkit-checks" ''
            uv sync --frozen
            uv run pytest -q
            # Both gates: --strict is health, --require-pinned is provenance.
            # --require-pinned alone passed on an environment whose pcbnew was
            # broken, which would have let CI go green on a dead toolchain.
            uv run pcbkit doctor --strict --require-pinned --text
          '';
          licences = app "pcbkit-licences" ''
            uv sync --frozen
            uv run pcbkit licences --strict --text
          '';
        in
        {
          checks = { type = "app"; program = "${checks}/bin/pcbkit-checks"; };
          licences = { type = "app"; program = "${licences}/bin/pcbkit-licences"; };
        });

      formatter = forEach (pkgs: pkgs.nixpkgs-fmt);
    };
}
