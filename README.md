# claude-plugins

Personal [Claude Code](https://code.claude.com) plugin marketplace.

## Install

```
/plugin marketplace add Weili-0234/claude-plugins
/plugin install mlsys-code-walkthrough@weili-claude-plugins
```

## Plugins

| Plugin | What it does |
|---|---|
| [mlsys-code-walkthrough](./mlsys-code-walkthrough) | Skill for writing rigorous ML-systems code walk-through tutorials (Awesome-ML-SYS-Tutorial style): trace the key data structures through one lifecycle — which function touches which structure, tagged Allocate / Write / Update / Free — grounded in commit-pinned permalinks, with mermaid data-flow diagrams and programmatically-authored Excalidraw hero figures (generator kit + render + self-check loop included). |

## Layout

```
.claude-plugin/marketplace.json        # marketplace manifest
mlsys-code-walkthrough/
  .claude-plugin/plugin.json           # plugin manifest
  skills/mlsys-code-walkthrough/
    SKILL.md                           # entry point: the method (six steps) + cardinal rules
    references/                        # per-topic deep dives, loaded on demand
      data-structures.md               #   Shape/Access/Value format, cross-linking via shared indices
      lifecycle-tracing.md             #   the core method: function -> mutation tracing
      diagrams.md                      #   mermaid conventions and templates
      excalidraw-plots.md              #   drawn hero figures: visual grammar, render, self-check
      narrative-and-format.md          #   concept->model->code ordering, bilingual titles, self-check
      finding-the-code.md              #   repo analysis recipes, commit pinning, permalinks
    templates/
      walkthrough-skeleton.md          #   article skeleton to copy
      excalidraw_kit.py                #   element builders for .excalidraw scenes
```
