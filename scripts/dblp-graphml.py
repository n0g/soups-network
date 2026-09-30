#! /usr/bin/env python3
"""
Build co-authorship GraphML files from DBLP proceedings XML (e.g. soups2026.xml).

Authors are identified by their DBLP person id (pid), so name variants that DBLP
has merged (e.g. "Emilee Rader" / "Emilee J. Rader") become a single node. Each
node carries one display name, chosen across ALL input files so a person keeps
the same name in every yearly snapshot. Each co-author pair is a single edge
whose weight is the number of papers they wrote together.

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


def write_graphml(papers, names, path):
	paper_count = collections.Counter()
	weights = collections.Counter()
	for p in papers:
		paper_count.update(p.authors)
		for a, b in itertools.combinations(sorted(p.authors), 2):
			weights[(a, b)] += 1

	root = ElementTree.Element('graphml', xmlns="http://graphml.graphdrawing.org/xmlns")
	ElementTree.SubElement(root, 'key', id="name", attrib={'for': "node", 'attr.name': "name", 'attr.type': "string"})
	ElementTree.SubElement(root, 'key', id="papers", attrib={'for': "node", 'attr.name': "papers", 'attr.type': "int"})
	ElementTree.SubElement(root, 'key', id="weight", attrib={'for': "edge", 'attr.name': "weight", 'attr.type': "int"})
	graph = ElementTree.SubElement(root, 'graph', id="G", edgedefault="undirected")
	for pid in sorted(paper_count, key=lambda p: names[p]):
		node = ElementTree.SubElement(graph, 'node', id=pid)
		ElementTree.SubElement(node, 'data', key="name").text = names[pid]
		ElementTree.SubElement(node, 'data', key="papers").text = str(paper_count[pid])
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

	if not ns.cumulative:
		write_graphml(parser.papers, names, ns.output)
		return
	os.makedirs(ns.output, exist_ok=True)
	for year in sorted({p.year for p in parser.papers}):
		upto = [p for p in parser.papers if p.year <= year]
		write_graphml(upto, names, os.path.join(ns.output, "{}{}.graphml".format(ns.prefix, year)))


if __name__ == "__main__":
	sys.exit(main())
