# Figma CN Maintenance Notes

## Scope

Maintain a runtime Chinese UI layer for the Figma desktop client. Keep the official Figma installation untouched.

## Verified Repair Order

1. Check whether Figma is running.
2. Check whether the CDP endpoint is reachable.
3. If not reachable, relaunch Figma with the test flag and a remote debugging port.
4. Rebuild the injector from `figmacn_content.js` and `figmacn_translations.json` when the source dictionary changes.
5. Inject into every page target and confirm translated DOM text appears.
6. If the UI structure changes, diagnose first, then refresh the source files and rebuild.

## Safety Rules

- Do not patch `app.asar` for normal maintenance.
- Do not overwrite the official Figma shortcut.
- Close the launcher-started process to return to stock behavior.

## Current Runtime Notes

- The launcher uses a local CDP port and `FIGMA_TEST=1` to keep the debugging port available.
- The launcher must allow remote origins when it connects to Chromium DevTools.
- The injector is rebuilt from the bundled figmaCN source files rather than edited in place.

## Troubleshooting Hints

- If the port is missing, relaunch Figma instead of editing the install.
- If text stops translating after a version change, regenerate `figmacn_inject.js` and re-run diagnosis.
- If the DOM no longer contains the expected text nodes, inspect the target pages first and then adjust the source translation files.
