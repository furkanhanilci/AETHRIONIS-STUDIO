# Packaging AETHRIONIS Studio as a desktop application

Two ways to have it as a real window. The first works now.

## Today — app window, no build

```bash
./aethrionis-studio
```

Starts the application if it is not running, then opens it in a Chromium app
window: no address bar, no tabs, its own entry in the window list, the AETHRIONIS
appmark as its icon. A `.desktop` entry is installed, so it is also in the
application menu as **AETHRIONIS Studio**.

Not a packaged binary. It is a real window today rather than a browser tab
someone has to remember is special.

## The packaged build — WP-060

Blocked on one command, which needs a password only you have:

```bash
sudo apt-get install -y libwebkit2gtk-4.1-dev libgtk-3-dev \
                        libayatana-appindicator3-dev librsvg2-dev \
                        patchelf build-essential
```

Then, with no further input needed:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
cargo install tauri-cli --version '^2' --locked
cd src-tauri && cargo tauri build
```

Produces a `.deb` and an AppImage under `src-tauri/target/release/bundle/`.

**Note on the AppImage:** this host is glibc 2.35 and AppImages built against a
newer base will not run here. The `.deb` is the safer artefact on this machine.

### What is already prepared

- `src-tauri/tauri.conf.json` — window at the mockup's 1672×941, dark theme, and
  a content policy that admits only the local application
- `src-tauri/capabilities/default.json` — the narrowest capability set the shell
  can run on. Studio reads its data over localhost HTTP, so the window needs
  nothing from the operating system beyond being a window, and a capability
  granted because it might be useful later is one nobody remembers to remove
- `src-tauri/src/main.rs` — opens a window and does nothing else. A shell that
  grew its own logic would become a second place where the product behaves
- icons generated from the approved appmark

### Disk

Rust toolchain ~1.5 GiB, crate registry ~1 GiB, `target/` for this shell ~2–3
GiB. The root filesystem is at 91%; check before starting.
