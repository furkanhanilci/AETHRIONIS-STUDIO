# Building AETHRIONIS Studio

Two things about this build are not guessable from the source, and both cost a
working day to find once.

## The frontend must be built before the binary

```bash
cd app
npm run build          # produces app/dist
npx tauri build --no-bundle
```

`app/src-tauri/build.rs` carries `cargo:rerun-if-changed=../dist`. Without it
cargo does not relink when only the frontend changed, and the build reports
success while shipping the previous interface. That happened four times before
the line existed; if a change you can see in `dist` is not in the running
application, this is the first thing to check.

## System libraries can come from a local sysroot

On a machine with `libasound2-dev`, `libopus-dev`, `libpulse-dev` and
`libxdo-dev` installed, `npx tauri build` is enough and this section does not
apply.

The host this was developed on has no `sudo`, so those packages are extracted
into `.sysroot/` instead. It is **not** in the repository — the headers belong
to those packages, not to this project. Recreate it by extracting the four
`.deb`s into `.sysroot/`, then:

```bash
SR="$PWD/../.sysroot"          # from app/
env PATH="$HOME/.cargo/bin:$PATH" \
    PKG_CONFIG_PATH="$SR/usr/lib/x86_64-linux-gnu/pkgconfig" \
    LIBRARY_PATH="$SR/usr/lib/x86_64-linux-gnu" \
    npx tauri build --no-bundle
```

`PKG_CONFIG_SYSROOT_DIR` must **not** be set. The `.pc` files in the sysroot
already carry absolute paths; setting it prefixes them a second time, producing
`.sysroot/home/.../.sysroot/...` and a linker that cannot find `-lopus`.

## The relay binary is not committed

`deploy/relay-image/Dockerfile` copies a `buzz-relay` executable that is not in
the repository: it is 64 MB, git cannot delta-compress it, and every clone would
pay for it forever. Build it from `crates/buzz-relay`, which is here, and place
the result next to the Dockerfile.

## Where this came from

A fork of [Buzz](https://github.com/block/buzz) at commit `0720f538`, Apache-2.0.
`LICENSE-APACHE-2.0-buzz` and `NOTICE` are kept alongside the code they cover.
