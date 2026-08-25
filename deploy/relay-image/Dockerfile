# The AETHRION relay: our own binary, in the runtime the upstream image uses.
#
# Upstream's Dockerfile compiles the relay inside the build, which takes the
# better part of an hour on this host and recompiles the whole workspace for
# every change. The binary is already built from `crates/buzz-relay` by the
# ordinary `cargo build --release`, so this image only assembles it.
#
# The base, the entrypoint, the working directory and the user match the image
# this replaces, so nothing else in the deployment has to change: same volumes,
# same env, same network. What changes is who compiled the binary.
#
# `git` is required — the relay shells out to it for repo hydrate, receive-pack
# and upload-pack (crates/buzz-relay/src/api/git). Removing it does not fail at
# boot; it fails the first time somebody pushes.
FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git libssl3 \
 && rm -rf /var/lib/apt/lists/*

# uid/gid 1000, pinned, because the git data volume is already owned by 1000 —
# it was written by the image this replaces. `--system` picks from the low range
# and gave 999, so the relay connected to everything, migrated the database, and
# then panicked creating a pack-cache directory it could not write. Nothing in
# the failure named a uid; it said "Permission denied" on a path.
RUN groupadd --gid 1000 buzz \
 && useradd --uid 1000 --gid 1000 --home /var/lib/buzz --no-create-home buzz \
 && mkdir -p /var/lib/buzz && chown buzz:buzz /var/lib/buzz

COPY buzz-relay /usr/local/bin/buzz-relay
RUN chmod 0755 /usr/local/bin/buzz-relay

# The invite landing page. `https://<relay>/invite/<code>` is the canonical
# share link — the form a phone follows — and the relay serves it from
# BUZZ_WEB_DIR. Leaving it out did not fail at boot: the route found nothing to
# serve, fell through to the git handler, and answered every invite with
# "internal endpoint: localhost only". An invite that 403s reads as a broken
# invite, not a missing bundle.
COPY web /srv/aethrion/web
ENV BUZZ_WEB_DIR=/srv/aethrion/web

USER buzz:buzz
WORKDIR /var/lib/buzz
ENTRYPOINT ["/usr/local/bin/buzz-relay"]
