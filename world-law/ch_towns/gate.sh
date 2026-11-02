# usage: gate.sh <town-key> <tlex-host> <city-site-host>   (claim, tlex robots alone, city robots)
h(){ python -c "import hashlib,sys;print('probe-cache/'+hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16]+'.body')" "$1"; }
python -I claim.py claim "$1" || exit 1
python -I -X utf8 probe.py 3 "https://$2/robots.txt"
f=$(h "https://$2/robots.txt"); cmp -s <(tr -d '\r' <$f) <(tr -d '\r' < ../../switzerland-winterthur-city-law/.cache/robots.txt) && echo "tlex robots SAME as Winterthur" || { echo "tlex robots DIFFER:"; head -50 $f; }
python -I -X utf8 probe.py 3 "https://$3/robots.txt"; echo "--- $3 robots:"; head -40 $(h "https://$3/robots.txt")
grep -q -i -E "^[[:space:]]*user-agent:[[:space:]]*(claudebot|claude-web|anthropic-ai|gptbot|claude-user|claude-searchbot)" $(h "https://$3/robots.txt") && { echo "STOP: $3 robots names an AI agent"; exit 2; }
echo; python -I -X utf8 probe.py 3 "https://$3/"; grep -o -i -E 'href="[^"]*(impressum|rechtlich|disclaimer|nutzung|hinweis|copyright|mentions|legal)[^"]*"' $(h "https://$3/") | sort -u | head
