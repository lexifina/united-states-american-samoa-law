# Emails to send before faster fetching (drafted 2026-10-29)

Send from alan@lexifina.com. The addresses marked "confirm" are from memory; check each on the publisher's
contact page first.

---

## 1. Federal Register of Legislation (Australia)

**To:** feedback@legislation.gov.au
**Subject:** Notice of a full download of Acts and compilations via the API

Hello,

Your website asks to be told one to two weeks before a full crawl, so I'm writing ahead of one.

I'm Alan Yahya at Lexifina. We are building a version history of Commonwealth Acts: every compilation of every
Act, recorded in order of the date it came into force, with each change credited to the amending Act named in
the compilation's endnotes. The text is reproduced as published under CC BY 4.0, with your attribution.

The download is about 21,800 compilation files for 5,338 titles: the Constitution, the principal Acts in force,
repealed principal Acts with compilations, and the amending Acts as made. We would like to fetch these through
`api.prod.legislation.gov.au` with no more than 4 requests in flight, outside 08:00–20:00 AEST/AEDT, and cache
everything so each file is fetched only once. Updates afterwards would be small and incremental.

Please tell us if you would prefer a different rate, time window or route, such as a bulk export. We will stop
at once if asked. We have already fetched about 300 files through www.legislation.gov.au at your Crawl-delay
of 10 seconds.

Thank you,
Alan Yahya
Lexifina · alan@lexifina.com

---

## 2. ACT Parliamentary Counsel's Office

**To:** the Parliamentary Counsel's Office (confirm the address on legislation.act.gov.au → Contact us)
**Subject:** Request for bulk access to republications on the ACT Legislation Register

Hello,

I'm Alan Yahya at Lexifina. We are building a version history of ACT Acts: every republication, dated by its
effective date and credited to the amending law named in its endnotes. The text is reproduced under the JACS
copyright policy (CC BY 4.0, "© Australian Capital Territory").

We fetch at your robots.txt Crawl-delay of one request every 10 seconds. At that rate the register's
republication files for Acts in force take one to two days. Could you provide either:
- a bulk export of the republication files (DOCX/RTF) and their metadata, or
- permission to fetch at a modestly higher rate (for example 2 requests per second, outside business hours)?

We stay out of the paths robots.txt disallows, and we cache every file so it is only fetched once.

Thank you,
Alan Yahya
Lexifina · alan@lexifina.com

---

## 3. South Australian Legislation (Office of Parliamentary Counsel / AGD)

**To:** the South Australian Legislation team (confirm the address on legislation.sa.gov.au → Contact; the
site now answers us with a Cloudflare challenge, so use a browser)
**Subject:** Bulk access to historical versions on legislation.sa.gov.au

Hello,

I'm Alan Yahya at Lexifina. We are building a version history of South Australian Acts: every historical
version, dated by its in-force date and credited to the amending Act named in its legislative history. The text
is reproduced under CC BY 4.0 with the attribution and disclaimer your site requires.

We fetched at your robots.txt Crawl-delay of 10 seconds. Since about 14:08 UTC today (29 October) the site has
answered our requests with a Cloudflare challenge, so we have stopped. So far we have the RTF versions of about
360 of the 1,390 current Acts.

Could you provide either:
- a bulk export of the historical RTF versions and their metadata, or
- an allowance for our fetcher (we can give our IP address and user agent), at your Crawl-delay or a rate you
  choose?

We will not fetch again until we hear from you.

Thank you,
Alan Yahya
Lexifina · alan@lexifina.com

---

## 4. RIS (Austria): notice of a planned bulk download of Landesrecht (required by the RIS OGD rules)

**To:** ris.it@bka.gv.at
**Subject:** Ankündigung eines geplanten Massendownloads (OGD): Landesrecht konsolidiert (LrKons), alle Bundesländer

Sehr geehrte Damen und Herren,

wir kündigen gemäß den Nutzungsbedingungen der RIS-OGD-Schnittstelle einen Massendownload an.

- **Zweck:** eine Versionsgeschichte des konsolidierten Landesrechts aller neun Bundesländer (jede Fassung mit Datum), veröffentlicht unter CC BY 4.0 mit Namensnennung „Rechtsinformationssystem des Bundes (RIS)“.
- **Applikation:** LrKons (data.bka.gv.at/ris/api/v2.6), Bundesland jeweils einzeln.
- **User-Agent:** lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)
- **Quell-IP:** [IP-Adresse dieses Rechners eintragen]
- **Zeiten:** nur zwischen 20:00 und 05:00 Uhr (Wien) sowie an Wochenenden und Feiertagen, höchstens 0,5 Anfragen pro Sekunde über eine Verbindung.
- **Geplantes Ende:** [Datum]; danach nur kleine, inkrementelle Abfragen.

Für die Bundesrecht-Applikation (BrKons) haben wir bereits eine Ankündigung gesendet. Bitte teilen Sie uns mit, falls Sie andere Zeiten oder eine andere Vorgehensweise wünschen.

Mit freundlichen Grüßen
Alan Yahya, Lexifina · alan@lexifina.com

---

## 5. BC Laws (British Columbia): permission to fetch for a version history

**To:** BC Laws / King's Printer (confirm the address on bclaws.gov.bc.ca → Contact Us)
**Subject:** Request for permission to fetch BC statutes and point-in-time versions for a public version history

Hello,

I'm Alan Yahya at Lexifina. We are building a public version history of British Columbia statutes: each
consolidation recorded on the date it took effect, with each change credited to the amending Act named in the
history notes. The King's Printer Licence allows the text to be reproduced, and we would follow its attribution and
"not an official version" terms.

Your robots.txt admits only Googlebot and Bingbot, so we have not fetched any statute text. Could you either:
- allow our fetcher (user agent `lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)`; we can give
  our IP address) at a rate you choose, for example one request every few seconds outside business hours; or
- point us to a bulk route, such as the BC Laws API or an export of the statutes and point-in-time versions?

Everything is cached, so each file is fetched only once, and later updates would be small and incremental. Until we
hear from you, we will only publish the bill and assent facts from the Legislative Assembly.

Thank you,
Alan Yahya
Lexifina · alan@lexifina.com

---

## 6. Law and Judiciary Department, Government of Maharashtra: permission to reproduce the Act reprints

**To:** the Law and Judiciary Department (confirm the address on lj.maharashtra.gov.in → Contact / Website Policy)
**Subject:** Permission to reproduce Maharashtra Act reprints in a public version history

Hello,

I'm Alan Yahya at Lexifina. Your website policy says material may be reproduced free of charge after permission
is requested by email, so I'm writing to ask for it.

We are building a free public record of Maharashtra Acts. It holds the English "Reprint of the Act" text of each
principal Act, "as modified upto" the date on the reprint, along with a ledger of the amending Acts and commencement
dates printed in each reprint. The text would be reproduced accurately, with the source named, a link to
lj.maharashtra.gov.in, and a note that it is not an official copy. We fetched the reprint PDFs once each, at least
2 seconds apart, and cached them.

May we reproduce the reprints this way? Please tell us if you would like a different attribution or other conditions.

Thank you,
Alan Yahya
Lexifina · alan@lexifina.com

---

## 7. Law Department, Government of Himachal Pradesh: permission to reproduce the State Acts (English)

**To:** the Law Department, Himachal Pradesh, Web Information Manager (Addl. LR-cum-Additional Secretary (Law), H.P.
Secretariat, Shimla 171002, phone 0177-2880862; confirm the email address on himachal.nic.in/law → Contact Us)
**Subject:** Permission to reproduce Himachal Pradesh Acts (English) in a public version history

Hello,

I'm Alan Yahya at Lexifina. The Copyright Statement on himachal.nic.in says material may be reproduced free of charge
with the permission of the concerned owner organisation, so I'm writing to ask for it.

We are building a free public record of Himachal Pradesh Acts. It would hold the English text of each State Act as
published under "State Acts (English)" on the Law Department's pages (himachal.nic.in/law), including the list of
amending Acts and the footnotes printed in each, one section per file so that later amendments can be shown as
dated changes. The text would be reproduced accurately, with the Law Department named as the source, a link to
himachal.nic.in/law, and a note that it is not an official copy. We would fetch each PDF once, slowly, and cache it.

May we reproduce the Acts this way? Please tell us if you would like a different attribution or other conditions.

Thank you,
Alan Yahya
Lexifina · alan@lexifina.com

---

## 8. Government of Puducherry (Law Department / Directorate of Information Technology): permission to reproduce Acts

**To:** the Law Department, Government of Puducherry, copied to the web information manager of py.gov.in
(Directorate of Information Technology; confirm both addresses on py.gov.in → Contact Us / Department Contacts)
**Subject:** Permission to reproduce Puducherry Acts in a public version history

Hello,

I'm Alan Yahya at Lexifina. The Copyright Policy on py.gov.in says its contents may not be reproduced without due
permission from the Government of Puducherry, so I'm writing to ask for it.

We are building a free public record of the Acts of Puducherry: the English text of each Act as published by the
Government (for example the Acts and the Puducherry Code volumes under "Acts & Rules"), one section per file, so that
later amendments can be shown as dated changes. The text would be reproduced accurately, with the Government of
Puducherry named as the source, a link to py.gov.in, and a note that it is not an official copy. We would fetch each
file once, slowly, and cache it.

May we reproduce the Acts this way? If the Law Department keeps a consolidated (up-to-date) English edition of the
Puducherry Acts, we would also be grateful to know where to find it. Please tell us if you would like a different
attribution or other conditions.

Thank you,
Alan Yahya
Lexifina · alan@lexifina.com

---

## WalLex (Service public de Wallonie), for lexifina/belgium-wallonia-law

**To:** wallex.avis@spw.wallonie.be
**Subject:** Demande d'autorisation : réutilisation des textes coordonnés de WalLex

Madame, Monsieur,

Je suis Alan Yahya, de Lexifina. Nous publions gratuitement l'historique des textes de loi sous forme de dépôts
git publics : un fichier par article, une version par modification, datée du jour de son entrée en vigueur et
attribuée au texte modificatif. Nous aimerions faire de même pour les décrets de la Région wallonne, à partir des
versions coordonnées que publie WalLex (liens ELI avec date de version).

Vos mentions légales réservent à une autorisation préalable toute reproduction à caractère commercial. Lexifina
étant une société, nous vous demandons cette autorisation avant de reproduire quoi que ce soit. Nous citerions
WalLex et le SPW comme source sur chaque dépôt, avec le rappel que seul le texte publié au Moniteur belge fait foi.
Nous téléchargerions les textes une requête à la fois, à quelques secondes d'intervalle, et une seule fois.

Pourriez-vous nous dire si cette réutilisation est permise, et à quelles conditions ? Nous nous conformerons à
toute préférence de rythme ou de format (par exemple un export).

Je vous remercie par avance,
Alan Yahya, Lexifina (alan@lexifina.com)

---

## Consiglio regionale del Friuli Venezia Giulia (LEXVIEW), for lexifina/italy-friuli-venezia-giulia-law

**To:** consiglio@certregione.fvg.it (PEC; confirm a plain-mail address on www.consiglio.regione.fvg.it → Persone e uffici / redazione web)
**Subject:** Richiesta di autorizzazione: riproduzione dei testi delle leggi regionali da LEXVIEW / Permission to reproduce regional law texts

Gentili signore e signori,

sono Alan Yahya di Lexifina. Stiamo costruendo una storia delle versioni delle leggi regionali del Friuli Venezia
Giulia: ogni testo vigente e storico pubblicato in LEXVIEW (lexview-int.regione.fvg.it), un file per articolo, ogni
modifica datata al giorno di entrata in vigore e attribuita alla legge che l'ha disposta, in un repository pubblico
e gratuito (github.com/lexifina), con citazione della fonte e l'avvertenza che i testi non hanno valore legale.

Le note legali del sito chiedono un'autorizzazione preventiva per la riproduzione dei contenuti. I testi degli atti
ufficiali sono esclusi dalla protezione del diritto d'autore (L. 633/1941, art. 5), ma preferiamo chiedere prima di
pubblicare. Possiamo riprodurre i testi delle leggi regionali (e dello Statuto) tratti da LEXVIEW? Scaricheremmo una
pagina alla volta, a diversi secondi di distanza, e ci fermeremo subito se ce lo chiedete. Se preferite, un export
in blocco (XML/NIR) sarebbe ancora meglio.

(English: your legal notes ask for prior authorisation to reproduce site content. Official texts are outside
copyright under art. 5 of L. 633/1941, but we ask first: may we reproduce the regional law texts from LEXVIEW, free
and credited, fetched slowly?)

Cordiali saluti,
Alan Yahya
Lexifina · alan@lexifina.com

---

## Consiglio della Provincia autonoma di Trento (Codice provinciale), for lexifina/italy-trento-law

**To:** webmaster@consiglio.provincia.tn.it (named in the site's Note legali)
**Subject:** Richiesta di autorizzazione: riproduzione del Codice provinciale / Permission to reproduce the Codice provinciale

Gentili signore e signori,

sono Alan Yahya di Lexifina. Vorremmo pubblicare, gratuitamente e con citazione della fonte, una storia delle
versioni delle leggi provinciali di Trento: lo Statuto e le leggi provinciali vigenti, con i "testi precedenti" del
Codice provinciale, un file per articolo, ogni modifica datata al giorno di entrata in vigore e attribuita alla legge
che l'ha disposta (repository pubblico su github.com/lexifina, con l'avvertenza che i testi non hanno valore legale).

Le Note legali del sito vietano lo "scraping". I testi degli atti ufficiali sono esclusi dalla protezione del diritto
d'autore (L. 633/1941, art. 5), ma rispettiamo le vostre condizioni e chiediamo prima: possiamo scaricare i testi del
Codice provinciale in modo automatico, una pagina alla volta e a diversi secondi di distanza, oppure ottenere un
export in blocco? Ci fermeremo subito se ce lo chiedete.

(English: your legal notes forbid scraping. May we download the Codice provinciale texts automatically, slowly, or
receive a bulk export, to publish a free, credited version history?)

Cordiali saluti,
Alan Yahya
Lexifina · alan@lexifina.com

---

## Consiglio regionale della Lombardia (NormeLombardia), for lexifina/italy-lombardy-law

**To:** protocollo.generale@pec.consiglio.regione.lombardia.it (the address the Note legali give; confirm a non-PEC
contact for the Banca dati NormeLombardia on the Consiglio's contact page)
**Subject:** Richiesta di autorizzazione: riuso dei testi delle leggi regionali di NormeLombardia / Permission to reuse
the regional law texts

Buongiorno,

sono Alan Yahya di Lexifina. Stiamo costruendo una storia delle versioni delle leggi regionali italiane in un archivio
git pubblico e gratuito (un file per articolo, un commit per modifica, datato dal giorno di entrata in vigore e
attribuito alla legge che l'ha disposta), senza alcun uso commerciale dei testi.

Le Note legali del sito del Consiglio regionale dicono che la riproduzione dei contenuti senza autorizzazione è
vietata. Sappiamo che i testi degli atti ufficiali delle amministrazioni pubbliche sono esclusi dal diritto d'autore
(art. 5 della legge 22 aprile 1941, n. 633), ma preferiamo chiedere prima: possiamo riprodurre, con citazione della
fonte ("Consiglio Regionale della Lombardia, NormeLombardia" e URL), il testo vigente e i testi storici dello Statuto,
delle leggi regionali e dei regolamenti pubblicati in NormeLombardia?

Leggeremmo la banca dati una pagina alla volta, ad almeno qualche secondo di distanza, e una sola volta per testo.
Se preferite un altro canale (per esempio un export dei dati) o un altro ritmo, lo seguiremo. Ci fermeremo subito se
richiesto.

Grazie,
Alan Yahya
Lexifina · alan@lexifina.com

(English summary: asks permission to reproduce, with attribution and non-commercially, the current and historical
texts of the Statute, regional laws and regulations in NormeLombardia, since the Consiglio's legal notes forbid
reproduction without authorisation; offers a slow one-request-at-a-time fetch or a data export instead.)

## SAIJ (Sistema Argentino de Información Jurídica, Ministerio de Justicia), for the lexifina/argentina-<province>-law repos

**To:** the contact form at https://www.saij.gob.ar/contacto (no direct address found on the home page; check the
"Contacto" page for an e-mail of the Dirección Nacional del Sistema Argentino de Información Jurídica)
**Subject:** Solicitud de autorización: reutilización de los textos de legislación provincial publicados en SAIJ /
Permission to reuse the provincial legislation texts

Buenos días,

soy Alan Yahya, de Lexifina. Estamos construyendo, de forma pública y gratuita, una historia de versiones de la
legislación de las provincias argentinas y de la Ciudad Autónoma de Buenos Aires en repositorios git (un archivo por
artículo, un commit por norma, fechado el día de su entrada en vigencia), sin ningún uso comercial de los textos.

El Reglamento de uso de SAIJ (Anexo de la Resolución MJyDH N° 1427/2011) restringe la descarga de contenidos al uso
personal (Cláusula Segunda, b) y prohíbe reproducir o publicar la información del sitio y obtener sus contenidos por
otros medios (Cláusula Tercera, c y d). Por eso, antes de usar SAIJ, les pedimos autorización: ¿podemos reproducir,
citando la fuente ("SAIJ, Ministerio de Justicia de la Nación" y la URL de cada norma), el texto de las constituciones
y leyes provinciales que SAIJ publica, junto con sus datos (número, fechas de sanción, promulgación y publicación)?

Leeríamos el sitio de a una página por vez, con varios segundos entre pedidos, y una sola vez por texto; si prefieren
otro canal (por ejemplo, una exportación de datos) u otro ritmo, lo seguiremos. Nos detendremos de inmediato si así
lo solicitan.

Muchas gracias,
Alan Yahya
Lexifina · alan@lexifina.com

(English summary: SAIJ's usage regulation (Res. MJyDH 1427/2011, annex, clauses 2.b and 3.c-d) limits downloads to
personal use and forbids reproduction and obtaining content by other means; asks permission to reproduce provincial
constitutions and laws with attribution, non-commercially, with a slow fetch or a data export. Until a yes, the
provinces are built only from their own official portals.)

---

## Dubai Legislation Portal (General Secretariat of the Supreme Legislation Committee), for lexifina/uae-dubai-law (gitlaw-scraper-dell, 2026-10-30)

**To:** the contact form at https://dlp.dubai.gov.ae/en/Pages/ContactUs.aspx (confirm an e-mail address there)
**Subject:** Permission to republish the official English texts of Dubai legislation

Hello,

I'm Alan Yahya at Lexifina. We are building a free, public version history of Dubai legislation in a git
repository: one file per article, one commit per law, dated the day it came into force, with each change credited
to the law that made it. There is no commercial use of the texts.

The portal's Terms and Conditions ask for the Supreme Legislation Committee's express prior written consent before
any material is republished or made available to others, so we are asking before we use it: may we reproduce the
official English (and Arabic) texts of Dubai laws and decrees published on dlp.dubai.gov.ae, with their numbers and
dates, citing "Dubai Legislation Portal, Supreme Legislation Committee" and each text's URL? We note that Federal
Decree-Law No. 38 of 2021, art. 3, excludes laws and other official texts from copyright protection; we would still
rather have your agreement.

We would read the portal one page at a time, several seconds apart, and fetch each text only once. If you prefer a
data export, another channel or a different pace, we will follow it, and we will stop at once if you ask.

Many thanks,
Alan Yahya
Lexifina · alan@lexifina.com

---

## Marche: Consiglio regionale delle Marche, reuse of the regional law database

**To:** the Consiglio regionale delle Marche (confirm the address on consiglio.marche.it → Note legali / Contatti)
**Subject:** Richiesta di autorizzazione: riproduzione delle leggi regionali in un archivio pubblico delle versioni

Gentili Signore e Signori,

sono Alan Yahya di Lexifina. Stiamo costruendo un archivio pubblico e gratuito delle leggi regionali delle Marche:
lo Statuto e le leggi regionali nel testo vigente, ciascuna con la data di entrata in vigore e l'indicazione della
fonte (consiglio.marche.it), con l'avvertenza che non si tratta di un testo ufficiale.

Le note legali del sito consentono lo scaricamento delle pagine solo per uso personale e non commerciale. Gli atti
ufficiali non sono protetti (L. 633/1941, art. 5), ma desideriamo rispettare le vostre condizioni: possiamo
riprodurre i testi in questo modo? In caso contrario, ci indichi le condizioni che preferite; rimuoveremo i testi
se richiesto.

Abbiamo scaricato le pagine una sola volta ciascuna, una richiesta alla volta, e le conserviamo in cache.

Cordiali saluti,
Alan Yahya
Lexifina · alan@lexifina.com

---

## Nevis: Nevis Island Administration, reuse of the Nevis ordinances it publishes

**To:** the Nevis Island Administration, Legal Department (confirm the address on nia.gov.kn → Legal Services / Contact; the site lists webmaster@niagovkn.com)
**Subject:** Request for permission to reproduce Nevis ordinances in a free public version history

Hello,

I'm Alan Yahya at Lexifina. We are building a free, public version history of the law of Nevis: the ordinances of
the Nevis Island Assembly and the regulations made under them, each recorded with its date and credited to the
Nevis Island Administration as the source, with a note that it is not an official text.

nia.gov.kn publishes several ordinances as PDFs (for example the Nevis Offshore Banking Ordinance, 1996 as amended,
and the Nevis International Mutual Funds Ordinance, 2007). The site says "All Rights Reserved", and we could not find
an exclusion for legislation in the Copyright Act, 2024, so we would like your permission before reproducing them.
May we reproduce these texts in this way? If you prefer other conditions, or a different source such as a list of
the ordinances in force, please tell us; we will remove anything you ask us to.

We have read only a handful of pages, one request at a time, and published nothing.

Thank you,
Alan Yahya
Lexifina · alan@lexifina.com

---

## New Caledonia: Gouvernement de la Nouvelle-Calédonie (LégiNova), reuse of the consolidated lois du pays

**To:** contact.leginova@gouv.nc (the address in LégiNova's CGU, s. 2.2)
**Subject:** Demande d'autorisation : historique public et gratuit des lois du pays de Nouvelle-Calédonie

Bonjour,

Je m'appelle Alan Yahya, de Lexifina. Nous construisons un historique public et gratuit du droit de plusieurs
territoires, publié sous forme de dépôts git : un fichier par article, une version datée pour chaque texte
modificatif, à la date de son entrée en vigueur, avec la source citée et la mention qu'il ne s'agit pas d'une
publication officielle.

LégiNova publie les textes consolidés de la Nouvelle-Calédonie avec l'historique des modifications. Vos conditions
générales d'utilisation (s. 2.1) indiquent que les textes officiels sont librement réutilisables, mais la s. 2.2
soumet à une autorisation écrite préalable toute extraction ou réutilisation substantielle des contenus, la
constitution de bases de données éditoriales et la rediffusion en ligne. Nous souhaitons donc votre accord avant de
reprendre :

- les lois du pays et, si possible, les délibérations du Congrès, dans leurs versions consolidées successives ;
- en citant LégiNova (Gouvernement de la Nouvelle-Calédonie) comme source de chaque texte, avec lien.

Nous lirions les textes une seule fois chacun, une requête à la fois, à un rythme que vous pouvez fixer, et nous
retirerons tout ce que vous nous demanderez de retirer. Si vous préférez d'autres conditions ou un export, nous
nous y conformerons.

Nous n'avons consulté que quelques pages publiques (robots.txt, llms.txt, CGU) et n'avons rien publié.

Cordialement,
Alan Yahya
Lexifina · alan@lexifina.com

---

## US Virgin Islands: Legislature of the Virgin Islands, access to the Virgin Islands Code and Acts (gitlaw-scraper-dell, 2026-10-31)

**To:** the Legislature's contact address (confirm on www.legvi.org; the site answered our automated check with a Cloudflare challenge, so we could not read it)
**Subject:** Access to the text of the Virgin Islands Code and the Acts of the Legislature

Hello,

I'm Alan Yahya at Lexifina. We are building a public version history of the law of each US state and territory, with
each change recorded on the date it took effect and credited to the Act that made it. Guam and the Northern Mariana
Islands are already published this way from their legislatures' own sites.

For the Virgin Islands we could find the Code's text online only through a commercial publisher, and your own website
answered our one-request check with a Cloudflare bot challenge, which we do not get round. Statute text is not
subject to copyright (Georgia v. Public.Resource.Org, 2020); we would take the statute text only, never a publisher's
annotations.

Could you tell us whether the Legislature publishes the Code, or the Acts as passed, as files we may download (for
example a bulk export or a list of PDFs), and whether our fetcher may be allowed through at one request every few
seconds? We will keep to any rate or schedule you set, cache everything so each file is fetched once, and stop at
once if asked.

Thank you,
Alan Yahya
Lexifina

---

## Bangsamoro Parliament (BTA – Parliament), reuse of the Bangsamoro Autonomy Acts, for lexifina/philippines-bangsamoro-law (gitlaw-scraper-dell, 2026-10-31)

**To:** the address on https://parliament.bangsamoro.gov.ph/contact-us-3/ (confirm; the page hides it behind Cloudflare email protection)
**Subject:** Request for written permission to republish the Bangsamoro Autonomy Acts as a public version history

Hello,

I'm Alan Yahya at Lexifina. We publish the law of many jurisdictions as public, version-controlled histories: each law
as text files, one dated change per commit, credited to the law that made it, free for anyone to read.

We would like to add the Bangsamoro Autonomous Region: the Organic Law (Republic Act No. 11054) and the Bangsamoro
Autonomy Acts as published on parliament.bangsamoro.gov.ph. Your Terms of Use (s. 5) ask for prior written consent
before the site's contents are republished, so we are asking first. Specifically:

- Purpose: a free public record of Bangsamoro legislation, text unchanged, each Act credited to the BTA – Parliament
  with a link to its page on your site.
- Method: a one-time download of the Acts' pages and PDFs, one request at a time, several seconds apart, then only new
  Acts as they are published.
- Time frame: from your reply onwards.
- Identity: Lexifina (alan@lexifina.com).

We have downloaded nothing beyond your robots.txt, the home page and the Terms of Use, and will publish nothing until
you reply. If you prefer a different route (a bulk copy, or attribution wording), we will follow it.

Thank you,
Alan Yahya, Lexifina

---

## Kenya Law (National Council for Law Reporting), county legislation, for lexifina/kenya-<county>-law (gitlaw-scraper-dell, 2026-10-31)

**To:** info@kenyalaw.org (named in the Terms of Use, s. 2 and s. 4)
**Subject:** Licensing request: county legislation for a public, non-commercial version history

Hello,

I'm Alan Yahya at Lexifina. We publish the law of many jurisdictions as public version histories (one dated change per
commit, credited to the law that made it). We would like to cover Kenya's 47 counties from the county legislation
Kenya Law publishes under /legislation/counties (the /akn/ke-0NN/act/ pages).

Your Terms of Use (s. 4 and s. 9, notice of 12 October 2026) prohibit automated scraping and bulk extraction without an
explicit Licensing Agreement, and robots.txt sets Content-Signal ai-input=no, so we have fetched nothing from those
pages. Could you tell us whether NCLR would grant a licence, or provide county Acts in bulk or through your API, for
this purpose? We would credit NCLR on every Act and follow your preferred wording, rate and route.

Thank you,
Alan Yahya, Lexifina

## Bogotá D.C.: Secretaría Jurídica Distrital (Régimen Legal de Bogotá), reuse of the Acuerdos del Concejo and other district norms, for lexifina/colombia-bogota-law (gitlaw-scraper-dell, 2026-10-31)

**To:** the Secretaría Jurídica Distrital (contact form / correspondence address on secretariajuridica.gov.co; Régimen Legal de Bogotá, Dirección Distrital de Política Jurídica)
**Subject:** Solicitud de autorización: Acuerdos distritales del Régimen Legal de Bogotá para un historial público y gratuito / Permission request: Bogotá district norms for a free public version history

Buenos días / Hello,

I'm Alan Yahya at Lexifina. We publish the law of many jurisdictions as free public version histories (one dated change
per commit, credited to the norm that made it), and would like to cover Bogotá D.C.: Decreto Ley 1421 de 1993 and the
Acuerdos del Concejo de Bogotá, in the consolidated texts the Régimen Legal de Bogotá publishes
(alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp).

The laws themselves are free to reproduce (Ley 23 de 1982, art. 41), but the Términos y Condiciones of the Secretaría
Jurídica Distrital (section 5, "Propiedad intelectual y derechos reservados") require "autorización previa y expresa
por escrito" for any reproduction of the site's contents and databases, and allow copies only "para uso personal y no
comercial". The Registro Distrital's site (secretariageneral.gov.co, Términos y Condiciones 8.1) says the same. We have
therefore published nothing. Would the Secretaría authorise this use of the norm texts (we would take only the official
text and dates, not the notes or editorial content), and if so, at what rate and with what attribution?

Thank you / Gracias,
Alan Yahya, Lexifina

## Gobernación del Atlántico and Gobernación del Cauca (Colombia): reuse of the ordenanzas departamentales, for lexifina/colombia-atlantico-law and lexifina/colombia-cauca-law (gitlaw-scraper-dell, 2026-10-31)

**To:** each Gobernación's PQRSD / contact address (Atlántico: atlantico.gov.co; Cauca: cauca.gov.co)
**Subject:** Solicitud de autorización: ordenanzas departamentales para un historial público y gratuito / Permission request: departmental ordinances for a free public version history

Buenos días / Hello,

I'm Alan Yahya at Lexifina. We publish the law of many jurisdictions as free public version histories (one dated change
per commit, credited to the norm that made it) and would like to cover the department's ordenanzas departamentales,
taking only the official texts and their dates from the documents the Gobernación publishes.

Laws and other official acts may be reproduced freely in Colombia (Ley 23 de 1982, art. 41), but the site's terms
(Atlántico: Condiciones de Uso and Política de Derechos de Autor, which require "autorización previa y por escrito" and
allow only "uso personal y no comercial"; Cauca: Políticas de Privacidad y Condiciones de Uso, which forbid copying "a
múltiples usuarios sin el previo visto bueno del Departamento por medio escrito") ask for prior written permission, so
we have published nothing. Would the Gobernación authorise this use of the ordinance texts, and if so, at what request
rate and with what attribution?

Thank you / Gracias,
Alan Yahya, Lexifina

## "Territoriales" portals (MinTIC Dirección de Gobierno Digital / Agencia Nacional Digital): ordenanzas of Sucre, Caquetá, Arauca, Guaviare, Amazonas, Vichada, Guainía, Vaupés and the Asambleas of Tolima and Cundinamarca, for lexifina/colombia-<unit>-law (gitlaw-scraper-dell, 2026-10-31)

**To:** soporteccc@mintic.gov.co (the support address in each portal's "Condiciones de uso de la información"), copy to each entity's contact address if MinTIC says the permission is theirs to give
**Subject:** Solicitud de autorización: ordenanzas departamentales publicadas en los portales territoriales gov.co / Permission request: departmental ordinances on the gov.co territorial portals

Buenos días / Hello,

I'm Alan Yahya at Lexifina. We publish the law of many jurisdictions as free public version histories (one dated
change per commit, credited to the norm that made it) and would like to cover the ordenanzas departamentales of ten
entities whose sites run on the gov.co territorial portal platform: the Gobernaciones of Sucre, Caquetá, Arauca,
Guaviare, Amazonas, Vichada, Guainía and Vaupés, and the Asambleas Departamentales of Tolima and Cundinamarca. We would
take only the official texts of the ordinances and their dates, from the documents the entities publish, one request at
a time and several seconds apart.

Laws and other official acts, ordenanzas included, may be reproduced in Colombia (Ley 23 de 1982, art. 41). But each
portal's "Condiciones de uso de la información" (the same text on every site we checked, e.g. sucre.gov.co and
asambleatolima.gov.co, /informacion/condiciones-de-uso-informacion) says: "Queda en cambio prohibida la copia o
reproducción de los datos en cualquier medio electrónico (redes, bases de datos, cd rom, diskettes) que permita la
disponibilidad de esta información a múltiples usuarios sin el previo visto bueno de la entidad por medio escrito." We
have therefore published nothing. Could you tell us whether that clause is meant to cover the texts of the ordinances
themselves, and if so, whether MinTIC or each entity can give the written visto bueno for this use, at what request rate
and with what attribution?

Thank you / Gracias,
Alan Yahya, Lexifina

## Swiss cities (municipal tier): Stadt Luzern, Stadt St.Gallen, Ville de Lausanne, Ville de Genève, for lexifina/switzerland-<city>-city-law (gitlaw-scraper-dell, 2026-10-31)

Four drafts, one per city. Nothing published, no repo created for any of them.

### Stadt Luzern

**To:** kommunikation@stadtluzern.ch (address named in the Impressum), copy Stadtkanzlei
**Subject:** Anfrage: Wiedergabe der Systematischen Rechtssammlung (sRSL) / Request: reproducing the city's systematic collection

Guten Tag,

ich bin Alan Yahya von Lexifina. Wir veröffentlichen das Recht vieler Gemeinwesen als frei zugängliche
Versionsgeschichte (eine datierte Änderung pro Eintrag, mit dem ändernden Erlass als Urheber), darunter bereits das
Recht aller Kantone. Gerne würden wir die Systematische Rechtssammlung der Stadt Luzern aufnehmen: nur die amtlichen
Texte der Erlasse in der von der Stadt publizierten Fassung (PDF unter stadtluzern.ch/dokumentebilder/rechtssammlung),
abgerufen einzeln und mit mehreren Sekunden Abstand.

Gesetze, Verordnungen und andere amtliche Erlasse sind nach Art. 5 Abs. 1 lit. a URG urheberrechtlich nicht geschützt.
Das Impressum hält aber fest: "Für die Reproduktion jeglicher Elemente ist die schriftliche Zustimmung der
Urheberrechtsträger im Voraus einzuholen." Wir haben deshalb nichts veröffentlicht. Dürfen wir die Erlasstexte der sRSL
in dieser Form wiedergeben (mit Quellenangabe und dem Hinweis, dass nur die amtliche Publikation massgebend ist)?

Freundliche Grüsse
Alan Yahya, Lexifina

### Stadt St.Gallen

**To:** info@stadt.sg.ch (Rechtshinweise / Impressum), copy Stadtkanzlei (Rechtssammlung)
**Subject:** Anfrage: Wiedergabe der Systematischen Rechtssammlung der Stadt St.Gallen (st.gallen.tlex.ch)

Guten Tag,

ich bin Alan Yahya von Lexifina. Wir veröffentlichen das Recht vieler Gemeinwesen als frei zugängliche
Versionsgeschichte (jede konsolidierte Fassung am Tag ihres Inkrafttretens, mit dem ändernden Erlass als Urheber),
darunter bereits das Recht aller Kantone. Gerne würden wir die Systematische Rechtssammlung der Stadt St.Gallen
aufnehmen, wie sie die Stadt unter st.gallen.tlex.ch publiziert: nur die amtlichen Erlasstexte, einzeln und mit
mehreren Sekunden Abstand abgerufen.

Amtliche Erlasse sind nach Art. 5 Abs. 1 lit. a URG urheberrechtlich nicht geschützt. Die Rechtshinweise der Stadt
(stadt.sg.ch/f/impressum/rechtshinweise.html, gültig für sämtliche Webseiten der Stadt) sagen aber: "Ohne schriftliche
Zustimmung der Stadtverwaltung St.Gallen sind Reproduktionen, Einframen oder Kopieren von Inhalten der Website für
öffentliche oder kommerzielle Zwecke untersagt." Wir haben deshalb nichts veröffentlicht. Erlauben Sie die Wiedergabe der
Erlasstexte in dieser Form (mit Quellenangabe und dem Hinweis, dass nur die amtliche Publikation massgebend ist)?

Freundliche Grüsse
Alan Yahya, Lexifina

### Ville de Lausanne

**To:** the Secrétariat municipal (recueil systématique du droit communal), via the webmaster address on lausanne.ch
**Subject:** Demande d'autorisation : reproduction du recueil systématique du droit communal

Bonjour,

Je suis Alan Yahya, de Lexifina. Nous publions le droit de nombreuses collectivités sous forme d'historiques de versions
librement accessibles (une modification datée par entrée, attribuée à l'acte qui l'a faite), dont déjà le droit de tous
les cantons. Nous aimerions y ajouter le recueil systématique du droit communal de la Ville de Lausanne
(lausanne.ch/reglements) : uniquement les textes officiels des règlements, téléchargés un à un, à plusieurs secondes
d'intervalle.

Les lois, règlements et autres actes officiels ne sont pas protégés par le droit d'auteur (art. 5 al. 1 let. a LDA).
Les conditions générales d'utilisation du site (lausanne.ch/hors-arbo/cgu.html) précisent toutefois que "la
reproduction, la transmission, la modification ou l'utilisation à des fins publiques ou commerciales du site web de la
Ville de Lausanne [...] sont soumises à autorisation écrite préalable". Nous n'avons donc rien publié. Nous
autorisez-vous à reproduire les textes des règlements communaux de cette manière (avec mention de la source et
l'indication que seule la publication officielle fait foi) ?

Avec mes meilleures salutations,
Alan Yahya, Lexifina

### Ville de Genève

**To:** the Service juridique / Secrétariat du Conseil administratif, via geneve.ch (règlements municipaux)
**Subject:** Demande d'autorisation : reproduction des règlements municipaux de la Ville de Genève

Bonjour,

Je suis Alan Yahya, de Lexifina. Nous publions le droit de nombreuses collectivités sous forme d'historiques de versions
librement accessibles, dont déjà le droit du canton de Genève. Nous aimerions y ajouter les règlements municipaux de la
Ville de Genève (geneve.ch/autorites-administration/administration-municipale/reglements-municipaux) : uniquement les
textes officiels, téléchargés un à un, à plusieurs secondes d'intervalle.

Les lois, règlements et autres actes officiels ne sont pas protégés par le droit d'auteur (art. 5 al. 1 let. a LDA).
Les mentions légales du site (geneve.ch/mentions-legales) indiquent toutefois que "la reproduction, la transmission, la
modification ou l'utilisation à des fins publiques ou commerciales du contenu protégé par les droits d'auteur [...] sont
soumises à autorisation écrite préalable de la Ville de Genève". Nous n'avons donc rien publié. Pouvez-vous nous
confirmer que les textes des règlements municipaux peuvent être reproduits de cette manière (avec mention de la source
et l'indication que seule la publication officielle fait foi) ?

Avec mes meilleures salutations,
Alan Yahya, Lexifina

## Swiss towns on LexWork/tlex (municipal tier, wave 2), for lexifina/switzerland-<town>-city-law (gitlaw-scraper-dell, 2026-11-01)

Nothing published, no repo created, no request to the collection's API for any town below.

### Stadt Chur

**To:** the Stadtkanzlei Chur (Gesetzessammlung), via the contact form / address in the Impressum (www.chur.ch/impressum)
**Subject:** Anfrage: Wiedergabe der Gesetzessammlung der Stadt Chur (gesetzessammlung.chur.ch)

Guten Tag,

ich bin Alan Yahya von Lexifina. Wir veröffentlichen das Recht vieler Gemeinwesen als frei zugängliche
Versionsgeschichte (jede konsolidierte Fassung am Tag ihres Inkrafttretens, mit dem ändernden Erlass als Urheber),
darunter bereits das Recht aller Kantone. Gerne würden wir die Gesetzessammlung der Stadt Chur aufnehmen, wie sie die
Stadt unter gesetzessammlung.chur.ch publiziert: nur die amtlichen Erlasstexte, einzeln und mit mehreren Sekunden
Abstand abgerufen.

Amtliche Erlasse sind nach Art. 5 Abs. 1 lit. a URG urheberrechtlich nicht geschützt. Das Impressum der Stadt
(www.chur.ch/impressum) sagt aber: "Für die Reproduktion jeglicher Elemente ist die schriftliche Zustimmung der
Urheberrechtsträger im Voraus einzuholen." Wir haben deshalb nichts veröffentlicht. Erlauben Sie die Wiedergabe der
Erlasstexte in dieser Form (mit Quellenangabe und dem Hinweis, dass nur die amtliche Publikation massgebend ist)?

Freundliche Grüsse
Alan Yahya, Lexifina

## Câmara Municipal de Campina Grande (PB), for lexifina/brazil-campina-grande-city-law (gitlaw-scraper-dell, 2026-11-01)

Nothing published, no repo created; only robots.txt, the SAPL home page and the Câmara site's home and terms pages were read.

**To:** Câmara Municipal de Campina Grande, via the contact page of www.camaracg.pb.gov.br (Ouvidoria / Fale conosco)
**Subject:** Solicitação: reprodução dos textos das leis municipais publicados no SAPL (sapl.campinagrande.pb.leg.br)

Prezados senhores,

sou Alan Yahya, da Lexifina. Publicamos a legislação de muitos entes federativos como um histórico de versões aberto
(cada versão de uma lei no dia em que entrou em vigor, creditada ao ato que a deu), já incluindo vários municípios
brasileiros. Gostaríamos de incluir a Lei Orgânica e as leis municipais de Campina Grande tal como a Câmara as publica
no SAPL (sapl.campinagrande.pb.leg.br), consultando uma página por vez, com mais de 60 segundos de intervalo, conforme
o robots.txt.

Os textos de leis não são protegidos por direito autoral (Lei 9.610/1998, art. 8º, IV), e o rodapé do SAPL indica
"Conteúdo e dados sob licença Creative Commons 4.0 Atribuir Fonte - Compartilhar Igual". Os Termos de Uso do site da
Câmara (www.camaracg.pb.gov.br/termos-de-uso), porém, falam em "autorização prévia e expressa da Câmara Municipal de
Campina Grande" para reaproveitamento de conteúdo; por isso nada foi publicado. A Câmara autoriza a reprodução dos
textos das leis dessa forma, com indicação da fonte e a ressalva de que somente a publicação oficial tem valor legal?

Atenciosamente,
Alan Yahya, Lexifina

### Same request to the other towns on hold (one email each; text as for Chur, with the town's own clause quoted)

Nur die Ortsnamen, Adressen und zitierten Sätze ändern sich; der Text ist derselbe wie für Chur ("Gerne würden wir die
Systematische Rechtssammlung der Gemeinde <X> aufnehmen, wie sie die Gemeinde unter <host> publiziert [...]
Erlauben Sie die Wiedergabe der Erlasstexte in dieser Form (mit Quellenangabe und dem Hinweis, dass nur die amtliche
Publikation massgebend ist)?").

| Town | Collection | To (from the notice) | Clause quoted |
| --- | --- | --- | --- |
| Rapperswil-Jona | rapperswil-jona.tlex.ch | Stadtkanzlei, via www.rapperswil-jona.ch/impressum | "Für die Reproduktion jeglicher Elemente ist die schriftliche Zustimmung der Urheberrechtsträger im Voraus einzuholen." |
| Baar | baar.tlex.ch | gemeindebuero@baar.ch (Impressum) | same i-web sentence |
| Solothurn | reglemente.stadt-solothurn.ch | Stadtkanzlei (Impressum, www.stadt-solothurn.ch/impressum) | same i-web sentence |
| Muttenz | muttenz.tlex.ch | info@muttenz.ch | same i-web sentence |
| Cham | cham.tlex.ch | Gemeindekanzlei, via www.cham.ch/impressum | same i-web sentence |
| Neuheim | neuheim.tlex.ch | Gemeindekanzlei, via www.neuheim.ch/impressum | same i-web sentence |
| Domat/Ems | domat-ems.tlex.ch | Gemeindekanzlei, via www.domat-ems.ch/impressum | same i-web sentence |
| Bischofszell | bischofszell.tlex.ch | Stadtkanzlei, via www.bischofszell.ch/impressum | same i-web sentence |
| Aarburg | aarburg.tlex.ch | Bereich Zentrale Dienste (Impressum, www.aarburg.ch/impressum) | same i-web sentence |
| Spreitenbach | spreitenbach.tlex.ch | webmaster(at)spreitenbach.ch | "Jede vom Urheberrechtsgesetz nicht zugelassene Verwendung bedarf vorheriger schriftlicher Zustimmung der Gemeinde Spreitenbach. [...] Ausdrucke und Downloads von Websites dürfen nur für den persönlichen, privaten und nicht kommerziellen Gebrauch hergestellt werden." |
| Rheinfelden | rheinfelden.tlex.ch | Stadtkanzlei, via www.rheinfelden.ch/de/impressum/ | "Sämtliche Inhalte dieser Internetpräsenz (u.a. Texte, Grafiken und herunterladbare Dateien) sind urheberrechtlich geschützt. [...] nur nach schriftlicher Genehmigung durch den Betreiber oder den Rechteinhaber [...] vervielfältigt [...] werden." |

## Câmara Municipal de Parnamirim (RN), for lexifina/brazil-parnamirim-city-law (gitlaw-scraper-dell, 2026-11-01)

Nothing published, no repo created; only robots.txt, the SAPL home page and the Câmara site's home and terms pages were read.

**To:** Câmara Municipal de Parnamirim, via the contact page of camaraparnamirim.rn.gov.br (Ouvidoria / Fale conosco)
**Subject:** Solicitação: reprodução dos textos das leis municipais publicados no SAPL (sapl.parnamirim.rn.leg.br)

Prezados senhores,

sou Alan Yahya, da Lexifina. Publicamos a legislação de muitos entes federativos como um histórico de versões aberto
(cada versão de uma lei no dia em que entrou em vigor, creditada ao ato que a deu), já incluindo vários municípios
brasileiros. Gostaríamos de incluir a Lei Orgânica e as leis municipais de Parnamirim tal como a Câmara as publica no
SAPL (sapl.parnamirim.rn.leg.br), consultando uma página por vez, com mais de 60 segundos de intervalo, conforme o
robots.txt.

Os textos de leis não são protegidos por direito autoral (Lei 9.610/1998, art. 8º, IV), e o rodapé do SAPL indica
"Conteúdo e dados sob licença Creative Commons 4.0 Atribuir Fonte - Compartilhar Igual". Os Termos de Uso do portal da
Câmara (camaraparnamirim.rn.gov.br/termos-de-uso), porém, vedam "Reproduzir, distribuir ou modificar conteúdos do
portal sem autorização prévia" e o uso de "mecanismos automatizados (bots, scrapers) para coletar dados do portal sem
autorização"; por isso nada foi consultado além dessas páginas e nada foi publicado. A Câmara autoriza a consulta
automatizada e pausada do SAPL e a reprodução dos textos das leis dessa forma, com indicação da fonte e a ressalva de
que somente a publicação oficial tem valor legal?

Atenciosamente,
Alan Yahya, Lexifina

### Wave 3 (2026-11-01 evening): same request, same text as for Chur

| Town | Collection | To (from the notice) | Clause quoted |
| --- | --- | --- | --- |
| Oberrieden | oberrieden.tlex.ch | Gemeindeverwaltung, via www.oberrieden.ch/impressum | i-web: "Für die Reproduktion jeglicher Elemente ist die schriftliche Zustimmung der Urheberrechtsträger im Voraus einzuholen." |
| Sissach | sissach.tlex.ch | via www.sissach.ch/impressum | same i-web sentence |
| Bonaduz | bonaduz.tlex.ch | via www.bonaduz.ch/impressum/ | same sentence |
| Nidau | nidau.tlex.ch | Stadtkanzlei, via www.nidau.ch/de/impressum/ | "Sämtliche Inhalte dieser Internetpräsenz (u.a. Texte, Grafiken und herunterladbare Dateien) sind urheberrechtlich geschützt. [...] nur nach schriftlicher Genehmigung [...]" (www.nidau.ch/de/datenschutz/nutzungsbedingungen.php) |
| Arlesheim | arlesheim.tlex.ch | via www.arlesheim.ch/de/impressum/ | same Talus sentence (nutzungsbedingungen.php) |
| Birsfelden | birsfelden.tlex.ch | Gemeindeverwaltung (Impressum, www.birsfelden.ch/de/impressum/) | same Talus sentence (www.birsfelden.ch/de/datenschutz/, section 1.2) |

## Kota Padang, Indonesia: JDIH Kota Padang (gitlaw-scraper-dell, 2026-11-01, kota/kabupaten tier) — HOLD, draft only, not sent

To: Bagian Hukum Sekretariat Daerah Kota Padang (contact on jdih.padang.go.id). Clause (jdih.padang.go.id/syarat-ketentuan, section 2):
"Anda dapat mengunduh atau mencetak konten dari situs web ini hanya untuk penggunaan pribadi, non-komersial Anda, dengan
ketentuan bahwa Anda tidak mengubah konten [...]". Only robots.txt, the home page and the terms page were read; nothing published.

Yth. Bagian Hukum Sekretariat Daerah Kota Padang,

Saya Alan Yahya dari Lexifina. Kami menerbitkan peraturan daerah dari banyak provinsi dan kabupaten/kota di Indonesia
sebagai riwayat versi yang terbuka (setiap Peraturan Daerah sebagaimana ditetapkan, bertanggal sesuai hari mulai
berlakunya, dengan sumber JDIH dicantumkan). Kami ingin memasukkan Peraturan Daerah Kota Padang sebagaimana diterbitkan
di jdih.padang.go.id, dengan mengakses satu halaman setiap kali dan dengan jeda beberapa detik.

Menurut Undang-Undang Nomor 28 Tahun 2014 tentang Hak Cipta, Pasal 42 huruf b, tidak ada hak cipta atas peraturan
perundang-undangan. Namun Syarat dan Ketentuan situs menyatakan bahwa konten hanya boleh diunduh "untuk penggunaan
pribadi, non-komersial", sehingga kami belum mengambil atau menerbitkan apa pun. Apakah Bagian Hukum mengizinkan
pengambilan otomatis secara perlahan dan penerbitan ulang teks Peraturan Daerah tersebut tanpa perubahan isi, dengan
mencantumkan sumbernya dan keterangan bahwa hanya naskah resmi yang berlaku?

Hormat kami,
Alan Yahya, Lexifina
