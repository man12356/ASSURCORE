-- ============================================================
-- Import insurance_journal_enc depuis PRIORITE_ENV_FACT_COMP
-- 12 journees d'encaissement — 764375.243 TND total
-- ============================================================

BEGIN;

-- Compagnie: BH ASSU (5 factures, 176264.377 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('BH ASSU', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    176264.377,
    176264.377,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22041 | MOHAMED HADJ TAIEB | 5017.897 TND
  N22438 | STE SOCOBAT | 155600.052 TND
  N22553 | KHALED ABBOU | 5324.372 TND
  N22567 | STE STAC | 1836.856 TND
  N22795 | STE SOMEDEN | 8485.200 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('BH ASSU'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: LLOYD (112 factures, 148931.668 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('LLOYD', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    148931.668,
    148931.668,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22030 | HANNACHI EP BEN TEMIME WISSAL | 599.700 TND
  N22045 | STE MEDTCO | 13048.331 TND
  N22052 | HADJ SALEM HECHMI | 174.293 TND
  N22063 | STE OFFICE PLAST | 872.290 TND
  N22078 | HAMMAMI KAOUTHER | 1237.058 TND
  N22082 | HAJJEM MAHER | 78.126 TND
  N22127 | LAZHARI EP BEN EZZEDDINE MOHSN | 2484.743 TND
  N22152 | BANNOURI MOHAMED | 1234.528 TND
  N22312 | KHZEMA MARIEM | 752.784 TND
  N22315 | KAMMOUN AMIRA | 969.727 TND
  N22322 | GHANOUCHI SOUHEIL | 573.672 TND
  N22324 | AKKERI KHAOULA | 576.544 TND
  N22325 | HIDRI DHOUHA | 856.184 TND
  N22328 | DAOUD MARIEM | 4415.504 TND
  N22329 | BETASGHIR TOUBA EP CHIHEB ACHO | 937.009 TND
  N22330 | DOGGUI SONIA | 2647.536 TND
  N22333 | STE MEDI MARKETING AGENCY | 2786.423 TND
  N22334 | GHARSALLI RIM | 1336.808 TND
  N22335 | HAMMAMI WASSIM | 7891.588 TND
  N22337 | ARAPIS MENIPPOS | 956.152 TND
  N22338 | GHARBI NOURA EP GUERMAZI | 2112.881 TND
  N22339 | STE JOUVENCEMED | 860.064 TND
  N22340 | SOULI MONAAM | 541.888 TND
  N22346 | BARAKATI DALINDA | 1255.968 TND
  N22350 | GUESMI IBTISSEM | 549.022 TND
  N22353 | HRIZI TAREK | 379.158 TND
  N22354 | ABDELAOUI WISSEM | 469.169 TND
  N22355 | ZOUAGHI EP SOUSSI AMEL | 1595.418 TND
  N22356 | CHEBBI AHMED | 3852.060 TND
  N22357 | MAGHRAOUI IMEN | 318.862 TND
  N22358 | BEN BRAHIM JAMEL EDDINE | 412.392 TND
  N22363 | BEN JEBARA WAFA | 592.939 TND
  N22364 | BOUZID TAHER | 1584.175 TND
  N22367 | STE ARISOTA REALTY | 2952.248 TND
  N22368 | DAB SOFIENE | 1720.902 TND
  N22370 | KOUMANJI MOLKA | 562.635 TND
  N22371 | SASSI MED IHEB | 299.485 TND
  N22372 | FARFAR WIEM | 1099.066 TND
  N22374 | GHARBI NESRINE | 474.215 TND
  N22375 | JELLALI ABDERRAOUF | 428.778 TND
  N22376 | BEN OTHMEN MAHA | 580.920 TND
  N22377 | ABROUGUI ACHREF | 409.332 TND
  N22380 | EL ABED LAMIA | 1303.199 TND
  N22383 | LAKHDHAR RAMZI | 2744.854 TND
  N22391 | MONARCA CALL CENTER | 1452.051 TND
  N22409 | GHANEM SONIA | 331.824 TND
  N22414 | ABASSI GHADHA | 534.234 TND
  N22441 | MOHAMED BELDI | 1636.790 TND
  N22472 | TRABELSI OUSSEMA | 26.600 TND
  N22481 | DHIF WISSAL | 515.578 TND
  N22482 | KOUMANJI MOHAMED MALEK | 596.477 TND
  N22490 | AGREBI EMNA | 26.379 TND
  N22492 | BOURAOUI FETEN | 413.406 TND
  N22498 | BEN ABDELHAMID NAOUEL | 1280.142 TND
  N22546 | KASRI ABDERRAOUF | 515.755 TND
  N22611 | REZGUI HEDIA | 393.202 TND
  N22618 | EZZINE KHALIL | 3900.124 TND
  N22627 | AOUADI NEJIB | 490.662 TND
  N22628 | BELHADJ NADIA | 1114.208 TND
  N22630 | HAIFA BOUATTOUR | 2916.492 TND
  N22634 | MAROUEN TBIB | 513.618 TND
  N22635 | STE DANEF | 3008.789 TND
  N22636 | SAAFI HAMADI | 1100.063 TND
  N22638 | SAMEH ELAOUINI | 480.488 TND
  N22642 | HADIJI FAIZA | 2052.361 TND
  N22647 | TAHAR HAMMOUDA | 1172.864 TND
  N22651 | AYMEN MHIRSI | 343.244 TND
  N22652 | FARDI MOHAMED | 1034.978 TND
  N22653 | BEN BECHIR IMED | 331.754 TND
  N22654 | ROMDHANI HASSEN | 1697.576 TND
  N22655 | BOUNEB AHMED | 747.885 TND
  N22657 | JOUINI FAOUZI | 524.974 TND
  N22658 | BEN AMAR HAJER | 451.986 TND
  N22663 | GHARSALLAH NESRINE | 618.407 TND
  N22665 | SABINE MICHAELA VALLANT | 971.868 TND
  N22667 | GHANNEM RIDHA | 346.875 TND
  N22668 | LENGLIZ IMEN | 373.899 TND
  N22670 | BEJAOUI SAMI | 784.369 TND
  N22673 | STE PRIMAPRINT | 1019.820 TND
  N22676 | KOOLI YASSINE | 568.584 TND
  N22774 | ZYADA NAJIA | 565.774 TND
  N22776 | BEN SAYEH MOHAMED LAKANI | 447.864 TND
  N22802 | JAIDANE WISSEM | 4177.176 TND
  N22808 | BACHA SEIFEDDINE | 342.781 TND
  N22819 | SASSI CHEDLY | 1478.391 TND
  N22872 | STE PRIMAPRINT | 6247.042 TND
  N22876 | AOUADI MONGIA | 1770.469 TND
  N22878 | BRIK MOHAMED HAITHEM | 1082.745 TND
  N22892 | DIMESSI SKANDER | 941.760 TND
  N22965 | ELFIL FARES | 689.203 TND
  N22969 | STE MEDI MARKETING AGENCY | 2190.952 TND
  N22975 | CLINIQUE ABOU ZIED | 1144.330 TND
  N22977 | BELKAHLA NEE TLILI SAIDA | 526.867 TND
  N22981 | GAMMOUDI MOHAMED | 749.116 TND
  N22994 | MAKHLOUFI SAMEH | 1389.983 TND
  N22997 | GUIZANI SANA | 684.229 TND
  N23002 | BEN MOOTA ALLHA MOHAMED | 393.421 TND
  N23005 | BEN HAJ AMOR YASMINE | 1237.335 TND
  N23006 | HAMMOUDA HAJER | 789.162 TND
  N23008 | KAHRI SONIA | 839.895 TND
  N23025 | MOHAMED MOULDI NECHI | 1245.131 TND
  N23050 | HABIBI ABDESSATTAR | 1862.464 TND
  N23066 | HAMMAMI MOKHTAR | 2416.818 TND
  N23070 | JALOULI NOURA | 320.413 TND
  N23120 | HEDHLI MOEZ KAIES | 746.791 TND
  N23130 | BEN KACEM SAIDA | 40.384 TND
  N23131 | KHAZRI LOTFI | 382.455 TND
  N23136 | ZOGHLAMI KAOUTHER | 1090.125 TND
  N23137 | GHARBI HOUNEIDA | 621.969 TND
  N23138 | BERRIRI MAHER | 506.185 TND
  N23148 | MARIEM MSADEK | 5339.333 TND
  N23149 | GHARBI HOUNEIDA | 854.149 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('LLOYD'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: STAR (15 factures, 101015.758 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('STAR', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    101015.758,
    101015.758,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22050 | CHEBLI MOHAMED AYMEN | 8111.776 TND
  N22128 | STE ILIADE CONSULTING | 53107.351 TND
  N22130 | STE WYPLAY TUNISIA | 739.607 TND
  N22134 | STE INTER 26 | 350.710 TND
  N22137 | ALARABY TELEVISION NETWORK LIM | 2740.121 TND
  N22139 | STE CODIX TUNISIE DEVELOPPEMEN | 21595.454 TND
  N22144 | ESSID KARIM | 679.928 TND
  N22422 | ZAOUAK MOHAMED KARIM | 1120.121 TND
  N22457 | STE MEDTCO | 3187.711 TND
  N22509 | STE  A G S | 120.209 TND
  N22617 | STE BEDOUI ELEC TRANSFORMATEUR | 2322.943 TND
  N22799 | DIGITAL IRIS PRODUCTION AUDIOV | 3596.003 TND
  N22829 | STE INTER 26 | 2875.534 TND
  N23184 | ZARRAD SAMIR MEHDI | 441.690 TND
  N23187 | STE KEMIKOL | 26.600 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('STAR'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: BH ASSURANCE (46 factures, 91294.035 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('BH ASSURANCE', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    91294.035,
    91294.035,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22028 | BOUASSIDA RADHOUAN | 989.836 TND
  N22034 | KHOULOUD BAIDI | 688.479 TND
  N22041 | MOHAMED HADJ TAIEB | 5017.897 TND
  N22062 | BOUBAYA FARID | 3109.400 TND
  N22064 | AYARI LOTFI | 1168.787 TND
  N22066 | AKROUT EP BAHI ALIA | 261.916 TND
  N22164 | STE CO LAIT FRAIS | 16027.563 TND
  N22178 | AYARI MOHAMED SALAH | 181.780 TND
  N22182 | BORGHEL JEBRANE | 60.536 TND
  N22198 | EL WARDIENNE EP ABID AIDA | 1004.326 TND
  N22199 | BOUFADEN YASER | 552.932 TND
  N22201 | FAYZER NORTH AFRICA | 696.531 TND
  N22206 | NAJJAR MOHAMED HEDI | 1188.857 TND
  N22210 | OMEGA FORMATION ET CONSULTING+ | 2406.903 TND
  N22211 | STE LE DOYEN DE CONSEIL ASS. & | 2186.021 TND
  N22214 | CHTIOUI LOTFI | 1461.070 TND
  N22215 | STE CODIX TUNISIE DEVELOPPEMEN | 1742.653 TND
  N22222 | ZARKOUNA RAYHANA | 666.674 TND
  N22282 | BEN FRAJ HASSEN | 181.780 TND
  N22413 | SHAIEK ALI | 79.115 TND
  N22440 | TECHNI AIR | 19551.071 TND
  N22442 | AKROUT EP BAHI ALIA | 4614.549 TND
  N22493 | FOURATI MOHAMED KARIM | 18.800 TND
  N22494 | ROUAHI MONIA | 1070.612 TND
  N22539 | OLFA GUESMI | 103.000 TND
  N22543 | BARRAK CHIRAZ | 1049.910 TND
  N22550 | STE CO LAIT FRAIS | 8222.437 TND
  N22568 | STE S.A.A.M | 2406.903 TND
  N22572 | SABEH KAMMOUN EP SELLAMI | 1390.774 TND
  N22573 | TAHER BELHADJ HASSAN | 838.462 TND
  N22577 | NOURI KHARRAT | 703.026 TND
  N22581 | MEDFI HANI | 181.780 TND
  N22674 | ZRIBI MOHAMED | 720.000 TND
  N22675 | STE PILASTRO | 396.585 TND
  N22793 | HAMED HMADA | 181.780 TND
  N22818 | HORRI CHIRAZ | 762.203 TND
  N22821 | TOUMI MOUNA | 1035.513 TND
  N22825 | NAJOUA FOURATI | 1754.488 TND
  N22837 | KESSENTINI TASNIM | 1348.978 TND
  N22889 | BEN SLIMA NAHED | 297.000 TND
  N22890 | RHOUMA MOHAMED AMINE | 297.000 TND
  N23095 | AJROUDI WALID | 396.585 TND
  N23096 | IBRAHIM RAFIK | 1424.088 TND
  N23111 | SABINE MICHAELA VALLANT | 522.785 TND
  N23139 | ZAHAG NEE LATRECH MOUFIDA | 1936.065 TND
  N23140 | NEFZI KHALED | 396.585 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('BH ASSURANCE'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: Astree (8 factures, 67315.680 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('Astree', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    67315.68,
    67315.68,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22388 | STE ZARZIS BETON | 2825.400 TND
  N22406 | STE ZARZIS BETON | 1883.526 TND
  N22416 | STE NEWREST CATERING TUNISIE | 17474.079 TND
  N22561 | STE CODIX TUNISIE DEVELOPPEMEN | 25225.400 TND
  N22784 | MAMI EP AZOUZ SAADIA | 1652.252 TND
  N23058 | STE ARTIMIS TUNIS | 15921.560 TND
  N23060 | EL KEFI SOUMAYA | 1044.438 TND
  N23061 | GRATI FETHI | 1289.025 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('Astree'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: AL AMANA TAKAFUL (9 factures, 54875.096 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('AL AMANA TAKAFUL', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    54875.096,
    54875.096,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22115 | M''HIRSI MARWA | 3101.498 TND
  N22118 | STE SESAME | 29293.000 TND
  N22119 | STE SOMEDEN | 5252.100 TND
  N22121 | STE ARCHETYPE TUNISIE | 7192.548 TND
  N22491 | ZAIMI ZEINEB | 938.025 TND
  N22690 | BOUABID MARWAN | 186.399 TND
  N22837 | KESSENTINI TASNIM | 1348.978 TND
  N23115 | STE ARCHETYPE TUNISIE | 7192.548 TND
  N23166 | BEN ROMDHANE YASSER | 370.000 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('AL AMANA TAKAFUL'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: CARTE (88 factures, 44510.433 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('CARTE', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    44510.433,
    44510.433,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22036 | IMENE MANAA EP KHARRAT | 27.000 TND
  N22068 | STE ARCHETYPE TUNISIE | 780.613 TND
  N22079 | BEN AMOR ANIS | 43.000 TND
  N22112 | HAMMAMI LOTFI | 601.236 TND
  N22126 | HAGUI ISLAM | 501.930 TND
  N22154 | ABDELMOUNEM SALHI | 1496.595 TND
  N22157 | STE EMPREINTE TS | 3026.388 TND
  N22166 | BEN SALEM KHEMAIES | 671.976 TND
  N22167 | BOUHLALI ADEL | 675.840 TND
  N22169 | BOUBTANE AMIR | 691.180 TND
  N22170 | AHMED FERCHICHI | 478.044 TND
  N22171 | HAMMAMI HAKIM | 355.744 TND
  N22172 | HAMMAMI LOTFI | 1173.247 TND
  N22173 | BEN ABDELKADER RYADH | 804.473 TND
  N22174 | SELLEMI MONCEF | 701.174 TND
  N22177 | GHARBI JAMILA | 702.468 TND
  N22179 | MR ALI  HAMMAMI | 694.024 TND
  N22183 | BEN KHMIS LOBNA ASMA | 287.306 TND
  N22218 | STE CODIX TUNISIE DEVELOPPEMEN | 54.000 TND
  N22224 | MSSIHLI FETHI | 353.960 TND
  N22225 | MSSIHLI FRAJ | 352.420 TND
  N22226 | SALIHA HEDHLI | 278.948 TND
  N22228 | HAMDI AKRMI | 341.440 TND
  N22229 | OUNI MOEZ | 216.900 TND
  N22231 | SOIYAH WAFA | 333.529 TND
  N22232 | GHARIANI WALID | 456.586 TND
  N22237 | BEN LAKHDHER NAJLA | 242.520 TND
  N22243 | JARIR MOHAMED AMINE | 393.366 TND
  N22283 | BEN AHMED OUSSEMA | 480.832 TND
  N22360 | FEZAI HALIMA EPOUSE KHEZAMI | 493.392 TND
  N22362 | SEBAI GHADA | 27.000 TND
  N22390 | CHELBA ABDELHAMID | 709.928 TND
  N22392 | BOUKHRIS EP OUESLATI SAIDA | 43.000 TND
  N22393 | ZEDDINI BESSEM | 274.214 TND
  N22410 | HAMRI NAJEM | 843.680 TND
  N22420 | FAZZANI MUSTAPHA | 563.120 TND
  N22437 | GHARBI SADOK | 702.468 TND
  N22456 | TOUMI NAWEL | 27.000 TND
  N22460 | STE CODIX TUNISIE DEVELOPPEMEN | 254.000 TND
  N22465 | EZDDINE ZAIRI | 560.320 TND
  N22547 | JANDOUBI HSSAN | 780.868 TND
  N22563 | HAMMAMI GHASSEN | 772.916 TND
  N22565 | STE GREEN VAGAT | 737.692 TND
  N22569 | GHOZLANI BOUKHTIOUA | 623.040 TND
  N22582 | JEDDA LAZHER | 479.302 TND
  N22583 | DAAJI TAREK | 493.392 TND
  N22585 | HORCHANI MAHER | 345.030 TND
  N22587 | OUNI NABIL | 336.364 TND
  N22590 | KAMOUN MOHAMED | 1137.088 TND
  N22596 | AMDOUNI HABIB | 436.162 TND
  N22597 | ELOUNI HICHEM | 352.840 TND
  N22598 | MOHAMED BESSI BRAHIM | 339.900 TND
  N22599 | MR HAYTHEM HAMMAMI | 437.256 TND
  N22601 | JLASSI RIDHA | 352.420 TND
  N22602 | BECHIR HELALI | 430.680 TND
  N22603 | DRIDI AMAL | 454.757 TND
  N22604 | GADHGADHI CHOKRI | 296.853 TND
  N22605 | HAMZA SAMIA | 481.412 TND
  N22606 | FRIKHA EP DHAHBI FATMA | 925.338 TND
  N22607 | SKINI AMOR | 1680.640 TND
  N22609 | GRAB RIHEM | 273.360 TND
  N22635 | STE DANEF | 3008.789 TND
  N22713 | HAMMAMI WISSEM | 737.692 TND
  N22801 | LATRECH ADNANE | 60.800 TND
  N22827 | HORCHANI JILENI | 700.352 TND
  N22843 | GOUIDRI DRISS | 884.916 TND
  N22846 | NAJJAR FETHI | 684.192 TND
  N22848 | BEJAOUI FETHI | 392.320 TND
  N22851 | JENNI HICHEM | 254.280 TND
  N22852 | SAYARI AMIRA | 400.899 TND
  N22853 | ZAIRI RANIA | 577.685 TND
  N22857 | BEN AYACHE EP BEN HANINI RAJA | 127.000 TND
  N22908 | BEN SABEUR VV LOUSSAIEF SOUAD | 43.000 TND
  N22909 | BENSABER SAIDA | 43.000 TND
  N22910 | BEN SABER VV BAKOUCHE MOUNIRA | 43.000 TND
  N23040 | LOUKIL TASNIM | 27.000 TND
  N23042 | ZARRAD SAMIR MEHDI | 72.500 TND
  N23044 | KHEZAMI ANOUER | 702.468 TND
  N23065 | GHRAM MAISSA | 47.232 TND
  N23071 | NABIL KAMOUN | 43.000 TND
  N23119 | EL ATOUI TAHAR | 934.480 TND
  N23123 | ZEDDINI BESSEM | 60.800 TND
  N23124 | MERDESSI OUMAYMA | 127.000 TND
  N23126 | BEN SAID FATMA | 27.000 TND
  N23127 | EL JAMI HABIB | 81.601 TND
  N23133 | BENABDALLAH KARIM | 27.000 TND
  N23142 | MOUMEN MOEZ | 43.000 TND
  N23212 | KSOURI AYMEN | 477.256 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('CARTE'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: MAGHREBIA (21 factures, 30771.684 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('MAGHREBIA', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    30771.684,
    30771.684,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22074 | AMRI DHOUHA | 1639.560 TND
  N22185 | BEN AHMED YAMINA | 782.136 TND
  N22186 | STE FOR IMPACT THREADS | 1510.446 TND
  N22187 | WALI LEILA | 2621.782 TND
  N22188 | NSIRI MBAREK | 1026.552 TND
  N22264 | REZGUI YASSINE | 1272.545 TND
  N22285 | STE GMI | 5198.938 TND
  N22326 | LA FINANCIERE TUNISIENNE | 3446.539 TND
  N22524 | RABTI ADEL | 361.720 TND
  N22531 | BEN ALI ABDELHAKH | 606.236 TND
  N22548 | STE SLIM BATIMENT ET TRAVAUX | 2474.666 TND
  N22616 | BOUAZIZ RAOUDHA | 950.752 TND
  N22727 | MERIAH MOUNA | 371.021 TND
  N22881 | EL AOUNI SOFIENE | 1425.159 TND
  N22882 | ABDELFATAH LASSOUED | 73.574 TND
  N22885 | AMRI AREM | 486.888 TND
  N23051 | STE MAXI ZOO | 428.600 TND
  N23064 | STE KANOUN ET MTIBAA ARTS | 3469.709 TND
  N23128 | KAROUI MONIA | 1199.672 TND
  N23134 | BEN WAHID IMEN | 1382.539 TND
  N23141 | BEN HAMMOUDA MED ADAM | 42.650 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('MAGHREBIA'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: MAE (33 factures, 29892.506 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('MAE', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    29892.506,
    29892.506,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22029 | MOGAADI SABRI | 391.281 TND
  N22077 | EL ASSAIDI AYMEN | 371.281 TND
  N22081 | CENTRALE LAITIERE DU CAP BON | 212.740 TND
  N22163 | THEYRI SANA | 161.500 TND
  N22176 | JEMAI ZIED | 264.268 TND
  N22287 | REBAI AICHA | 965.940 TND
  N22298 | MAMI NESRINE | 846.020 TND
  N22299 | SLIM AMIRA | 1348.922 TND
  N22302 | DHIEDDINE ENEFZI | 408.180 TND
  N22429 | SAHBANI KHALED | 2038.274 TND
  N22464 | EL AGREBI OUMAYA | 240.100 TND
  N22501 | YOUSSFI MOUNIR | 1571.920 TND
  N22507 | CHIBANI NADER | 220.100 TND
  N22520 | STE BOOSTENO TUNISIE | 4849.950 TND
  N22545 | EL ABBESSI WAEL | 231.436 TND
  N22564 | PIERRE FABRE MEDICAMENT TUNISI | 178.600 TND
  N22678 | STE D''IMAGERIE MEDIC | 1639.523 TND
  N22692 | MERGHMI ADEL | 377.773 TND
  N22728 | CHAKER DORRA | 1648.420 TND
  N22739 | ERNAZ MARIEM | 944.564 TND
  N22740 | STE LASKAA | 1050.072 TND
  N22743 | ELKADRI NEILI | 741.732 TND
  N22760 | BEN GUIRAT JIHEN | 207.100 TND
  N22794 | HANNIBAL LEASE | 602.811 TND
  N22811 | GOODIZ INDUSTRY | 1708.037 TND
  N22830 | REBIAAT JALEL | 211.436 TND
  N22835 | HDIJI MOURAD | 580.800 TND
  N22877 | SOUIDI FATHI | 264.268 TND
  N22927 | GARALI HATEM | 1866.112 TND
  N22930 | ALI TRABELSI | 494.324 TND
  N22960 | KHARCHI AMIRA | 824.104 TND
  N23022 | ELMASSOUDI AHMED | 212.740 TND
  N23039 | STE JETS | 2218.178 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('MAE'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: COMAR (3 factures, 7911.800 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('COMAR', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    7911.8,
    7911.8,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22488 | STE RIVEXIA | 181.060 TND
  N22506 | CHEBBI GHASSEN | 1022.200 TND
  N22903 | MEDDEB AHMED | 6708.540 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('COMAR'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: BIAT ASS (1 factures, 7688.200 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('BIAT ASS', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    7688.2,
    7688.2,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22428 | HEALTH LINK SARL | 7688.200 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('BIAT ASS'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

-- Compagnie: AMI (1 factures, 3904.006 TND)
INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE('AMI', ' ', '_')),
    'ouvert',
    ic.id,
    '2026-04-17'::date,
    3904.006,
    3904.006,
    0,
    'Sfax',
    'Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :
  N22046 | STE RMC REKIK MANAGEMENT&CONSU | 3904.006 TND',
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM('AMI'))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;

COMMIT;

-- Verification
SELECT ic.name AS compagnie, je.total_montant_enc AS montant_restant, je.state
FROM insurance_journal_enc je
JOIN insurance_company ic ON ic.id = je.company_ins_id
WHERE je.notes LIKE 'Factures migreees depuis Oracle%'
ORDER BY je.total_montant_enc DESC;
