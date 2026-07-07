from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFERENCES = ROOT.parent / "references"
SOURCE_JS = REFERENCES / "figmacn_content.js"
SOURCE_JSON = REFERENCES / "figmacn_translations.json"
OUTPUT = ROOT / "figmacn_inject.js"


def main() -> int:
    content = SOURCE_JS.read_text(encoding="utf-8")
    translations = SOURCE_JSON.read_text(encoding="utf-8")

    content = content.replace("loadTranslationData();", "initializeTranslation(allData);")

    output = f"""(() => {{
  if (window.__codexFigmaCNInjected) {{
    return {{ ok: true, alreadyInjected: true, title: document.title, url: location.href }};
  }}
  window.__codexFigmaCNInjected = true;
  const allData = {translations};
{content}
  return {{ ok: true, alreadyInjected: false, entries: allData.length, title: document.title, url: location.href }};
}})();
"""

    OUTPUT.write_text(output, encoding="utf-8")
    print(str(OUTPUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
