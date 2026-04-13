# AGENTS.md

## Purpose
This repo stores **project JSON manifests** that define:
- which ComfyUI custom node repos to install
- which model/data files to download

Each manifest follows this structure:
- `custom_nodes`: array of `{ "repo_dir", "repo" }`
- `files`: array of `{ "url", "target" }`

## File naming convention
Use a clear, versioned filename:
- `<project-name>-v<version>.json`
- `<project-name>-v<version>.files.json` (optional variant if you want to emphasize file manifests)

Examples:
- `avatary-image-generator-v1.json`
- `seedvr2-image-upscaler-v1.files.json`

## Manifest schema

```json
{
  "custom_nodes": [
    {
      "repo_dir": "ComfyUI-ExampleNode",
      "repo": "https://github.com/example/ComfyUI-ExampleNode.git"
    }
  ],
  "files": [
    {
      "url": "https://huggingface.co/org/repo/resolve/main/model.safetensors",
      "target": "models/checkpoints/model.safetensors"
    }
  ]
}
```

## How to create a new project JSON
1. Copy an existing manifest as a starting point.
2. Rename it to the new project name and version.
3. Update `custom_nodes`:
   - `repo_dir`: target directory name under ComfyUI custom nodes.
   - `repo`: full git URL (prefer `.git` form for consistency).
4. Update `files`:
   - `url`: direct downloadable URL.
   - `target`: destination path relative to the ComfyUI root.
5. Remove any entries not required for the new project.
6. Keep arrays ordered logically (core dependencies first).

## Authoring rules
- Keep valid JSON (no trailing commas, double quotes only).
- Use 2-space indentation.
- Keep paths case-sensitive and consistent with ComfyUI folders.
- Prefer unique `repo_dir` values.
- If using `import_projects`, do not duplicate dependencies already provided by imported manifests.
  - No overlap on `custom_nodes.repo_dir`.
  - No overlap on `files.target`.
- Prefer pinned/controlled file URLs that won’t move unexpectedly.

## Placeholders for unknown dependencies
If a workflow references a custom node repo or file that you cannot resolve yet, **keep it in the manifest as a placeholder** (do not omit it).

Use this format:

```json
{
  "repo_dir": "TODO-<expected-folder-name>",
  "repo": "TODO_REPO_URL_FOR_<NODE_NAME>"
}
```

```json
{
  "url": "TODO_URL_FOR_<filename>",
  "target": "models/<folder>/<filename>"
}
```

Placeholder rules:
- Prefix unknown custom node directories with `TODO-`.
- Prefix unknown repo URLs with `TODO_REPO_URL_FOR_`.
- Prefix unknown file URLs with `TODO_URL_FOR_`.
- Keep the `target` path real and final, even when the URL is unknown.
- Replace placeholders as soon as real sources are confirmed.

## Quick validation
Run these checks after editing:

```bash
jq . <manifest-file>.json
```

Validate all manifests in this repo:

```bash
for f in *.json; do echo "Checking $f"; jq . "$f" >/dev/null; done
```

## Change checklist
Before committing a new/updated manifest:
- JSON parses with `jq`
- unresolved dependencies are explicitly listed as `TODO_*` placeholders
- when `import_projects` is present, added `custom_nodes.repo_dir` and `files.target` do not overlap imported manifests
- all non-placeholder `repo` URLs are reachable
- all non-placeholder `url` download links are correct
- all `target` paths are intentional
- filename includes a version
