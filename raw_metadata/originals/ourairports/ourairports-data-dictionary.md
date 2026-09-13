<!--
Source:  https://ourairports.com/help/data-dictionary.html
Fetched: 2026-09-13 09:53:57
Status:  200
Converted from HTML to Markdown verbatim. Text is unmodified.
-->

Toggle navigation [ OurAirports  ](/ "OurAirports home")
  * [ World ](/world.html)
  * [ Airports ](/airports/)
  * [ Comments ](/comments.html)
  * [ Downloads ](/data/)
  * Site info
    * [ Contributor leaderboard ](/stats/contributors.html)
    * [ About ](/about.html)
    * [ Contact ](/contact.html)


  * Login 
    * [ Login ](/login?from=/help/data-dictionary.html)
    * [ Sign up ](/signup.html?from=/help/data-dictionary.html)
  * [ Help ](/help/)
  * 

#  OurAirports dataset formats 
This page documents the columns used in the open-data datasets described on the [Downloads](/data/) page. There is more information there about using the data, including terms of use, and working around Microsoft Excel's UTF-8 handling for CSV files. 
All of the following datasets use the [comma-separated values](https://en.wikipedia.org/wiki/Comma-separated_values) (CSV) format, and UTF-8 character encoding. 
##  Dataset: [airports.csv](/data/airports.csv)
Each row in this dataset represents the record for a single airport. The primary key for interoperability purposes with other datasets is ident, but the actual internal OurAirports primary key is id. iso_region is a foreign key into the regions.csv download file. 
Column | Sample value | Description  
---|---|---  
id | 2434 |  Internal OurAirports integer identifier for the airport. This will stay persistent, even if the airport code changes.   
ident | EGLL |  The text identifier used in the OurAirports URL. This will be the ICAO code if available. Otherwise, it will be a local airport code (if no conflict), or if nothing else is available, an internally-generated code starting with the ISO2 country code, followed by a dash and a four-digit number.   
type | large_airport |  The type of the airport. Allowed values are "balloonport", "closed_airport", "heliport", "large_airport", "medium_airport", "seaplane_base", and "small_airport". See the [map legend](/help/#airports) for a definition of each type.   
name | London Heathrow Airport |  The official airport name, including "Airport", "Airstrip", etc.   
latitude_deg | 51.470600 |  The airport latitude in decimal degrees (positive for north).   
longitude_deg | -0.461941 |  The airport longitude in decimal degrees (positive for east).   
elevation_ft | 83 |  The airport elevation MSL in feet (_not_ metres).   
continent | EU |  The code for the continent where the airport is (primarily) located. Allowed values are "AF" ([Africa](/continents/AF/)), "AN" ([Antarctica](/continents/AN/)), "AS" ([Asia](/continents/AS/)), "EU" ([Europe](/continents/EU/)), "NA" ([North America](/continents/NA/)), "OC" ([Oceania](/continents/OC/)), or "SA" ([South America](/continents/SA/)).   
iso_country | GB |  The two-character [ISO 3166:1-alpha2 code](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes) for the country where the airport is (primarily) located. A handful of unofficial, non-ISO codes are also in use, such as "XK" for [Kosovo](/countries/XK/). Points to the code column in countries.csv.   
iso_region | GB-ENG |  An alphanumeric code for the high-level administrative subdivision of a country where the airport is primarily located (e.g. province, governorate), prefixed by the ISO2 country code and a hyphen. OurAirports uses [ISO 3166:2](https://en.wikipedia.org/wiki/ISO_3166-2) codes whenever possible, preferring higher administrative levels, but also includes some custom codes. See the documentation for regions.csv.   
municipality | London |  The primary municipality that the airport serves (when available). Note that this is _not_ necessarily the municipality where the airport is physically located.   
scheduled_service | yes |  "yes" if the airport currently has scheduled airline service; "no" otherwise.   
gps_code | EGLL |  The code that an aviation GPS database (such as Jeppesen's or Garmin's) would normally use for the airport. This will always be the icao_code if the airport has one, but it is not guaranteed to be globally unique.   
icao_code | EGLL |  The four-letter [ICAO code](https://en.wikipedia.org/wiki/ICAO_airport_code) for the airport (if it has one).   
iata_code | LHR |  The three-letter [IATA code](https://en.wikipedia.org/wiki/International_Air_Transport_Association_code) for the airport (if it has one).   
local_code |  |  The local country code for the airport, if different from the gps_code, icao_code, and iata_code fields (used mainly for US airports).   
home_link | http://www.heathrowairport.com/ |  URL of the airport's official home page on the web, if one exists.   
wikipedia_link | https://en.wikipedia.org/wiki/Heathrow_Airport |  URL of the airport's page on Wikipedia, if one exists.   
keywords | LON, Londres |  Extra keywords/phrases to assist with search, comma-separated. May include former names for the airport, alternate codes, names in other languages, nearby tourist destinations, etc.   
##  Dataset: [airport-frequencies.csv](/data/airport-frequencies.csv)
Each row in this dataset represents a single airport radio frequency for voice communication (radio navigation aids appear in navaids.csv). The column airport_ident is a foreign key referencing the ident column in airports.csv for the associated airport. 
Column | Sample value | Description  
---|---|---  
id | 54836 |  Internal OurAirports integer identifier for the frequency. This will stay persistent, even if the radio frequency or description changes.   
airport_ref | 3206 |  Internal integer foreign key matching the id column for the associated airport in airports.csv. (airport_ident is a better alternative.)   
airport_ident | HKJK |  Externally-visible string foreign key matching the ident column for the associated airport in airports.csv.   
type | TWR |  A code for the frequency type. This isn't (currently) a controlled vocabulary, but probably will be soon. Some common values are "TWR" (tower), "ATF" or "CTAF" (common traffic frequency), "GND" (ground control), "RMP" (ramp control), "ATIS" (automated weather), "RCO" (remote radio outlet), "ARR" (arrivals), "DEP" (departures), "UNICOM" (monitored ground station), and "RDO" (a flight-service station).   
description | Nairobi tower |  A description of the frequency, typically the way a pilot would open a call on it.   
frequency_mhz | 118.7 |  Radio voice frequency in megahertz. Note that the same frequency may appear multiple times for an airport, serving different functions.   
##  Dataset: [runways.csv](/data/runways.csv)
Each row in this dataset represents a single airport landing surface (runway, helipad, or waterway). The initial fields apply to the entire surface, in both directions. Fields beginning with le_* apply only to the low-numbered end of the runway (e.g. 09), while fields beginning with he_* apply only to the high-numbered end of the runway (e.g. 27). 
Column | Sample value | Description  
---|---|---  
id | 234512 |  Internal OurAirports integer identifier for the runway. This will stay persistent, even if the runway numbering changes.   
airport_ref | 1941 |  Internal integer foreign key matching the id column for the associated airport in airports.csv. (airport_ident is a better alternative.)   
airport_ident | CYVR |  Externally-visible string foreign key matching the ident column for the associated airport in airports.csv.   
length_ft | 9940 |  Length of the full runway surface (including displaced thresholds, overrun areas, etc) in feet.   
width_ft | 200 |  Width of the runway surface in feet.   
surface | CON |  Code for the runway surface type. This is not yet a controlled vocabulary, but probably will be soon. Some common values include "ASP" (asphalt), "TURF" (turf), "CON" (concrete), "GRS" (grass), "GRE" (gravel), "WATER" (water), and "UNK" (unknown).   
lighted | 1 |  1 if the surface is lighted at night, 0 otherwise. (Note that this is inconsistent with airports.csv, which uses "yes" and "no" instead of 1 and 0.)   
closed | 0 | 1 if the runway surface is currently closed, 0 otherwise.  
le_ident | 08L | Identifier for the low-numbered end of the runway.  
le_latitude_deg | 49.205000 |  Latitude of the centre of the low-numbered end of the runway, in decimal degrees (positive is north), if available.   
le_longitude_deg | -123.201000 |  Longitude of the centre of the low-numbered end of the runway, in decimal degrees (positive is east), if available.   
le_elevation_ft | 14 |  Elevation above MSL of the low-numbered end of the runway in feet.   
le_heading_degT | 99 |  Heading of the low-numbered end of the runway in degrees true (_not_ magnetic).   
le_displaced_threshold_ft |  |  Length of the displaced threshold (if any) for the low-numbered end of the runway, in feet.   
he_ident | 26R | Identifier for the high-numbered end of the runway.  
he_latitude_deg | 49.200600 |  Latitude of the centre of the high-numbered end of the runway, in decimal degrees (positive is north), if available.   
he_longitude_deg | -123.160000 |  Longitude of the centre of the high-numbered end of the runway, in decimal degrees (positive is east), if available.   
he_elevation_ft | 9 |  Elevation above MSL of the high-numbered end of the runway in feet.   
he_heading_degT | 279 |  Heading of the high-numbered end of the runway in degrees true (_not_ magnetic).   
he_displaced_threshold_ft |  |  Length of the displaced threshold (if any) for the high-numbered end of the runway, in feet.   
##  Dataset: [navaids.csv](/data/navaids.csv)
Each row in this dataset represents a single radio navigation. When the navaid is associated with an airport, the associated_airport field links to the ident field in [airports.csv](airports). 
Column | Sample value | Description  
---|---|---  
id | 86738 |  Internal OurAirports integer identifier for the navaid. This will stay persistent, even if the navaid identifier or frequency changes.   
filename | Christchurch_VOR-DME_NZ |  This is a unique string identifier constructed from the navaid name and country, and used in the OurAirports URL.   
ident | CH |  The 1-3 character identifer that the navaid transmits.   
name | Christchurch |  The name of the navaid, excluding its type.   
type | VOR-DME |  The type of the navaid. Options are "DME", "NDB", "NDB-DME", "TACAN", "VOR", "VOR-DME", or "VORTAC". See the [map legend](/help/#navaids) for more information about each type.   
frequency_khz | 115300 |  The frequency of the navaid in _kilohertz_. If the Navaid operates on the VHF band (VOR, VOR-DME) or operates on the UHF band with a paired VHF frequency (DME, TACAN, VORTAC), the you need to divide this number by 1,000 to get the frequency in megahertz (115.3 MHz in this example). For an NDB or NDB-DME, you can use this frequency directly.   
latitude_deg | -43.504101 |  The latitude of the navaid in decimal degrees (negative for south).   
longitude_deg | 172.514999 |  The longitude of the navaid in decimal degrees (negative for west).   
elevation_ft | 123 |  The navaid's elevation MSL in feet (not metres).   
iso_country | NZ |  The two-character [ISO 3166:1-alpha2 code](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes) for the country that operates the navaid. A handful of unofficial, non-ISO codes are also in use, such as "XK" for [Kosovo](/countries/XK/).   
dme_frequency_khz | 115300 |  The paired VHF frequency for the DME (or TACAN) in kilohertz. Divide by 1,000 to get the paired VHF frequency in megahertz (e.g. 115.3 MHz).   
dme_channel | 100X |  The DME channel (an alternative way of tuning distance-measuring equipment).   
dme_latitude_deg | -43.504200 |  The latitude of the associated DME in decimal degrees (negative for south). If missing, assume that the value is the same as latitude_deg.   
dme_longitude_deg | 172.515000 |  The longitude of the associated DME in decimal degrees (negative for west). If missing, assume that the value is the same as longitude_deg.   
dme_elevation_ft | 140 |  The associated DME transmitters elevation MSL in feet. If missing, assume that it's the same value as elevation_ft.   
slaved_variation_deg | 23.007 |  The magnetic variation adjustment built into a VOR's, VOR-DME's, or TACAN's radials. Positive means east (added to the true direction), and negative means west (subtracted from the true direction). This will not usually be the same as magnetic-variation because the magnetic pole is constantly in motion.   
magnetic_variation_deg | 23.188 |  The actual magnetic variation at the navaid's location. Positive means east (added to the true direction), and negative means west (subtracted from the true direction).   
usageType | BOTH |  The primary function of the navaid in the airspace system. Options include "HI" (high-altitude airways, at or above flight level 180), "LO" (low-altitude airways), "BOTH" (high- and low-altitude airways), "TERM" (terminal-area navigation only), and "RNAV" (non-GPS area navigation).   
power | HIGH |  The power-output level of the navaid. Options include "HIGH", "MEDIUM", "LOW", and "UNKNOWN".   
associated_airport | NZCH |  The OurAirports text identifier (usually the ICAO code) for an airport associated with the navaid. Links to the ident column in airports.csv.   
##  Dataset: [countries.csv](/data/countries.csv)
Each row represents a country or country-like entity (e.g. Hong Kong). The iso_country column in airports.csv, navaids.csv, and regions.csv refer to the code column here. 
Column | Sample value | Description  
---|---|---  
id | 302791 |  Internal OurAirports integer identifier for the country. This will stay persistent, even if the country name or code changes.   
code | BR |  The two-character [ISO 3166:1-alpha2 code](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes) for the country. A handful of unofficial, non-ISO codes are also in use, such as "XK" for [Kosovo](/countries/XK/). The iso_country field in airports.csv points into this column.   
name | Brazil |  The common **English** -language name for the country. Other variations of the name may appear in the keywords field to assist with search.   
continent | SA |  The code for the continent where the country is (primarily) located. See the continent code in airports.csv for allowed values.   
wikipedia_link | https://en.wikipedia.org/wiki/Brazil |  Link to the Wikipedia article about the country.   
keywords | Brasil, Brasilian |  A comma-separated list of search keywords/phrases related to the country.   
##  Dataset: [regions.csv](/data/regions.csv)
Each row represents a high-level administrative subdivision of a country. The iso_region column in airports.csv links to the code column in this dataset. 
Column | Sample value | Description  
---|---|---  
id | 306408 |  Internal OurAirports integer identifier for the region. This will stay persistent, even if the region code changes.   
code | GE-KA |  local_code prefixed with the country code to make a globally-unique identifier.   
local_code | KA |  The local code for the administrative subdivision. Whenever possible, these are official [ISO 3166:2](https://en.wikipedia.org/wiki/ISO_3166-2), at the highest level available, but in some cases OurAirports has to use unofficial codes. There is also a pseudo code "U-A" for each country, which means that the airport has not yet been assigned to a region (or perhaps can't be, as in the case of a deep-sea oil platform).   
name | Kakheti |  The common **English** -language name for the administrative subdivision. In some cases, the name in local languages will appear in the keywords field assist search.   
continent | AS |  A code for the continent to which the region belongs. See the continent field in airports.csv for a list of codes.   
iso_country | GE |  The two-character [ISO 3166:1-alpha2 code](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes) for the country containing the administrative subdivision. A handful of unofficial, non-ISO codes are also in use, such as "XK" for [Kosovo](/countries/XK/).   
wikipedia_link | https://en.wikipedia.org/wiki/Kakheti |  A link to the Wikipedia article describing the subdivision.   
keywords | Kakhet'i, კახეთი |  A comma-separated list of keywords to assist with search. May include former names for the region, and/or the region name in other languages. 
