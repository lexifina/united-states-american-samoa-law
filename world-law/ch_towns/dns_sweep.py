"""DNS-only sweep for <name>.tlex.ch (no request to any host). Swiss municipalities above about 5,000 inhabitants,
German / French / Italian names, with spelling variants. Prints: name host ip.  Private.

    python -I -X utf8 dns_sweep.py > dns-hits.txt
"""
import socket
import unicodedata
import re

TOWNS = """
Zürich|Genève|Genf|Basel|Lausanne|Bern|Winterthur|Luzern|Lucerne|St. Gallen|Lugano|Biel/Bienne|Biel-Bienne|Thun|Köniz|La Chaux-de-Fonds|Fribourg|Freiburg|Schaffhausen|Chur|Vernier|Uster|Sion|Sitten|Neuchâtel|Lancy|Zug|Emmen|Yverdon-les-Bains|Kriens|Rapperswil-Jona|Dübendorf|Dietikon|Montreux|Frauenfeld|Wetzikon|Baar|Riehen|Meyrin|Wädenswil|Wettingen|Carouge|Renens|Bulle|Allschwil|Kreuzlingen|Aarau|Horgen|Nyon|Reinach|Vevey|Kloten|Baden|Wil|Adliswil|Volketswil|Schlieren|Bellinzona|Opfikon|Onex|Olten|Ostermundigen|Pully|Thalwil|Gossau|Muttenz|Monthey|Burgdorf|Martigny|Steffisburg|Littau|Grenchen|Sierre|Siders|Solothurn|Herisau|Wohlen|Morges|Pratteln|Locarno|Cham|Spiez|Schwyz|Langenthal|Binningen|Einsiedeln|Thônex|Le Grand-Saconnex|Arbon|Mendrisio|Ebikon|Stäfa|Küsnacht|Regensdorf|Muri bei Bern|Meilen|Lyss|Wallisellen|Liestal|Delémont|Delsberg|Horw|Illnau-Effretikon|Bülach|Versoix|Freienbach|Brig-Glis|Naters|Visp|Oftringen|Chêne-Bougeries|Zollikon|Ecublens|Prilly|Gland|Rheinfelden|Spreitenbach|Hinwil|Wangen-Brüttisellen|Pfäffikon|Rüti|Davos|Ittigen|Neuhausen am Rheinfall|Neuhausen|Wettswil|Weinfelden|Amriswil|Romanshorn|Uzwil|Flawil|Altstätten|Buchs|Rorschach|Goldach|Wittenbach|Gossau SG|Zuchwil|Bassersdorf|Richterswil|Maur|Uetikon am See|Männedorf|Hombrechtikon|Egg|Fällanden|Greifensee|Schwerzenbach|Dübendorf|Wädenswil|Affoltern am Albis|Affoltern|Birmensdorf|Urdorf|Oberengstringen|Geroldswil|Unterengstringen|Dielsdorf|Niederhasli|Embrach|Bülach|Eglisau|Rafz|Winkel|Kloten|Bassersdorf|Nürensdorf|Dietlikon|Wangen|Fehraltorf|Russikon|Uster|Volketswil|Gossau ZH|Grüningen|Bubikon|Dürnten|Wald|Fischenthal|Bauma|Turbenthal|Seuzach|Neftenbach|Elgg|Wiesendangen|Hettlingen|Dinhard|Andelfingen|Zollikerberg|Herrliberg|Erlenbach|Kilchberg|Rüschlikon|Langnau am Albis|Oberrieden|Hirzel|Schönenberg|Hausen am Albis|Mettmenstetten|Obfelden|Ottenbach|Hedingen|Bonstetten|Stallikon|Uitikon|Aesch|Dällikon|Buchs ZH|Otelfingen|Boppelsen|Regensberg|Steinmaur|Schöfflisdorf|Oberglatt|Rümlang|Höri|Hochfelden|Glattfelden|Bachenbülach|Winterthur|Pfungen|Embrach|Brütten|Lindau|Illnau|Effretikon|Kyburg
Köniz|Ostermundigen|Bolligen|Ittigen|Zollikofen|Münchenbuchsee|Moosseedorf|Urtenen-Schönbühl|Jegenstorf|Kirchberg|Belp|Münsingen|Worb|Muri|Kehrsatz|Wohlen bei Bern|Frauenkappelen|Laupen|Neuenegg|Schwarzenburg|Konolfingen|Langnau im Emmental|Langnau|Huttwil|Herzogenbuchsee|Langenthal|Roggwil|Aarberg|Lyss|Nidau|Ipsach|Brügg|Studen|Pieterlen|Lengnau|Moutier|Tramelan|Saint-Imier|Saint-Imier|Tavannes|Reconvilier|Valbirse|Interlaken|Unterseen|Matten|Frutigen|Spiez|Wimmis|Zweisimmen|Saanen|Meiringen|Brienz|Heimberg|Hilterfingen|Oberhofen|Uetendorf|Uttigen|Steffisburg|Sigriswil|Burgdorf|Hasle|Lützelflüh|Sumiswald|Wynigen|Oberburg|Kirchberg BE|Utzenstorf|Bätterkinden|Langenthal|Madiswil|Thunstetten|Wangen an der Aare|Niederbipp|Oberbipp
Luzern|Emmen|Kriens|Horw|Ebikon|Adligenswil|Meggen|Root|Dierikon|Buchrain|Inwil|Rothenburg|Neuenkirch|Sempach|Hochdorf|Hitzkirch|Sursee|Oberkirch|Nottwil|Ruswil|Wolhusen|Willisau|Dagmersellen|Reiden|Triengen|Schötz|Entlebuch|Schüpfheim|Escholzmatt-Marbach|Malters|Weggis|Vitznau|Greppen|Küssnacht|Küssnacht am Rigi|Arth|Steinen|Ingenbohl|Brunnen|Schwyz|Lachen|Altendorf|Galgenen|Wollerau|Feusisberg|Freienbach|Einsiedeln|Muotathal|Altdorf|Schattdorf|Bürglen|Erstfeld|Flüelen|Sarnen|Kerns|Alpnach|Sachseln|Engelberg|Stans|Hergiswil|Buochs|Ennetbürgen|Stansstad|Beckenried|Glarus|Glarus Nord|Glarus Süd|Näfels|Zug|Baar|Cham|Steinhausen|Risch|Hünenberg|Unterägeri|Oberägeri|Menzingen|Walchwil|Neuheim
Fribourg|Bulle|Villars-sur-Glâne|Marly|Düdingen|Guin|Murten|Morat|Estavayer|Estavayer-le-Lac|Romont|Châtel-Saint-Denis|Wünnewil-Flamatt|Tafers|Kerzers|Givisiez|Granges-Paccot|Belfaux|Courtepin|Gruyères|Riaz|Le Mouret|Gibloux|Hauterive|Avry|Neyruz|Corminboeuf|Plaffeien|Schmitten|Ueberstorf|Bösingen|Mont-Vully|Cheyres-Châbles|Broc|Attalens|Ursy|Vuisternens-devant-Romont|La Sonnaz|Matran|Prez|Pont-en-Ogoz
Solothurn|Grenchen|Olten|Zuchwil|Biberist|Derendingen|Gerlafingen|Bellach|Langendorf|Bettlach|Dornach|Breitenbach|Balsthal|Oensingen|Trimbach|Wangen bei Olten|Hägendorf|Egerkingen|Schönenwerd|Dulliken|Däniken|Lostorf|Niedergösgen|Obergösgen|Subingen|Lohn-Ammannsegg|Riedholz|Feldbrunnen|Selzach|Lengnau
Basel|Riehen|Bettingen|Allschwil|Reinach|Muttenz|Pratteln|Binningen|Münchenstein|Oberwil|Birsfelden|Aesch|Liestal|Therwil|Arlesheim|Bottmingen|Sissach|Frenkendorf|Gelterkinden|Laufen|Zwingen|Ettingen|Pfeffingen|Füllinsdorf|Lausen|Waldenburg|Muttenz
Schaffhausen|Neuhausen am Rheinfall|Thayngen|Stein am Rhein|Beringen|Hallau|Neunkirch|Löhningen
Appenzell|Herisau|Teufen|Heiden|Speicher|Gais|Trogen|Urnäsch|Waldstatt|Walzenhausen|Bühler|Rehetobel|Wolfhalden|Oberegg
St. Gallen|Rapperswil-Jona|Wil|Gossau|Uzwil|Altstätten|Buchs|Flawil|Rorschach|Goldach|Wittenbach|Jona|Rapperswil|Wattwil|Widnau|Diepoldsau|Au|Berneck|Balgach|Heerbrugg|Oberriet|Rüthi|Sennwald|Gams|Grabs|Sevelen|Wartau|Sargans|Mels|Flums|Walenstadt|Bad Ragaz|Pfäfers|Vilters-Wangs|Quarten|Amden|Weesen|Schänis|Benken|Kaltbrunn|Uznach|Schmerikon|Eschenbach|Gommiswald|Ebnat-Kappel|Neckertal|Lichtensteig|Bütschwil-Ganterschwil|Kirchberg SG|Jonschwil|Oberuzwil|Zuzwil|Niederbüren|Oberbüren|Niederhelfenschwil|Waldkirch|Gaiserwald|Andwil|Gossau|Mörschwil|Tübach|Rorschacherberg|Thal|Rheineck|St. Margrethen|Untereggen|Eggersriet|Muolen|Häggenschwil|Berg|Steinach|Degersheim|Mogelsberg|Wil SG
Chur|Davos|Landquart|Domat/Ems|Domat-Ems|Ems|Igis|Zizers|Trimmis|Untervaz|Maienfeld|Malans|Grüsch|Schiers|Klosters|Klosters-Serneus|Arosa|Lenzerheide|Vaz/Obervaz|Vaz-Obervaz|Thusis|Cazis|Domleschg|Ilanz|Ilanz/Glion|Ilanz-Glion|Flims|Laax|Trin|Bonaduz|Rhäzüns|Tamins|Felsberg|St. Moritz|Samedan|Pontresina|Celerina|Scuol|Zernez|Poschiavo|Roveredo|Mesocco|Disentis|Val Müstair|Bregaglia|Surses|Albula|Bergün
Aarau|Baden|Wettingen|Wohlen|Rheinfelden|Spreitenbach|Oftringen|Zofingen|Brugg|Lenzburg|Möhlin|Neuenhof|Suhr|Obersiggenthal|Buchs AG|Bremgarten|Muri|Aarburg|Windisch|Würenlos|Ennetbaden|Wettingen|Rothrist|Strengelbach|Kölliken|Safenwil|Reinach AG|Menziken|Beinwil am See|Seon|Seengen|Hallwil|Lenzburg|Niederlenz|Staufen|Möriken-Wildegg|Hunzenschwil|Rupperswil|Schafisheim|Buchs|Gränichen|Küttigen|Erlinsbach|Unterentfelden|Oberentfelden|Teufenthal|Villmergen|Dottikon|Sarmenstorf|Fahrwangen|Dintikon|Hendschiken|Othmarsingen|Mägenwil|Mellingen|Wohlenschwil|Niederrohrdorf|Oberrohrdorf|Fislisbach|Birmenstorf|Gebenstorf|Turgi|Untersiggenthal|Freienwil|Nussbaumen|Ehrendingen|Döttingen|Klingnau|Bad Zurzach|Zurzach|Leibstadt|Leuggern|Kaiseraugst|Frick|Laufenburg|Stein|Sisseln|Eiken|Wallbach|Magden|Mumpf|Zeiningen|Rheinfelden|Bergdietikon|Berikon|Widen|Rudolfstetten-Friedlisberg|Oberwil-Lieli|Zufikon|Unterlunkhofen|Hägglingen|Villigen|Remigen|Riniken|Umiken|Lupfig|Birr|Schinznach|Holderbank|Auenstein|Veltheim|Wildegg|Merenschwand|Sins|Oberrüti|Dietwil|Abtwil|Muri AG|Boswil|Bünzen|Besenbüren|Waltenschwil|Wohlen AG|Villmergen|Niederwil|Fischbach-Göslikon|Künten|Stetten|Bellikon|Remetschwil|Killwangen|Würenlingen
Frauenfeld|Kreuzlingen|Arbon|Amriswil|Weinfelden|Romanshorn|Aadorf|Sirnach|Münchwilen|Bischofszell|Sulgen|Kradolf-Schönenberg|Bürglen TG|Berg TG|Egnach|Steckborn|Diessenhofen|Eschlikon|Wängi|Tobel-Tägerschen|Affeltrangen|Matzingen|Stettfurt|Thundorf|Felben-Wellhausen|Hüttlingen|Müllheim|Pfyn|Frauenfeld|Gachnang|Uesslingen-Buch|Wigoltingen|Tägerwilen|Gottlieben|Ermatingen|Münsterlingen|Bottighofen|Altnau|Langrickenbach|Güttingen|Kesswil|Uttwil|Salmsach|Horn|Roggwil TG|Erlen|Zihlschlacht-Sitterdorf|Hauptwil-Gottshaus|Hohentannen|Neukirch an der Thur|Fischingen|Bettwiesen|Lommis|Wilen|Rickenbach|Wuppenau
Lausanne|Yverdon-les-Bains|Montreux|Renens|Nyon|Vevey|Pully|Morges|Gland|Ecublens|Prilly|La Tour-de-Peilz|Bussigny|Aigle|Payerne|Le Mont-sur-Lausanne|Epalinges|Crissier|Lutry|Chavannes-près-Renens|Bex|Ollon|Blonay|Saint-Légier|Blonay-Saint-Légier|Moudon|Echallens|Lucens|Avenches|Orbe|Vallorbe|Sainte-Croix|Grandson|Rolle|Coppet|Founex|Prangins|Saint-Prex|Etoy|Aubonne|Préverenges|Saint-Sulpice|Chexbres|Bourg-en-Lavaux|Savigny|Cugy|Belmont-sur-Lausanne|Paudex|Jouxtens-Mézery|Romanel-sur-Lausanne|Cheseaux-sur-Lausanne|Penthalaz|Cossonay|Penthaz|Villeneuve|Leysin|Château-d'Oex|Le Chenit|Oron|Jorat-Mézières|Mézières|Savigny|Puidoux|Corsier-sur-Vevey|Corseaux|Jongny|Chardonne|Saint-Saphorin|Chavornay|Yvonand|Concise|Penthéréaz|Bercher|Assens|Bottens|Froideville|Le Mont|Mont-sur-Rolle|Nyon|Trélex|Genolier|Begnins|Eysins|Crans|Commugny|Mies|Tannay|Chéserex|Gingins|Arzier-Le Muids|Saint-Cergue|Duillier|Coinsins|Vich|Gilly|Bursins|Tolochenaz|Lonay|Echandens|Denges|Lussy-sur-Morges|Vufflens-le-Château|Bremblens|Romanel-sur-Morges|Vaux-sur-Morges|Apples|Bière|Gimel|Montricher|L'Isle|La Sarraz|Eclépens|Orny|Pompaples|Croy|Romainmôtier
Genève|Vernier|Lancy|Meyrin|Carouge|Onex|Thônex|Versoix|Le Grand-Saconnex|Grand-Saconnex|Chêne-Bougeries|Plan-les-Ouates|Bernex|Veyrier|Chêne-Bourg|Collonge-Bellerive|Cologny|Bellevue|Pregny-Chambésy|Satigny|Confignon|Troinex|Puplinge|Vandoeuvres|Genthod|Collex-Bossy|Anières|Hermance|Corsier|Choulex|Presinge|Jussy|Gy|Meinier|Perly-Certoux|Bardonnex|Plan-les-Ouates|Avully|Chancy|Cartigny|Avusy|Aire-la-Ville|Russin|Dardagny
Sion|Sierre|Martigny|Monthey|Brig-Glis|Naters|Visp|Conthey|Collombey-Muraz|Bagnes|Val de Bagnes|Savièse|Fully|Crans-Montana|Saxon|Saint-Maurice|Vouvry|Port-Valais|Ayent|Nendaz|Chalais|Grône|Vétroz|Ardon|Chamoson|Leytron|Riddes|Saillon|Vernayaz|Salvan|Evionnaz|Massongex|Troistorrents|Val-d'Illiez|Champéry|Zermatt|Saas-Fee|Leuk|Leukerbad|Gampel-Bratsch|Steg-Hohtenn|Raron|Zermatt|Stalden|St. Niklaus|Termen|Ried-Brig|Mörel-Filet|Fiesch|Goms|Anniviers|Hérens|Evolène|Vex|Mont-Noble|Nax|Veyras|Miège|Venthône|Noble-Contrée|Salquenen|Salgesch|Varen|Lens|Icogne|Arbaz|Grimisuat|Savièse|Saint-Léonard|Orsières|Sembrancher|Bovernier|Martigny-Combe|Trient|Finhaut|Liddes|Bourg-Saint-Pierre
Neuchâtel|La Chaux-de-Fonds|Le Locle|Val-de-Travers|Val-de-Ruz|Milvignes|Boudry|Peseux|Corcelles-Cormondrèche|Cortaillod|Bevaix|Saint-Blaise|Hauterive|Marin-Epagnier|La Tène|Le Landeron|Cressier|Cornaux|Enges|Lignières|La Grande Béroche|Rochefort|Brot-Plamboz|Les Ponts-de-Martel|La Sagne|Les Brenets|Le Cerneux-Péquignot|La Brévine|La Chaux-du-Milieu|Le Val-de-Travers
Delémont|Porrentruy|Haute-Sorne|Val Terbi|Courrendlin|Saignelégier|Fontenais|Alle|Courgenay|Bassecourt|Clos du Doubs|Courroux|Soyhières|Develier|Courtételle|Rossemaison|Châtillon|Vicques|Haute-Ajoie|Basse-Allaine|La Baroche|Coeuve|Damphreux|Les Breuleux|Le Noirmont|Les Bois
Lugano|Bellinzona|Locarno|Mendrisio|Chiasso|Minusio|Biasca|Muralto|Ascona|Losone|Capriasca|Collina d'Oro|Massagno|Savosa|Sorengo|Porza|Canobbio|Paradiso|Melide|Morcote|Bissone|Maroggia|Melano|Mezzovico-Vira|Monteceneri|Gambarogno|Tenero-Contra|Gordola|Lavertezzo|Cugnasco-Gerra|Terre di Pedemonte|Centovalli|Onsernone|Maggia|Avegno Gordevio|Vallemaggia|Riviera|Serravalle|Blenio|Acquarossa|Faido|Airolo|Quinto|Giornico|Bodio|Pollegio|Personico|Arbedo-Castione|Lumino|Sant'Antonino|Cadenazzo|Balerna|Coldrerio|Novazzano|Stabio|Genestrerio|Ligornetto|Riva San Vitale|Vacallo|Morbio Inferiore|Morbio Superiore|Breggia|Castel San Pietro|Agno|Bioggio|Manno|Lamone|Cadempino|Origlio|Ponte Capriasca|Torricella-Taverne|Bedano|Gravesano|Grancia|Lugaggia|Caslano|Ponte Tresa|Magliaso|Neggio|Pura|Croglio|Monteggio|Sessa|Astano|Curio|Bedigliora|Novaggio|Miglieglia|Alto Malcantone|Aranno|Cademario|Vernate|Muzzano|Breganzona|Viganello|Pregassona|Davesco-Soragno|Cureglia|Comano|Vezia|Lugano-Paradiso
"""


def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def variants(name: str) -> set[str]:
    out = set()
    base = name.strip()
    base = re.sub(r'\s+(ZH|BE|SG|AG|TG|SO)$', '', base)       # canton suffix used only to tell homonyms apart
    for n in {base, base.replace('St. ', 'Sankt '), base.replace('St. ', 'St.'), base.replace('Saint-', 'St-')}:
        low = n.lower()
        for u in (low.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue'), fold(low)):
            u = u.replace("'", '').replace('’', '')
            for sep in ('-', ''):
                v = re.sub(r'[\s/.]+', sep, u).strip('-')
                v = re.sub(r'-+', '-', v)
                if v:
                    out.add(v)
            # dotted host like st.gallen.tlex.ch
            if '. ' in u:
                out.add(re.sub(r'\s+', '', u))
    return out


def main():
    seen = set()
    names = [x for x in re.split(r'[|\n]', TOWNS) if x.strip()]
    for name in names:
        for v in sorted(variants(name)):
            if v in seen:
                continue
            seen.add(v)
            h = f'{v}.tlex.ch'
            try:
                ip = socket.gethostbyname(h)
            except OSError:
                continue
            print(f'{name.strip()}\t{h}\t{ip}', flush=True)


if __name__ == '__main__':
    main()
