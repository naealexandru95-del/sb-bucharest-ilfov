# București + Ilfov for Subway Builder

A custom [Subway Builder](https://www.subwaybuilder.com/) map of Bucharest and all of Ilfov County (city code **BUH**).

- **Area:** the 6 sectors of Bucharest plus all 40 towns and communes of Ilfov (~2.26 M residents, 2021 census)
- **Demand:** ~3,900 demand points, ~39,000 commuter groups, ~1.71 M daily trips
- **Special demand:** Henri Coandă airport, 7 universities, 9 malls, Arena Națională, Romexpo, 4 parks, 3 hospitals
- **Map:** OpenStreetMap roads and labels, Overture building footprints with collision, water depths

## Install

**Railyard:** search for "București" or "Bucharest" and install.

**Manual:** download `BUH-x.y.z.zip` from [Releases](../../releases) and import it in Railyard as a local map.

## How the demand is modelled

1. **Residents:** the 2021 census population of each sector, town and commune, spread over the residential floor area (footprint × floors) of every building. Buildings come from Overture footprints, typed with OSM building and land-use tags.
2. **Destinations:** 62% of residents make a daily trip (workers plus commuting students). Trip destinations are split 83% Bucharest and 17% Ilfov, following INS employee counts. Within each county they are placed on offices, retail, industry, schools and hospitals by floor area and building type, plus OSM shop and office points.
3. **Hand-tuned zones:** `config.py` boosts or reduces activity in known areas, such as the Pipera, Floreasca and Băneasa business districts, the A1 and DN2 logistics belts, the dense southern estates and Militari Residence.
4. **Commutes:** a doubly-constrained gravity model, calibrated to a 9.5 km mean trip, sampled into commuter groups of at most 200 people. Driving times come from OSRM on the OSM road network.
5. **Special demand:** added with depot's `add_points`. Visitor and student figures are estimates (see `data/special_demand.json`).

Building it yourself: see [BUILD.md](BUILD.md).

## Data sources

- © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL)
- [Overture Maps Foundation](https://overturemaps.org/) buildings
- INS Romania, 2021 Population and Housing Census (via [citypopulation.de](https://www.citypopulation.de/en/romania/ilfov/)); INS employee statistics
- GEBCO bathymetry (via depot)

## Credits & licence

Built with [depot](https://github.com/Subway-Builder-Modded/depot) by the Subway Builder Modded community. Code is licensed under GPL-3.0. Map data keeps its original licences, listed above.
