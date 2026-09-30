#! /usr/bin/env python3
"""
Build co-authorship GraphML files from DBLP proceedings XML (e.g. soups2026.xml).

Authors are identified by their DBLP person id (pid), so name variants that DBLP
has merged (e.g. "Emilee Rader" / "Emilee J. Rader") become a single node. Each
node carries one display name, chosen across ALL input files so a person keeps
the same name in every yearly snapshot. Each co-author pair is a single edge
whose weight is the number of papers they wrote together.

Communities are detected with Leiden (modularity with a resolution parameter) on
Newman-weighted edges (each paper adds 1/(n-1) to every pair of its n authors),
at several resolutions. With --cumulative, each year starts from the previous
year's partition and communities are matched to the previous year's by member
overlap, so a community keeps its label (and colour in the viewer) over time and
a label change means the data changed. Communities under MIN_COMMUNITY_SIZE
members get label -1. Requires: pip install igraph leidenalg

Usage:
  dblp-graphml.py <xml file or folder> <output.graphml>
  dblp-graphml.py <folder> <output dir> --cumulative [--prefix soups_]
      writes <output dir>/<prefix>YYYY.graphml containing all papers up to YYYY
"""

import os
import re
import sys
import argparse
import itertools
import collections
from xml.etree import ElementTree

import igraph
import leidenalg

RESOLUTIONS = [0.1, 0.25, 0.5, 1, 2]  # Leiden resolution levels, coarse to fine; 1 = standard modularity
MIN_COMMUNITY_SIZE = 5                # smaller groups are not labelled
MATCH_THRESHOLD = 0.3                 # min. Jaccard overlap to continue a community's label
PALETTE_SIZE = 20                     # viewer colours = label % PALETTE_SIZE
SEED = 42


class Paper:
	def __init__(self, title, year, authors):
		self.title = title
		self.year = year
		self.authors = authors  # list of pids


class Parser:
	def __init__(self):
		self.papers = []
		# pid -> Counter of (year, name) usages, to pick a display name later
		self.name_usage = collections.defaultdict(collections.Counter)

	def parse_file(self, file):
		print("parsing {}".format(file))
		m = re.search(r"(\d{4})", os.path.basename(file))
		file_year = int(m.group(1)) if m else None
		for e in ElementTree.parse(file).findall('.//inproceedings'):
			year = int(e.findtext('year') or file_year)
			pids = []
			for a in e.findall('author'):
				name = a.text.strip()
				pid = a.get('pid') or name  # fall back to the name if DBLP has no pid
				self.name_usage[pid][(year, name)] += 1
				if pid not in pids:
					pids.append(pid)
			self.papers.append(Paper(e.findtext('title'), year, pids))

	def display_names(self):
		"""Most recently used name per pid (ties: most frequent), without DBLP's ' 0001' suffix,
		unless stripping it would give two different people the same name."""
		chosen = {}
		for pid, usage in self.name_usage.items():
			latest = max(y for y, _ in usage)
			counts = collections.Counter({n: c for (y, n), c in usage.items() if y == latest})
			chosen[pid] = counts.most_common(1)[0][0]
		stripped = {pid: re.sub(r" \d{4}$", "", n) for pid, n in chosen.items()}
		clashes = collections.Counter(stripped.values())
		return {pid: stripped[pid] if clashes[stripped[pid]] == 1 else chosen[pid] for pid in chosen}


def pair_weights(papers):
	"""Joint paper count and Newman collaboration weight per co-author pair."""
	count = collections.Counter()
	newman = collections.Counter()
	for p in papers:
		for a, b in itertools.combinations(sorted(p.authors), 2):
			count[(a, b)] += 1
			newman[(a, b)] += 1 / (len(p.authors) - 1)
	return count, newman


class CommunityTracker:
	"""Leiden communities at one resolution, with labels that persist across yearly snapshots."""

	def __init__(self, resolution):
		self.resolution = resolution
		self.raw = {}       # pid -> Leiden community id from the previous snapshot (warm start)
		self.labels = {}    # label -> set of pids, communities alive in the previous snapshot
		self.used = set()   # labels ever handed out; never reused, so a label is one community's history

	def step(self, papers):
		pids = sorted({a for p in papers for a in p.authors})
		index = {pid: i for i, pid in enumerate(pids)}
		_, newman = pair_weights(papers)
		graph = igraph.Graph(n=len(pids), edges=[(index[a], index[b]) for a, b in newman])
		graph.es["weight"] = list(newman.values())

		init = None
		if self.raw:
			start = max(self.raw.values()) + 1
			init = [self.raw[pid] if pid in self.raw else start + i for i, pid in enumerate(pids)]
			compact = {c: i for i, c in enumerate(sorted(set(init)))}
			init = [compact[c] for c in init]
		part = leidenalg.find_partition(graph, leidenalg.RBConfigurationVertexPartition, weights="weight",
			resolution_parameter=self.resolution, initial_membership=init, n_iterations=-1, seed=SEED)
		previous = set(self.raw)
		self.raw = {pid: part.membership[i] for i, pid in enumerate(pids)}

		groups = [set(pids[i] for i in members) for members in part if len(members) >= MIN_COMMUNITY_SIZE]
		groups.sort(key=len, reverse=True)
		# match to last year's communities by Jaccard overlap among authors who already existed
		candidates = []
		for g, members in enumerate(groups):
			old = members & previous
			for label, before in self.labels.items():
				shared = len(old & before)
				if shared:
					candidates.append((shared / len(old | before), g, label))
		assigned, taken = {}, set()
		for score, g, label in sorted(candidates, reverse=True):
			if score >= MATCH_THRESHOLD and g not in assigned and label not in taken:
				assigned[g] = label
				taken.add(label)
		for g in range(len(groups)):
			if g not in assigned:
				assigned[g] = self._new_label({l % PALETTE_SIZE for l in assigned.values()})

		self.labels = {assigned[g]: members for g, members in enumerate(groups)}
		self.used.update(self.labels)
		result = dict.fromkeys(pids, -1)
		for label, members in self.labels.items():
			for pid in members:
				result[pid] = label
		return result

	def _new_label(self, colours_in_use):
		"""Smallest unused label whose colour no other current community has, if possible."""
		free_colour = len(colours_in_use) < PALETTE_SIZE
		label = 0
		while label in self.used or (free_colour and label % PALETTE_SIZE in colours_in_use):
			label += 1
		self.used.add(label)
		return label


def write_graphml(papers, names, path, communities):
	paper_count = collections.Counter(a for p in papers for a in p.authors)
	weights, _ = pair_weights(papers)

	root = ElementTree.Element('graphml', xmlns="http://graphml.graphdrawing.org/xmlns")
	ElementTree.SubElement(root, 'key', id="name", attrib={'for': "node", 'attr.name': "name", 'attr.type': "string"})
	ElementTree.SubElement(root, 'key', id="papers", attrib={'for': "node", 'attr.name': "papers", 'attr.type': "int"})
	ElementTree.SubElement(root, 'key', id="weight", attrib={'for': "edge", 'attr.name': "weight", 'attr.type': "int"})
	for level, resolution in enumerate(RESOLUTIONS):
		ElementTree.SubElement(root, 'key', id="community_{}".format(level),
			attrib={'for': "node", 'attr.name': "community (resolution {})".format(resolution), 'attr.type': "int"})
	graph = ElementTree.SubElement(root, 'graph', id="G", edgedefault="undirected")
	for pid in sorted(paper_count, key=lambda p: names[p]):
		node = ElementTree.SubElement(graph, 'node', id=pid)
		ElementTree.SubElement(node, 'data', key="name").text = names[pid]
		ElementTree.SubElement(node, 'data', key="papers").text = str(paper_count[pid])
		for level, labels in enumerate(communities):
			ElementTree.SubElement(node, 'data', key="community_{}".format(level)).text = str(labels[pid])
	for (a, b), w in sorted(weights.items()):
		edge = ElementTree.SubElement(graph, 'edge', source=a, target=b)
		ElementTree.SubElement(edge, 'data', key="weight").text = str(w)

	ElementTree.indent(root)
	ElementTree.ElementTree(root).write(path, encoding="UTF-8", xml_declaration=True)
	print("wrote {} ({} authors, {} co-author pairs)".format(path, len(paper_count), len(weights)))


def main(argv=None):
	ap = argparse.ArgumentParser(description="Generate co-authorship GraphML from DBLP proceedings XML.")
	ap.add_argument('input', help="DBLP XML file or folder of XML files")
	ap.add_argument('output', help="Output GraphML file, or output folder with --cumulative")
	ap.add_argument('--cumulative', action='store_true', help="write one cumulative file per year")
	ap.add_argument('--prefix', default="soups_", help="file name prefix for --cumulative (default: soups_)")
	ns = ap.parse_args(argv)

	parser = Parser()
	if os.path.isdir(ns.input):
		for f in sorted(os.listdir(ns.input)):
			if f.endswith('.xml'):
				parser.parse_file(os.path.join(ns.input, f))
	else:
		parser.parse_file(ns.input)
	names = parser.display_names()

	trackers = [CommunityTracker(r) for r in RESOLUTIONS]
	if not ns.cumulative:
		write_graphml(parser.papers, names, ns.output, [t.step(parser.papers) for t in trackers])
		return
	os.makedirs(ns.output, exist_ok=True)
	for year in sorted({p.year for p in parser.papers}):
		upto = [p for p in parser.papers if p.year <= year]
		communities = [t.step(upto) for t in trackers]
		write_graphml(upto, names, os.path.join(ns.output, "{}{}.graphml".format(ns.prefix, year)), communities)


if __name__ == "__main__":
	sys.exit(main())
