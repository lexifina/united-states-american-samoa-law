# usage: batch.sh town:tlexhost:sitehost ...   strictly sequential
h(){ python -c "import hashlib,sys;print('probe-cache/'+hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16]+'.body')" "$1"; }
for spec in "$@"; do
  IFS=: read t tl site <<<"$spec"
  echo "===== $t"
  out=$(bash gate.sh "$t" "$tl" "$site" 2>&1); rc=$?; echo "$out" | grep -E 'robots ->|SAME|DIFFER|STOP|claimed|href' | cut -c1-200
  if [ $rc -eq 2 ]; then python -I claim.py release "$t"; echo "VERDICT $t: FAIL ai-optout"; continue; fi
  [ $rc -ne 0 ] && { echo "VERDICT $t: gate error rc=$rc"; python -I claim.py release "$t"; continue; }
  imp=$(echo "$out" | grep -o -E 'href="/_rtr/impressum"|href="[^"]*impressum[^"]*"' | head -1 | sed -E 's/href="([^"]*)"/\1/')
  [ -z "$imp" ] && { echo "VERDICT $t: no impressum link found (manual)"; continue; }
  case $imp in http*) u=$imp;; *) u="https://$site$imp";; esac
  n=$(bash notice.sh "$u" 2>&1)
  echo "$n" | grep -i -E 'urheber|reprodu|zustimmung|gesetz|bewilligung' | cut -c1-400
  if echo "$n" | grep -q 'schriftliche Zustimmung der Urheberrechtsträger im Voraus'; then python -I claim.py release "$t"; echo "VERDICT $t: HOLD i-web consent clause ($u)"; else echo "VERDICT $t: NEEDS READING ($u), claim kept"; fi
done
