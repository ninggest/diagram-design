<div align="center">

<h1>
  diagram-design, with an editable draw.io export
</h1>

**An agent skill that draws diagrams as one self-contained HTML + SVG file, in your brand —<br>and now exports them to a real, editable draw.io shape graph.<br>45 diagram types. No shadows. No Mermaid slop.**

[![Upstream stars](https://img.shields.io/github/stars/cathrynlavery/diagram-design?style=flat-square&color=bf4520)](https://github.com/cathrynlavery/diagram-design/stargazers)
[![skills.sh installs](https://skills.sh/b/cathrynlavery/diagram-design?type=install)](https://skills.sh/c/cathrynlavery/diagram-design/diagram-design)
[![MIT license](https://img.shields.io/badge/license-MIT-555555)](LICENSE)

**[Gallery](https://cathrynlavery.github.io/diagram-design/) · [Changelog](CHANGELOG.md) · [Cookbook](docs/cookbook.md)**

This is a fork of [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) (MIT).
Everything upstream does, it still does — and it tracks upstream. This fork adds one
thing: **a `.drawio` export that carries the relationships SVG cannot.** See
[Provenance and license](#provenance-and-license) for exactly what changed.

</div>

<br>

## What this fork adds

SVG records geometry, not relationships. A `<path>` knows it was drawn from A's right
edge to B's bottom edge, but not that A is the *source* and B the *target*, nor which
shapes belong together. draw.io and Visio need exactly that missing layer — a shape
graph whose connectors are glued to the shapes they join — so a plain SVG round-trip
degrades into loose shapes and dead lines.

The `--drawio` export rebuilds that layer from a contract the skill already
guarantees: **a connector's endpoints sit on the borders of the shapes they join.**
Matching a path's first and last point against the node rectangles recovers who
connects to whom, plus the attach fractions that keep a connector glued when you
drag its shapes.

Three more relationships fall out of the same pass:

- **A swimlane band becomes a container.** A step dragged into a lane belongs to it,
  and moving the lane moves its steps.
- **A caption becomes a child of the step it captions.** Drag the step and the
  caption travels with it instead of stranding.
- **A filled band becomes a polygon shape.** A Sankey ribbon is an object with
  editable vertices, not a picture.

What you get is a live document in draw.io: pick up a box and the arrows follow it.

| | upstream | this fork |
|---|---|---|
| Output | one HTML file with inline SVG | the same, plus an editable `.drawio` |
| Change it later | ask the agent again, or edit the SVG | …or export to draw.io and drag the boxes |
| A swimlane | hairlines on a canvas | a container whose steps belong to it |
| A caption | floating text | a child of the step it captions |

## Install

Works with any host that reads Agent Skills — Cursor, Claude Code, Codex, Qoder, GitHub
Copilot, Gemini CLI, Cline, Windsurf, Amp:

```bash
npx skills add ninggest/diagram-design        # this fork
npx skills add cathrynlavery/diagram-design  # upstream
```

In Claude Code, the plugin marketplace gets you updates and the slash commands:

```text
/plugin marketplace add cathrynlavery/diagram-design
/plugin install diagram-design@diagram-design
```

<details>
<summary><b>Codex</b></summary>

```bash
codex plugin marketplace add cathrynlavery/diagram-design
codex plugin add diagram-design@diagram-design
```

</details>

<details>
<summary><b>GitHub Copilot</b></summary>

```bash
copilot plugin marketplace add cathrynlavery/diagram-design
copilot plugin install diagram-design@diagram-design
```

</details>

<details>
<summary><b>Factory (Droid)</b></summary>

```bash
droid plugin marketplace add https://github.com/cathrynlavery/diagram-design
droid plugin install diagram-design@diagram-design --scope user
```

</details>

<details>
<summary><b>From a clone</b></summary>

```bash
git clone https://github.com/ninggest/diagram-design.git
```

The clone is the route that carries this fork's `.drawio` export. The marketplace
entries above resolve to the upstream repository, because this fork keeps upstream's
plugin identity — see [Provenance and license](#provenance-and-license).

</details>

---

## Quickstart

```bash
npx skills add ninggest/diagram-design        # this fork
npx skills add cathrynlavery/diagram-design  # upstream
```

Then ask your agent in plain words:

- *"Make me an architecture diagram of my app: frontend, backend, database, Redis cache."*
- *"I need a quadrant showing Q2 projects by impact vs effort."*
- *"Give me an editable draw.io file of this flow that I can rearrange by hand."*
- *"Onboard diagram-design to https://yoursite.com"* (pulls your palette and fonts so every diagram after this one matches your site)

The agent picks the type, states its plan, and writes one `.html` file you can open by
double-clicking.

---

## The draw.io export

```bash
# one file, no Playwright needed
/diagram-design:export-diagram path/to/diagram.html --drawio

# or in the Pi surface
/export-diagram path/to/diagram.html --drawio
```

or just ask: *"Give me an editable draw.io file I can rearrange."*

`--drawio` on its own produces just the `.drawio`; add `--svg-only` or `--png-only` if
you want an image as well. What lands in the file:

| The diagram has | The `.drawio` gets |
|---|---|
| A step box | A vertex; the name stays bold, the sub-label stays mono and smaller |
| A connector | An edge with `source`/`target` set and `exitX`/`entryY` attach fractions |
| A swimlane band | A container holding its steps; the role name is the container's own label |
| A caption beside a step | A child of that step, so it travels with it |
| A filled band | A polygon vertex carrying `polyCoords` — a shape, not a picture |
| A legend key or divider | Decoration: an edge or a small rectangle, no endpoints |

Two honest limits. Fonts are not embedded, so draw.io renders with its own faces and a
CJK diagram falls back to the system font. And a value bar and the ribbon around it
stay separate objects with no relation between them, so dragging one detaches it from
the other — for charts, the SVG or a design tool is still the better editing surface.
`.drawio` earns its place for process, architecture and swimlane diagrams.

Full procedure: [`references/export.md`](skills/diagram-design/references/export.md).

---

## What it makes

45 diagram types, each in three static variants: minimal light, minimal dark, and
full-editorial. Open any of them directly in a browser. There is no build step,
JavaScript, or external image dependency.

<table>
<tr>
  <td align="center" width="33%"><a href="docs/screenshots/architecture.png"><img src="docs/screenshots/thumbs/architecture.webp" alt="Architecture"></a><br><b>Architecture</b><br><sub>Components + connections</sub></td>
  <td align="center" width="33%"><a href="docs/screenshots/it-state.png"><img src="docs/screenshots/thumbs/it-state.webp" alt="IT current-state"></a><br><b>IT current-state</b><br><sub>Legacy landscape + modernization</sub></td>
  <td align="center" width="33%"><a href="docs/screenshots/flowchart.png"><img src="docs/screenshots/thumbs/flowchart.webp" alt="Flowchart"></a><br><b>Flowchart</b><br><sub>Decision logic</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/sequence.png"><img src="docs/screenshots/thumbs/sequence.webp" alt="Sequence"></a><br><b>Sequence</b><br><sub>Messages over time</sub></td>
  <td align="center"><a href="docs/screenshots/state.png"><img src="docs/screenshots/thumbs/state.webp" alt="State machine"></a><br><b>State machine</b><br><sub>States + transitions</sub></td>
  <td align="center"><a href="docs/screenshots/er.png"><img src="docs/screenshots/thumbs/er.webp" alt="ER"></a><br><b>ER / data model</b><br><sub>Entities + fields</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/timeline.png"><img src="docs/screenshots/thumbs/timeline.webp" alt="Timeline"></a><br><b>Timeline</b><br><sub>Events on an axis</sub></td>
  <td align="center"><a href="docs/screenshots/swimlane.png"><img src="docs/screenshots/thumbs/swimlane.webp" alt="Swimlane"></a><br><b>Swimlane</b><br><sub>Cross-functional flow</sub></td>
  <td align="center"><a href="docs/screenshots/quadrant.png"><img src="docs/screenshots/thumbs/quadrant.webp" alt="Quadrant"></a><br><b>Quadrant</b><br><sub>Two-axis positioning</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/radar.png"><img src="docs/screenshots/thumbs/radar.webp" alt="Radar chart"></a><br><b>Radar / spider</b><br><sub>Multi-axis comparison</sub></td>
  <td align="center"><a href="docs/screenshots/loop.png"><img src="docs/screenshots/thumbs/loop.webp" alt="Loop"></a><br><b>Loop / flywheel</b><br><sub>Reinforcing cycle + shared hub</sub></td>
  <td align="center"><a href="docs/screenshots/nested.png"><img src="docs/screenshots/thumbs/nested.webp" alt="Nested"></a><br><b>Nested</b><br><sub>Hierarchy by containment</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/tree.png"><img src="docs/screenshots/thumbs/tree.webp" alt="Tree"></a><br><b>Tree</b><br><sub>Parent → children</sub></td>
  <td align="center"><a href="docs/screenshots/org-chart.png"><img src="docs/screenshots/thumbs/org-chart.webp" alt="Org chart"></a><br><b>Org chart</b><br><sub>Ownership + routing</sub></td>
  <td align="center"><a href="docs/screenshots/layers.png"><img src="docs/screenshots/thumbs/layers.webp" alt="Layer stack"></a><br><b>Layer stack</b><br><sub>Stacked abstractions</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/venn.png"><img src="docs/screenshots/thumbs/venn.webp" alt="Venn"></a><br><b>Venn</b><br><sub>Set overlap</sub></td>
  <td align="center"><a href="docs/screenshots/pyramid.png"><img src="docs/screenshots/thumbs/pyramid.webp" alt="Pyramid"></a><br><b>Pyramid / funnel</b><br><sub>Ranked hierarchy or drop-off</sub></td>
  <td align="center"><a href="docs/screenshots/bar.png"><img src="docs/screenshots/thumbs/bar.webp" alt="Bar chart"></a><br><b>Bar chart</b><br><sub>Categorical comparison</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/treemap.png"><img src="docs/screenshots/thumbs/treemap.webp" alt="Treemap"></a><br><b>Treemap</b><br><sub>Part-of-whole by area</sub></td>
  <td align="center"><a href="docs/screenshots/line.png"><img src="docs/screenshots/thumbs/line.webp" alt="Line chart"></a><br><b>Line chart</b><br><sub>Trends over time</sub></td>
  <td align="center"><a href="docs/screenshots/gantt.png"><img src="docs/screenshots/thumbs/gantt.webp" alt="Gantt"></a><br><b>Gantt</b><br><sub>Tasks + phases on a timeline</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/scatter.png"><img src="docs/screenshots/thumbs/scatter.webp" alt="Scatter plot"></a><br><b>Scatter plot</b><br><sub>Distribution + correlation</sub></td>
  <td align="center"><a href="docs/screenshots/high-level.png"><img src="docs/screenshots/thumbs/high-level.webp" alt="High-Level"></a><br><b>High-Level</b><br><sub>End-to-end stack on a cluster</sub></td>
  <td align="center"><a href="docs/screenshots/process.png"><img src="docs/screenshots/thumbs/process.webp" alt="Process"></a><br><b>Process</b><br><sub>Multi-actor sequential workflow</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/medallion.png"><img src="docs/screenshots/thumbs/medallion.webp" alt="Medallion"></a><br><b>Medallion</b><br><sub>Multi-tier data storage</sub></td>
  <td align="center"><a href="docs/screenshots/data-flow.png"><img src="docs/screenshots/thumbs/data-flow.webp" alt="Data flow"></a><br><b>Data flow</b><br><sub>Role-scoped pipeline steps</sub></td>
  <td align="center"><a href="docs/screenshots/dp-integration.png"><img src="docs/screenshots/thumbs/dp-integration.webp" alt="DP integration"></a><br><b>DP integration</b><br><sub>Sources → core → consumers</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/dp-security-matrix.png"><img src="docs/screenshots/thumbs/dp-security-matrix.webp" alt="DP security matrix"></a><br><b>DP security matrix</b><br><sub>Per-role access permissions</sub></td>
  <td align="center"><a href="docs/screenshots/sankey.png"><img src="docs/screenshots/thumbs/sankey.webp" alt="Sankey"></a><br><b>Sankey</b><br><sub>Quantities that split + merge</sub></td>
  <td align="center"><a href="docs/screenshots/fishbone.png"><img src="docs/screenshots/thumbs/fishbone.webp" alt="Fishbone"></a><br><b>Fishbone</b><br><sub>Grouped causes → one effect</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/wardley.png"><img src="docs/screenshots/thumbs/wardley.webp" alt="Wardley map"></a><br><b>Wardley map</b><br><sub>Value chain × evolution</sub></td>
  <td align="center"><a href="docs/screenshots/kanban.png"><img src="docs/screenshots/thumbs/kanban.webp" alt="Kanban"></a><br><b>Kanban</b><br><sub>Work in progress by state</sub></td>
  <td align="center"><a href="docs/screenshots/journey.png"><img src="docs/screenshots/thumbs/journey.webp" alt="User journey"></a><br><b>User journey</b><br><sub>Stages, actions + sentiment</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/deployment.png"><img src="docs/screenshots/thumbs/deployment.webp" alt="Deployment"></a><br><b>Deployment</b><br><sub>Zones, hosts + artifacts</sub></td>
  <td align="center"><a href="docs/screenshots/dependency.png"><img src="docs/screenshots/thumbs/dependency.webp" alt="Dependency graph"></a><br><b>Dependency graph</b><br><sub>Fan-in, ranks + cycles</sub></td>
  <td align="center"><a href="docs/screenshots/uml-class.png"><img src="docs/screenshots/thumbs/uml-class.webp" alt="UML class"></a><br><b>UML class</b><br><sub>Classes, operations + typed relations</sub></td>
</tr>
<tr>
  <td align="center"><a href="docs/screenshots/story-map.png"><img src="docs/screenshots/thumbs/story-map.webp" alt="Story map"></a><br><b>Story map</b><br><sub>Backbone × release slices</sub></td>
  <td align="center"><a href="docs/screenshots/db-schema.png"><img src="docs/screenshots/thumbs/db-schema.webp" alt="Database schema"></a><br><b>Database schema</b><br><sub>Physical tables + column FKs</sub></td>
  <td align="center"><a href="docs/screenshots/polar.png"><img src="docs/screenshots/thumbs/polar.webp" alt="Polar chart"></a><br><b>Polar chart</b><br><sub>Cyclic magnitude · linear radius</sub></td>
</tr>
<tr>
  <td align="center" width="33%"><a href="docs/screenshots/waterfall.png"><img src="docs/screenshots/thumbs/waterfall.webp" alt="Waterfall"></a><br><b>Waterfall</b><br><sub>Running total + signed bridges</sub></td>
  <td align="center" width="33%"><a href="docs/screenshots/architecture-delta.png"><img src="docs/screenshots/thumbs/architecture-delta.webp" alt="Architecture delta"></a><br><b>Architecture delta</b><br><sub>Before · Changes · After topology</sub></td>
  <td align="center" width="33%"><a href="docs/screenshots/exploded.png"><img src="docs/screenshots/thumbs/exploded.webp" alt="Exploded axonometric"></a><br><b>Exploded axonometric</b><br><sub>Parts pulled apart on one axis</sub></td>
</tr>
<tr>
  <td align="center" width="33%"><a href="docs/screenshots/axonometric-plan.png"><img src="docs/screenshots/thumbs/axonometric-plan.webp" alt="Axonometric plan"></a><br><b>Axonometric plan</b><br><sub>Rooms and buildings on one plate</sub></td>
  <td align="center" width="33%"><a href="docs/screenshots/heatmap.png"><img src="docs/screenshots/thumbs/heatmap.webp" alt="Heatmap"></a><br><b>Heatmap</b><br><sub>Value per row × column cell</sub></td>
  <td align="center" width="33%"><a href="docs/screenshots/service-blueprint.png"><img src="docs/screenshots/thumbs/service-blueprint.webp" alt="Service blueprint"></a><br><b>Service blueprint</b><br><sub>Frontstage and backstage on a shared stage grid</sub></td>
</tr>
</table>

---

## How it compares

| | Mermaid / PlantUML | draw.io / Excalidraw | Diagram Design |
|---|---|---|---|
| You make it by | Writing text | Dragging shapes by hand | Describing it to your agent |
| Layout | Automatic | Manual | Placed by the agent on a 4px grid, with CI checks for overlaps and clipping |
| Look | The renderer's theme | Whatever you draw | One opinionated editorial style, matched to your brand |
| Output | Text that renders on GitHub | An editable `.drawio` or `.excalidraw` file | One HTML file with inline SVG, exportable to SVG, PNG or draw.io |
| Change it later | Edit the text | Edit the canvas | Ask the agent again, edit the SVG, or export to draw.io and drag the boxes |
| Existing diagrams | | | Redraws Mermaid, draw.io and Excalidraw files |

The downsides are real. Output quality depends on the model you run it with, and the
same prompt can lay out differently twice. The result is not an editable source
format: there is no text to diff in a pull request. For docs that live in Git and
change every sprint, Mermaid is still the better fit. Diagram Design is for the
diagram you are going to publish. If you do want a canvas to drag boxes on, export
to `.drawio` — but that file is a derivative of the HTML, not the thing you version.

---

## Output formats

| Format | Deliverable | Keeps | Drops |
|---|---|---|---|
| `html` | self-contained `.html` (default) | header, diagram, summary cards, footer, live fonts | nothing |
| `svg` | `.svg` next to the source | the `<svg>` node, vector text | editorial wrapper; fonts substitute in offline tools |
| `png` | `.png` at `device_scale_factor` | pixels exactly as the browser renders them | vector editability |
| `drawio` | `.drawio` next to the source | the shape graph: editable shapes, lane containers, connectors glued to the shapes they join | editorial wrapper; fonts are not embedded |
| `html+png` | both | — | — |

SVG export carries CDATA-wrapped diagram CSS, including selectors bound to the original
SVG root, and preserves quoted selector values containing comment delimiters. PNG export
rasterizes via Playwright at 2× by default (one-time setup: `pip install playwright &&
playwright install chromium`); it does not need Playwright. A `--registry` flag emits
`<basename>.registry.json` for the traceable block decomposition pattern. See
[`references/export.md`](skills/diagram-design/references/export.md) and
[`references/export-registry.md`](skills/diagram-design/references/export-registry.md).

---

## Match your brand

Onboarding pulls a URL and extracts the palette and fonts, then every diagram after it
matches your site. The contrast checks run automatically, and the skill refuses to ship
a diagram whose text does not clear 4.5:1 on paper. A first run asks before it
customizes anything. Procedure:
[`references/onboarding.md`](skills/diagram-design/references/onboarding.md).

## Import existing diagrams

Point the skill at a `.drawio`, `.mmd`/`.mermaid`, or `.excalidraw` file and it reads
the structure, then redraws it in this design system — discarding the source's
coordinates, palette and shape vocabulary.

[![Redrawn from a .drawio file](docs/screenshots/thumbs/import-drawio.webp)](docs/screenshots/import-drawio.png)

*A 12-node draw.io file redrawn at `balanced` detail for a blog post. The source's six pastel fills became one accent; its hand-dragged coordinates became a 4px grid.*

```
/diagram-design:import-drawio platform.drawio
/diagram-design:import-drawio platform.drawio --size=slide-16x9 --detail=simplified
/diagram-design:import-mermaid architecture.mmd --detail=faithful
/diagram-design:import-excalidraw whiteboard.excalidraw --size=slide-16x9
```

Four dials decide the outcome:

| Dial | Options | What it changes |
|---|---|---|
| **Format** | `html` · `svg` · `png` · `drawio` · `html+png` | The deliverable. SVG for Figma, PNG for slides, draw.io for editing, HTML for the web. |
| **Size** | `doc-inline` · `doc-wide` · `slide-16x9` · `slide-4x3` · `social-og` · `social-square` · `print-a4-landscape` · `print-a3-landscape` · `print-letter-landscape` · `fit` | The `viewBox` **and the type ramp**: a projected slide gets 16px node names, not 12px. |
| **Detail** | `faithful` (≤24 nodes, zoned) · `balanced` (≤12) · `simplified` (≤7) | How much of the source survives, via a fixed degrade ladder: decorations, then duplicates, then leaf clusters, then infrastructure. |
| **Audience** | `engineer` · `mixed` · `executive` | The *wording*, not the count. `Auth Service / JWT · RS256 · :8443` → `Auth Service / token check` → `Sign-in`. |

Every import ships a fidelity ledger listing what was merged, collapsed or dropped. See
[`references/import-drawio.md`](skills/diagram-design/references/import-drawio.md),
[`references/import-mermaid.md`](skills/diagram-design/references/import-mermaid.md) and
[`references/import-excalidraw.md`](skills/diagram-design/references/import-excalidraw.md).

---

## Architecture

```
diagram-design/
├── .agents/plugins/marketplace.json  # Codex marketplace catalog
├── .claude-plugin/                   # Claude marketplace + plugin manifest
├── .codex-plugin/                    # Codex plugin manifest
├── .factory-plugin/                  # Factory Droid marketplace + plugin manifest
├── .qoder-plugin/                    # Qoder native plugin manifest
├── commands/
│   ├── export-diagram.md             # plugin export command
│   ├── import-drawio.md              # plugin draw.io import command
│   ├── import-mermaid.md             # plugin Mermaid import command
│   ├── import-excalidraw.md          # plugin Excalidraw import command
│   ├── profile.md                    # plugin client-profile command
│   └── doctor.md                     # plugin environment diagnostics command
├── prompts/
│   ├── export-diagram.md             # Pi `/export-diagram` prompt template
│   ├── import-mermaid.md             # Pi Mermaid import prompt template
│   ├── import-excalidraw.md          # Pi Excalidraw import prompt template
│   ├── profile.md                    # Pi `/profile` prompt template
│   └── doctor.md                     # Pi `/doctor` diagnostics prompt template
├── skills/
│   └── diagram-design/
│       ├── SKILL.md                  # philosophy, selection guide, checklist
│       ├── references/               # loaded only when a type or primitive is chosen
│       │   ├── style-guide.md        # single source of truth for colors + fonts
│       │   ├── semantic-patterns.md  # behavior patterns independent of layout
│       │   ├── animation.md          # optional motion + accessibility contract
│       │   ├── onboarding.md         # the URL-to-tokens flow
│       │   ├── profiles.md           # named client profiles + project markers
│       │   ├── doctor.md             # environment diagnostics
│       │   ├── import-drawio.md      # draw.io redraw procedure
│       │   ├── import-mermaid.md     # Mermaid redraw procedure
│       │   ├── import-excalidraw.md  # Excalidraw redraw procedure
│       │   ├── output-spec.md        # format × size × detail level
│       │   ├── export.md             # SVG / PNG export + sizing
│       │   ├── export-registry.md    # block-metadata JSON sidecar export
│       │   ├── primitives-core.md    # exact markup for nodes, arrows, labels
│       │   ├── layout-budget.md      # 4px grid + per-type budgets
│       │   ├── primitive-annotation.md
│       │   ├── primitive-icons.md
│       │   ├── primitive-sketchy.md
│       │   ├── primitive-terminal.md
│       │   ├── type-architecture.md
│       │   ├── type-architecture-delta.md
│       │   ├── type-axonometric-plan.md
│       │   ├── type-bar.md
│       │   ├── type-data-flow.md
│       │   ├── type-db-schema.md
│       │   ├── type-dependency.md
│       │   ├── type-deployment.md
│       │   ├── type-dp-integration.md
│       │   ├── type-dp-security-matrix.md
│       │   ├── type-er.md
│       │   ├── type-exploded.md
│       │   ├── type-fishbone.md
│       │   ├── type-flowchart.md
│       │   ├── type-gantt.md
│       │   ├── type-heatmap.md
│       │   ├── type-high-level.md
│       │   ├── type-it-state.md
│       │   ├── type-journey.md
│       │   ├── type-kanban.md
│       │   ├── type-layers.md
│       │   ├── type-line.md
│       │   ├── type-loop.md
│       │   ├── type-medallion.md
│       │   ├── type-nested.md
│       │   ├── type-org-chart.md
│       │   ├── type-polar.md
│       │   ├── type-process.md
│       │   ├── type-pyramid.md
│       │   ├── type-quadrant.md
│       │   ├── type-radar.md
│       │   ├── type-sankey.md
│       │   ├── type-scatter.md
│       │   ├── type-sequence.md
│       │   ├── type-service-blueprint.md
│       │   ├── type-state.md
│       │   ├── type-story-map.md
│       │   ├── type-swimlane.md
│       │   ├── type-timeline.md
│       │   ├── type-tree.md
│       │   ├── type-treemap.md
│       │   ├── type-uml-class.md
│       │   ├── type-venn.md
│       │   ├── type-wardley.md
│       │   └── type-waterfall.md
│       ├── scripts/
│       │   ├── drawio_extract.py     # draw.io → structured IR
│       │   ├── mermaid_extract.py    # Mermaid → structured IR
│       │   ├── excalidraw_extract.py  # Excalidraw → structured IR
│       │   ├── export_svg.py         # standalone SVG export
│       │   ├── export_png.py         # Playwright PNG renderer
│       │   ├── export_drawio.py      # draw.io export (shape graph, glued connectors)
│       │   ├── export_drawio.py      # draw.io export (shape graph, glued connectors)
│       │   └── self_check.py         # packaged output self-check (runs installed)
│       └── assets/
│           ├── index.html            # live gallery, tabbed
│           ├── icons.html            # icon library browser
│           ├── template*.html        # scaffolds for new diagrams
│           ├── example-<type>.html   # 3 variants per type
│           ├── example-loop-terminal.html
│           ├── example-quadrant-consultant.html
│           ├── example-import-drawio.html
│           ├── example-import-mermaid.html
│           ├── example-import-excalidraw.html
│           ├── example-policy-trace-animated.html
│           └── example-sequence-oauth*.html
├── scripts/                          # CI gates and build helpers (see CONTRIBUTING.md)
│   ├── lint-skin.py                  # palette, fonts, a11y, single-file safety
│   ├── lint-render.py                # Chromium rendered-layout checker
│   ├── verify-docs-sync.py           # routing, gallery, README and count sync
│   ├── verify-geometry.py            # label, connector and port geometry
│   ├── render-canonical-screenshots.py  # deterministic per-type PNG catalog renderer
│   ├── build-readme-thumbs.py        # regenerates docs/screenshots/thumbs/
│   └── fixtures/                     # draw.io, Mermaid and Excalidraw test inputs
├── docs/cookbook.md                  # operator recipes for editable installs and common tasks
├── docs/adr/                         # short records of settled design decisions
├── docs/superpowers/                 # design specs and implementation plans (plans/, specs/)
├── docs/hero/                        # README demo GIFs (dark, light) and social preview image
├── docs/screenshots/                 # full-resolution images + source-digest manifest.json
├── docs/screenshots/thumbs/          # generated WebP previews the README renders
├── CHANGELOG.md                      # release history
└── CONTRIBUTING.md                   # validation gates and how each one works
```


### What loads when

`SKILL.md` first, then exactly one type reference, then the two core references
(`primitives-core.md`, `layout-budget.md`) — and nothing else. The gallery, the
templates and the importers load only when you ask for them. Full map:
[`docs/cookbook.md`](docs/cookbook.md).

---

## Provenance and license

This fork is MIT-licensed, like upstream. The upstream copyright notice and permission
notice in [`LICENSE`](LICENSE) are unchanged and must stay in every copy — that is the
one condition MIT imposes.

**Upstream:** [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design)
by Cathryn Lavery, MIT. Everything here except the list below is that project, including
the 45 diagram types, the design system, the importers and the validation gates.

**What this fork changes:**

| File | Change |
|---|---|
| `skills/diagram-design/scripts/export_drawio.py` | New. The `.drawio` exporter. |
| `scripts/test-export-drawio.py` | New. Nine regression tests, including a round trip through the skill's own draw.io importer. |
| `skills/diagram-design/references/export.md` | New "draw.io export procedure" section. |
| `skills/diagram-design/SKILL.md` | A "Exporting to draw.io" subsection; the script path is exposed for strict bundlers. |
| `commands/export-diagram.md`, `prompts/export-diagram.md` | A `--drawio` flag on both export surfaces. |
| `skills/diagram-design/references/output-spec.md` | `drawio` joins the format dial. |
| `scripts/verify-docs-sync.py` | The new script joins the packaged-runtime-file list. |
| `.github/workflows/ci.yml`, `.maintainer-policy.json` | The new test is registered as a CI gate in both places. |

The plugin manifests, `SECURITY.md`, `PRIVACY.md` and `CODE_OF_CONDUCT.md` still name
the upstream maintainer, and the plugin is still published as `diagram-design`. Report
a security problem through the upstream's private advisory channel, and read the
upstream privacy policy for the plugin's data handling.

Third-party assets keep their own terms — Tabler Icons (MIT), Simple Icons (CC0),
log-z/logos (MIT), Devicon (MIT) and Instrument Serif (SIL OFL 1.1). See
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) for what each covers and for the
trademark note on the brand marks in the icon set.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first — it lists the validation gates every
change must pass, and the rules for each kind of change. The gate suite is also in
[`.maintainer-policy.json`](.maintainer-policy.json).

```bash
python3 scripts/verify-docs-sync.py     # docs, routing and packaging stay in sync
python3 scripts/lint-skin.py --all      # palette, fonts and the a11y contract
python3 scripts/test-export-drawio.py   # the draw.io export contract
```

## About

Diagram Design is by [Cathryn Lavery](https://github.com/cathrynlavery). This fork
extends it with an editable draw.io export.
