# Legacy HUD backup

To restore this UI, copy the files from this folder over `../hud/` (from the `dinesh/` directory):

```bash
cd "$(dirname "$0")/.."
cp -R hud_v1_backup/index.html hud_v1_backup/style.css hud_v1_backup/app.js \
      hud_v1_backup/reactor.js hud_v1_backup/space.js hud/ 2>/dev/null || true
```

Prefer the current HUD unless you intentionally want the older layout.
