# Adatszótár - Emergency Dispatch & Traffic Physics Dataset

## Áttekintés

| Tétel | Érték |
|---|---|
| Név / forrás | Emergency Dispatch and Traffic Physics Dataset, [Kaggle](https://www.kaggle.com/datasets/razanihababdellatif/emergency-dispatch-and-traffic-physics-dataset?resource=download) |
| Licensz | Attribution 4.0 International, szabadon felhasználható |
| Eredeti méret | 200 000 sor, 29 oszlop (szintetikus benchmark, városi, elővárosi és vidéki forgalom) |
| Felhasznált sorok | 8 231, csak azok a rekordok, ahol az `Accident_Occurred` értéke 1 |
| Oszlopok | 11 oszlop, 10 jellemző és 1 célváltozó |
| Feladattípus | Regresszió |
| Célváltozó | `Actual_Response_Time_min`, a mentők tényleges kiérkezési ideje percben |
| Célváltozó tartománya | 4,8 és 56,6 perc között, átlag 21,96 perc, szórás 8,11 perc |
| Train/Test Felosztás | 80 / 20 - 6 584 tanító és 1 647 teszt sor|

A feladat azt becsli, mennyi idő alatt ér a helyszínre a mentő egy baleset után. Az adatkészletet nem tisztítottuk, csak a balesetes sorokat és a kiválasztott oszlopokat tartottuk meg. A hiányzó értékek és a következetlen írásmódok így az eredeti formájukban szerepelnek a fájlban.

## Jellemzők

### Idő

| Oszlop | Jelentés | Mértékegység | Valószínű tartomány | Megbízhatatlan érték? | Megjegyzés |
|---|---|---|---|---|---|
| `Hour` | A nap órája | óra | 0-23 | nem | Átlag 12,41 |
| `Month` | Hónap sorszáma | hónap | 1-12 | nem | Átlag 6,49 |

### Helyszín és út

| Oszlop | Jelentés | Mértékegység | Valószínű tartomány | Megbízhatatlan érték? | Megjegyzés |
|---|---|---|---|---|---|
| `Area_Type` | Terület típusa | kategória | `Urban`, `Suburban`, `Rural` | nem | Leggyakoribb a `Urban` 3 665 sorral |
| `Road_Type` | Úttípus | kategória | `Interstate`, `Arterial`, `Collector`, `Local` | nem | Leggyakoribb az `Arterial` 3 019 sorral |
| `Intersection_Type` | Csomópont típusa | kategória | `4-Way`, `T-Junction`, `Roundabout`, `None` | igen, a `None` érték | A `None` szöveg jelentése nincs csomópont, 3 596 sorban szerepel. A pandas alapból hiányzó értékként olvassa be, ezért a betöltésnél vissza kell állítani szöveggé |
| `Road_Condition` | Útfelszín állapota | kategória | `Dry`, `Wet`, `Snowy`, `Icy`, `Standing Water` | nem | Leggyakoribb a `Dry` 4 039 sorral |

### Környezet és forgalom

| Oszlop | Jelentés | Mértékegység | Valószínű tartomány | Megbízhatatlan érték? | Megjegyzés |
|---|---|---|---|---|---|
| `Weather` | Időjárás | kategória | `Clear`, `Rain`, `Snow`, `Fog` | igen, következetlen írásmód | Az eső négyféleképpen szerepel (`Rain`, `rain`, `Rain `, ` RAIN`), ezért 7 különböző érték van. Nem tisztítottuk, a változatok külön kategóriának számítanak |
| `Visibility_m` | Látótávolság | méter | 66,4-15 000 | igen, hiányzó értékek | 264 sorban hiányzik, ez a sorok kb. 3,2 százaléka. A fájlban nincs kitöltve. Átlag 5 730,44 |
| `Congestion_Index` | Forgalmi torlódási index | index | 2,2-100 | nem | Magasabb érték nagyobb torlódást jelent. Átlag 73,15, a 75. percentilis már a maximum, vagyis sok sor éri el a 100-as plafont |

### Riasztás

| Oszlop | Jelentés | Mértékegység | Valószínű tartomány | Megbízhatatlan érték? | Megjegyzés |
|---|---|---|---|---|---|
| `Dispatch_Priority` | Kiérkezési prioritás | kategória | `Standard`, `Medium`, `High` | nem | A riasztás pillanatában már ismert, ezért megengedett jellemző. A `Standard` 4 124 sorban szerepel, ez a sorok fele. Szintetikus adatnál erősen összefügghet a célváltozóval |

### Célváltozó

| Oszlop | Jelentés | Mértékegység | Valószínű tartomány | Megbízhatatlan érték? | Megjegyzés |
|---|---|---|---|---|---|
| `Actual_Response_Time_min` | Tényleges kiérkezési idő | perc | 4,8-56,6 | nem | Nincs hiányzó érték. A balesetmentes sorok 0 értékét a szűréssel kizártuk |

## Elhagyott oszlopok

| Oszlop | Indok |
|---|---|
| `Record_ID` | Azonosító, nincs prediktív értéke, és kb. 24 duplikált értéke van |
| `Timestamp`, `Date` | Szöveges típusúak, és az `Hour` és `Month` oszlopok már tartalmazzák a lényegüket |
| `Accident_Occurred` | A szűrés után minden értéke 1, ezért nem hordoz információt |
| `Driver_Age`, `Driver_Experience_yrs`, `Vehicle_Age_yrs`, `Vehicle_Type` | A feladat az út- és forgalmi jellemzőkre fókuszál, ezért a vezetőre és a járműre vonatkozó adatok kimaradtak |
| `Recorded_Speed_kmh` | Vezetőfüggő jellemző, és 999 km/h-s placeholder értéket is tartalmaz |
| `Collision_Type`, `Accident_Severity`, `Road_Closure_Duration_min`, `Vehicles_Involved` | Csak baleset után ismertek, ezért célváltozó-szivárgást okoznának |
| `Baseline_Expected_Response_Time_min` | A célváltozó közvetlen közelítése, ezért elfedné a valódi út- és forgalmi hatásokat |
| `Day_of_Week`, `Time_of_Day`, `Is_Holiday`, `Speed_Limit_kmh` | A végső jellemzőkészletből kihagytuk. A `Time_of_Day` részben megegyezik az `Hour` információjával |

## Ismert sajátosságok és figyelmeztetések

- Az adatkészlet szintetikus, ezért a valós forgalmi összefüggéseket csak korlátozottan tükrözi.
- Az adatokat nem tisztítottuk. A `Weather` oszlop következetlen írásmódjai és a `Visibility_m` hiányzó értékei megmaradtak a fájlban.
- A hiányzó értékek kezelése a modellezési folyamat feladata, és csak a tanító halmazból számolt statisztikával szabad elvégezni, hogy ne kerüljön információ a teszthalmazból a tanításba.
- Az `Intersection_Type` oszlop `None` értékét a betöltéskor a `keep_default_na=False` beállítás védi, különben hiányzó értékként olvasódna be.
- A `Congestion_Index` értékei sok sorban a 100-as maximumon vannak, ezért az eloszlása nem szimmetrikus.
- A `Dispatch_Priority` a riasztáskor már ismert, de szintetikus adatnál a generátor közvetlenül összekapcsolhatta a kiérkezési idővel.
- Az R2 0,80 értéket ennek tudatában kell értelmezni, mert a prioritás a szórás nagy részét megmagyarázhatja.

## Numerikus oszlopok statisztikái

Az értékek a felhasznált 8 231 balesetes sorból származnak.

| Oszlop | Hiányzó | Min | Max | Átlag | Szórás |
|---|---:|---:|---:|---:|---:|
| `Hour` | 0 | 0 | 23 | 12,41 | 5,06 |
| `Month` | 0 | 1 | 12 | 6,49 | 3,55 |
| `Visibility_m` | 264 | 66,4 | 15 000 | 5 730,44 | 4 569,25 |
| `Congestion_Index` | 0 | 2,2 | 100 | 73,15 | 26,81 |
| `Actual_Response_Time_min` | 0 | 4,8 | 56,6 | 21,96 | 8,11 |