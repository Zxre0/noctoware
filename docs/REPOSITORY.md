# The [noctoware] pacman repository

* Configured in `/etc/pacman.conf` via `/etc/pacman.d/noctoware-mirrorlist`
  (package `noctoware-mirrorlist`), signed by `noctoware-keyring`.
* `sudo pacman -Syu` updates Noctoware, CachyOS and Arch packages together.

## Hosting: GitHub Releases
One release (tag `repo-x86_64`, see `NOCTO_REPO_TAG`) holds a flat repo:
`noctoware.db`, `noctoware.files`, `*.pkg.tar.zst` and a `.sig` for each.
Server URL: `https://github.com/<owner>/<repo>/releases/download/repo-x86_64`.

Compatibility notes:
* pacman (libcurl) follows GitHub's 302 redirect to its asset CDN — works.
* Assets cannot be symlinks → `publish-repo.sh` uploads real `noctoware.db`
  / `noctoware.files` files.
* GitHub rewrites `:` in asset names → no epochs in Noctoware package
  versions (checked by `check-repo.sh` and `publish-repo.sh`).
* Per-asset limit 2 GiB; the largest package (`noctoware-hyde`) is ~55 MB.
* Uploads are not atomic: packages are uploaded first, the database last,
  and the previous package generation is kept for clients with a cached db.

## Publishing (controlled)
Only maintainers, only from `main`, only through the `release-repo` workflow
(manual dispatch, protected `release` environment with required reviewers).
It builds with the release key, runs all checks, simulates `pacman -Syu`
(`scripts/validate-update.sh`), publishes, then validates the live repo.
Pull requests run `ci.yml`, which has no access to secrets.

## Migrating hosting
Upload the same flat directory to any static HTTPS host (S3/R2/B2 bucket,
your own server) and change `NOCTO_REPO_URL` / the `Server =` line in
`noctoware-mirrorlist` (ship a new `noctoware-mirrorlist` package listing the
new server first and GitHub second during the transition). Signatures make
the host untrusted by design.
