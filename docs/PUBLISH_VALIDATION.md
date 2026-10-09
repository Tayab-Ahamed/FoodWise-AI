# GitHub publication verification

Executed on Windows on 9 October 2026, before the first push to `Tayab-Ahamed/FoodWise-AI`.

| Check | Actual result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest backend/tests -q` | **163 passed**, 1 existing dependency warning, **16.08 s**; exit 0. |
| `npm.cmd run typecheck` in `frontend/` | **Passed**; exit 0. |
| `npm.cmd run build` in `frontend/` | **Passed**; Vite **6.4.4**, **2,190 modules**, **20.21 s**; exit 0. |
| Publication preflight | **105 staged files**, six screenshots, **34 README file references** resolved to published files; no local credential values or recognized key patterns found. Local databases, environments, dependencies, and render artifacts excluded. |
| Staged whitespace check | `git diff --cached --check` **passed** after removing one trailing blank line from the relocated guide. |

The dependency warning is Starlette TestClient's existing deprecation of the httpx adapter; no domain assertion failed. Tests use isolated temporary SQLite databases. Application behavior and dependency versions were not changed for publication.

## Earlier browser and video verification

The publication README reuses actual browser captures, copied intact into `docs/screenshots/`. The servers remain stopped as requested; they were not restarted for documentation work. See the screenshot README for capture context.

The connected video scenario previously passed 16 local assertions. Its 213.375-second, 1920×1080 H.264/AAC render passed full decoding, frame/caption/poster verification, and browser playback/chapter seeking. These are prior video checks, not checks rerun for this publication. Generated video projects and local render dependencies are excluded from Git.

Provider calls are not part of this publication check. Earlier live provider results are recorded in [AI Kitchen Advisor validation](AI_KITCHEN_ADVISOR.md).

## Publication boundaries

The README's badges record the local checks above; they do not claim continuous integration or a hosted deployment. The project has no selected license. Credentials, SQLite databases, dependency directories, generated artifacts, and local font/video assets are excluded from the published source.
