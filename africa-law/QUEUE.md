# Countries waiting for an agent slot

The cap is 20 concurrent subagents, set by CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS. Start the next country here each time an agent finishes, and tick it off. Each agent follows `scripts/africa-law/FANOUT.md`. Use at most 4 WebSearch calls each.

| Done | Code | Slug | tz | Language | Future branch | On-date tool | Sources | Phase 1 |
|---|---|---|---|---|---|---|---|---|
| [x] | LR | liberia | Africa/Monrovia | en | future | on.py | Government and legislature; any LII via Wayback; the Liberian Codes | 1986 Constitution (amended 2011) + 2 core acts |
| [x] | SS | south-sudan | Africa/Juba | en | future | on.py | Parliament or ministry of justice text PDFs | Transitional Constitution 2011 with its amendments + 2 core acts |
| [x] | SN | senegal | Africa/Dakar | fr | futur | en_vigueur_au | Journal Officiel (jo.gouv.sn), Secrétariat général du gouvernement | 2001 Constitution with its constitutional laws (2016, 2019), Code pénal, Loi 2008-12 on personal data |
| [x] | CI | cote-divoire | Africa/Abidjan | fr | futur | en_vigueur_au | Journal Officiel, SGG, Conseil constitutionnel | 2016 Constitution (2020 revision), 2019 Code pénal, Loi 2013-450 |
| [x] | CM | cameroon | Africa/Douala | en + fr (bilingual; English where an official text exists) | future | on.py | Presidency (prc.cm), Assemblée nationale, Journal Officiel | 1972 Constitution as revised 1996 and 2008, 2016 Penal Code, 2024 personal data law |
| [x] | MG | madagascar | Indian/Antananarivo | fr | futur | en_vigueur_au | Journal Officiel, Haute Cour constitutionnelle | 2010 Constitution, Loi 2014-038, Code pénal |
| [x] | MZ | mozambique | Africa/Maputo | pt | futuro | vigente_em | Boletim da República, Assembleia da República, Conselho Constitucional | 2004 Constitution (revised 2018, 2023), 2019 Código Penal, Lei de Transacções Electrónicas |
| [x] | AO | angola | Africa/Luanda | pt | futuro | vigente_em | Diário da República, Assembleia Nacional, Tribunal Constitucional | 2010 Constitution (2021 revision), 2020 Código Penal, Lei 22/11 |
| [x] | CV | cabo-verde | Atlantic/Cape_Verde | pt | futuro | vigente_em | Boletim Oficial (kiosk.incv.cv), Parlamento | 1992 Constitution (revised 1999, 2010), Código Penal, Lei 133/V/2001 |

| [x] | BF | burkina-faso | Africa/Ouagadougou | fr | futur | en_vigueur_au | Journal Officiel, SGG, Conseil constitutionnel | 1991 Constitution (amended) / current charter, Code pénal 2018, Loi 001-2021 on personal data |
| [x] | ML | mali | Africa/Bamako | fr | futur | en_vigueur_au | Journal Officiel, SGG, Cour constitutionnelle | 2023 Constitution, Code pénal 2024, Loi 2013-015 on personal data |
| [x] | BJ | benin | Africa/Porto-Novo | fr | futur | en_vigueur_au | Journal Officiel, SGG (sgg.gouv.bj), Cour constitutionnelle | 1990 Constitution (revised 2019), Code du numérique 2017, Code pénal 2018 |
| [x] | TG | togo | Africa/Lome | fr | futur | en_vigueur_au | Journal Officiel, Assemblée nationale | 2024 Constitution (1992 with revisions before it), Code pénal 2015, Loi 2019-014 on personal data |
| [x] | GN | guinea | Africa/Conakry | fr | futur | en_vigueur_au | Journal Officiel, SGG | 2020 Constitution / 2025 Constitution, Code pénal 2016, Loi L/2016/037 |
| [x] | CD | dr-congo | Africa/Kinshasa | fr | futur | en_vigueur_au | Journal Officiel (journalofficiel.cd), Leganet.cd | 2006 Constitution (revised 2011), Code pénal, Code du numérique 2023 |

French- and Portuguese-language READMEs are English first, then the country's language.
