# SOUPS Co-authorship Network Evolution

Interactive visualization of the temporal evolution of the usable security research community, based on SOUPS co-authorship data from [DBLP](https://dblp.org/db/conf/soups/index.html).

## Repository layout

```
dblp/                     SOUPS proceedings as DBLP XML, one file per year (soups2005.xml …)
scripts/fetch-dblp.sh     downloads the XML from DBLP into dblp/
scripts/dblp-graphml.py   builds the co-authorship GraphML files from dblp/
data/                     cumulative GraphML per year (soups_2005.graphml …) + manifest.json
generate_manifest.py      writes data/manifest.json from the GraphML files in data/
index.html                the visualization
```

## Running locally

```bash
python3 -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000).

## Adding a new year

1. Get the proceedings XML into `dblp/`:
   ```bash
   scripts/fetch-dblp.sh 2027 2027
   ```
   DBLP often blocks scripted downloads with a bot check. If the script says so, open
   `https://dblp.org/db/conf/soups/soups2027.xml` in a browser and save it as `dblp/soups2027.xml`.

2. Rebuild all yearly GraphML files and the manifest (needs `pip install -r scripts/requirements.txt` once):
   ```bash
   python3 scripts/dblp-graphml.py dblp data --cumulative
   python3 generate_manifest.py
   ```

3. Commit and push. GitHub Pages serves the site from the `main` branch root.

## Data notes

- Authors are identified by their DBLP person id (`pid`), so name variants that DBLP has merged
  (e.g. "Emilee Rader" / "Emilee J. Rader") are one node. Each node's `name` is the most recently
  used variant; DBLP's number suffix (" 0001") is dropped unless two people would share a name.
- Each GraphML file is **cumulative** (all papers up to that year). Each co-author pair is one edge
  whose `weight` is the number of papers they wrote together; nodes carry a `papers` count.
- Communities are computed at build time with Leiden (modularity, resolutions 0.1–2; 1 is the default in
  the viewer) on Newman-weighted edges (each paper adds 1/(n-1) to each pair of its n authors). Each year
  starts from the previous year's partition, and communities are matched to last year's by member overlap,
  so a community keeps its label and colour over time: a change means the data changed, not the algorithm.
  Groups under 5 authors get no label (grey). Stored as node attributes `community_0` … `community_4`.
- The visualization diffs consecutive years to identify new nodes and edges, and node positions
  persist across years so the network grows organically.
