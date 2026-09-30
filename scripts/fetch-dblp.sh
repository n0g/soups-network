#! /bin/sh
# Download SOUPS proceedings XML from DBLP into dblp/.
#
# Usage: scripts/fetch-dblp.sh [first_year] [last_year]    (default: 2005 to the current year)
#
# DBLP puts a bot check in front of scripted downloads, so this may fail. In that case open
# https://dblp.org/db/conf/soups/soupsYYYY.xml in a browser and save it as dblp/soupsYYYY.xml.

cd "$(dirname "$0")/.." || exit 1
first=${1:-2005}
last=${2:-$(date +%Y)}

for year in $(seq "$first" "$last"); do
	out="dblp/soups$year.xml"
	tmp="$out.tmp"
	curl -sSL -o "$tmp" "https://dblp.org/db/conf/soups/soups$year.xml"
	if head -c 200 "$tmp" | grep -q '<bht'; then
		mv "$tmp" "$out"
		echo "$year: $(grep -c '<inproceedings' "$out") papers"
	else
		rm -f "$tmp"
		echo "$year: not downloaded (bot check or no proceedings yet) - get it in a browser"
	fi
done
