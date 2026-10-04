# Unofficial Herdr OpenCode V2 background-status workaround

Keeps Herdr's yellow working circle active while the selected OpenCode session
has running background subagents. Parent completion no longer reports idle until
the remaining descendants settle. Pending permissions/forms still take precedence.

Related upstream report:
https://github.com/herdrdev/herdr/issues/4511

This is a **local, unofficial workaround**, not an upstream contribution or
release. It changes only the dependency-free terminal integration asset, not the
Herdr binary, socket protocol, OpenCode server plugin, or CLI configuration.

## Compatibility

Tested with Herdr **0.9.3**, integration **13**, and OpenCode **2.0.21** on Linux.
The installer accepts only the exact reviewed stock plugin or the exact patched
copy. It refuses unknown upstream versions, custom edits, and symlinks.

The upstream migration marker stays unchanged: this workaround must not pretend
to be a newer official integration or prevent Herdr from installing a future one.

## Check, install, and undo

Download the bundle, then inspect the patch and installer before applying it:

```sh
git clone https://github.com/brijmcq/herdr-opencode-v2-fix.git
cd herdr-opencode-v2-fix
```

```sh
python3 manage.py
python3 manage.py --apply
```

Checking makes no changes. Applying creates a private, exact backup and replaces
the plugin atomically while preserving its file permissions. The helper prints
the backup path and a matching restore command:

```sh
python3 manage.py --restore /path/to/herdr-tui-session.js.backup
```

Use `--target /path/to/herdr-tui-session.js` for a non-default OpenCode config
directory. Otherwise the helper honors `XDG_CONFIG_HOME`.

Relaunch affected OpenCode terminals when convenient. Existing terminal plugin
instances may not have reloaded. **Do not stop the Herdr server**, since that also
stops its panes.

## Keep receiving upstream updates

Upgrade Herdr and its official integration normally. Herdr's updater,
integration installer, or dotfile restore (such as chezmoi) may overwrite this
local workaround. After an update or restore,
run `python3 manage.py` before using `--apply` again.

- If the official plugin is still the exact reviewed version, reapplication is safe.
- If the plugin changed, the helper stops without overwriting it. Review/rebase
  the patch and repeat the regression tests before supporting that version.
- If an official fix is released, keep the official plugin and retire this bundle.

This does not pin or fork the Herdr binary. It deliberately does not hook into
updates or silently override new upstream code.

## Tests and evidence

```sh
python3 -m unittest test_manage.py
node regression.mjs
```

With Bun installed, the complete terminal-plugin suite is also available:

```sh
bun test herdr-tui-session.test.ts
```

`ci-tests.yml.example` is an optional GitHub Actions template. Copy it to
`.github/workflows/tests.yml` when using credentials with workflow permission.

The source checkout includes ten new V2 regression tests covering background
completion, multiple descendants, attachment, delayed caches, deletion,
permission precedence, and selection isolation. All **65 integration-asset tests**
passed; nine new tests failed against the original implementation before fixing it.

The patched Herdr source checkout also passed its complete native Linux
`just test` recipe using Rust **1.96.1**, Zig **0.16.0**, and cargo-nextest **0.9.146**:

- **3,903 Rust tests passed; 14 skipped** by the normal test configuration.
- **150 Python maintenance tests** and **6 architecture tests** passed.
- **5 release-workflow tests**, **65 integration-asset tests**, and
  **7 documentation-contract tests** passed.

No Rust or protocol code was changed. Windows cross-compilation and lint checks
were not run.

A native test used the real Herdr/OpenCode binaries, a real OpenCode background
subagent, and a deterministic loopback test provider. The Agents panel showed a
yellow `● working` (`#f9e2af`) after the parent finished and returned to idle after
the child completed. A second terminal attached during the background work also
reported working. No external model calls were used for that successful test.

## Sharing

The bundle can be shared in your own repository or gist under the included
Apache-2.0 license, retaining its upstream attribution. Clearly label it unofficial
and document its supported versions. Do not submit an unsolicited Herdr PR or
paste the patch/implementation plan into the upstream issue; follow Herdr's
contribution policy.

Upstream source and license attribution are recorded in `manifest.json`.
