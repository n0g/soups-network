# SOUPS Co-authorship Network Evolution

Interactive visualization of the temporal evolution of the usable security research community, based on SOUPS co-authorship data.

## Setup

1. Add cumulative yearly GraphML files to `data/` — name them with a 4-digit year anywhere in the filename:
   ```
   data/soups_2005.graphml
   data/soups_2006.graphml
   ...
   ```

2. Generate the manifest:
   ```bash
   python3 generate_manifest.py
   ```

3. Serve locally:
   ```bash
   python3 -m http.server 8000
   ```

4. Open [http://localhost:8000](http://localhost:8000)

## Deployment

Push to GitHub and enable GitHub Pages (Settings → Pages → main branch / root).

The site will be live at `https://YOUR_USERNAME.github.io/soups-network/`

## Adding New Years

1. Drop the new GraphML file in `data/`
2. Run `python3 generate_manifest.py`
3. Commit and push

## Notes

- Each GraphML file should be **cumulative** (all papers up to that year, not just that year)
- The visualization diffs consecutive years to identify new nodes and edges
- Node positions persist across years so the network grows organically
