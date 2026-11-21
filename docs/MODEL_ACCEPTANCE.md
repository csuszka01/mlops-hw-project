## Modellelfogadási szabályok

**GO**, ha egyik ellenőrzés sem bukik meg, egyébként **NO-GO**. A `register` és a `promote` csak GO esetén fut le, a modellfájl NO-GO esetén is megmarad.

### Vizsgált csoportok

A csoportokat a `params.yaml` `evaluation.slices` blokkja definiálja, a nyers adaton, a hiányzó értékek pótlása előtt. A `Weather` értékei itt is kisbetűsek.

| Szelet | Oszlop | Csoportok (sor a jelenlegi 1 642 soros teszthalmazon) | Méltányossági kapu |
|---|---|---|---|
| `weather` | `Weather` | `clear` (796), `rain` (463), `snow` (257), `fog` (126) | igen |
| `area_type` | `Area_Type` | `urban` (727), `suburban` (593), `rural` (322) | igen |
| `dispatch_priority` | `Dispatch_Priority` | `standard` (814), `high` (498), `medium` (330) | igen |
| `visibility_missing` | `Visibility_m` | `visibility_present` (1 595), `visibility_missing` (47) | nem, csak jelentés |

| Ellenőrzés | Határ | Indok |
|---|---|---|
| R2 | legalább 0,70 | Az átlagot jósló modell R2 értéke 0 |
| RMSE | legfeljebb 4,5 perc | Az átlagot jósló modell hibája kb. a szórás (8,11 perc) |
| MAE | legfeljebb 3,5 perc | Az RMSE határral összhangban |
| Romlás a bajnokhoz képest | RMSE legfeljebb 0,3 perccel lehet rosszabb | Zajsáv, nem keret a romlásra |
| Csoport RMSE | legfeljebb 5,5 perc | Egyetlen csoport sem lehet ennél pontatlanabb |
| Csoport eltérés az összesítettől | legfeljebb 1,5 perc RMSE | Egy csoport sem maradhat el jelentősen az átlagtól |
| Csoportok közti RMSE különbség | legfeljebb 2,0 perc | `weather`, `area_type`, `dispatch_priority` szeleteken |
| Csoportok közti MAE különbség | legfeljebb 1,5 perc | Ugyanezeken a szeleteken |

- A csoportonkénti ellenőrzés 30 sornál kisebb csoportot kihagy.
- A `visibility_missing` szelet csak jelentésben szerepel, nem kapuzott.
- A kihagyott ellenőrzés nem számít sikeresnek, a kimenet külön mutatja a darabszámát. Amíg nincs bajnok modell, az összehasonlítás is kihagyott.
- Küszöb módosításakor az `acceptance.criteria_version` értékét is emelni kell.
