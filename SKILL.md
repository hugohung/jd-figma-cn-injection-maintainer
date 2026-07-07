---
name: figma-cn-injection-maintainer
description: Maintain the Figma desktop Chinese UI injector by relaunching, diagnosing, rebuilding, or reapplying runtime injection when Figma menus, sidebars, right-click menus, or version changes break the translation layer. Use when the user asks to repair the Figma Chinese launcher, refresh the injector from figmaCN source files, recreate shortcuts, inspect CDP or FIGMA_TEST behavior, or restore Chinese UI after a Figma update.
---

# Figma CN Injection Maintainer

Maintain a non-destructive Chinese UI layer for the Figma desktop client. Keep the official Figma install untouched and repair the runtime injector instead of patching `app.asar`.

## Use Cases

- Relaunch the Chinese Figma helper after a restart.
- Diagnose why a new Figma version stopped translating menus or panels.
- Rebuild the injector when `figmaCN` translations change.
- Recreate desktop or Start menu shortcuts for the launcher.
- Verify that the current Figma page targets still accept CDP injection.

## Workflow

1. Check whether Figma is already running and whether the CDP port is open.
2. If CDP is not available, start Figma with the test flag and a remote debugging port.
3. Rebuild `figmacn_inject.js` from the bundled `figmacn_content.js` and `figmacn_translations.json` when translation data changes.
4. Inject into every Figma page target and verify that translated text appears in the DOM.
5. If the page structure changes, run the diagnosis script first, then refresh the bundled source files and rebuild.
6. Avoid permanent client changes. Close the launcher-started Figma process to return to stock behavior.

## Scripts

- `scripts/launch_figma_cn.py`: start or monitor Figma and keep the Chinese injector attached.
- `scripts/build_injector.py`: rebuild the standalone injector from the source translation bundle.
- `scripts/diagnose_figma_cn.py`: inspect Figma processes, CDP targets, and optional injection status.
- `scripts/install_shortcut.ps1`: create desktop and Start menu shortcuts for the launcher.

## References

- `references/figma-maintenance.md`: repair order, safety rules, and version-change notes.
- `references/figmacn_content.js`: the source injector logic copied from figmaCN.
- `references/figmacn_translations.json`: the translation dictionary used by the injector.
