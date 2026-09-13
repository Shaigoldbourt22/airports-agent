<!--
Source:  https://ourairports.com/data/
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
    * [ Login ](/login?from=/data/)
    * [ Sign up ](/signup.html?from=/data/)
  * [ Help ](/help/)
  * 

#  Open data downloads 
Data should be open and sharable. 
OurAirports has [RSS](http://en.wikipedia.org/wiki/RSS) feeds for [comments](/comments.rss), [CSV](http://en.wikipedia.org/wiki/Comma-separated_values) and [HXL](http://hxlstandard.org) data downloads for geographical regions, and [KML](http://en.wikipedia.org/wiki/Keyhole_Markup_Language) files for individual airports and personal airport lists (so that you can get your personal airport list any time you want). 
Microsoft Excel users should read the special instructions below. 
## Downloads
For more intense work, we have a [CSV](http://en.wikipedia.org/wiki/Comma-separated_values)-formatted data dump of all our airports, countries, and top-level administrative subdivisions (regions), which we update every night. You can download these files and open them with almost any spreadsheet program or import them into your own database. You can even use them to set up your own, competing airport web site if you'd like! We'd love you to give us credit, like [we give credit to our sources](/about.html#credits), but you're not required to. 
### Terms of use
All data is released to the Public Domain, and comes with no guarantee of accuracy or fitness for use. 
### Datasets
For information about the columns and values in the datasets, please visit the [data dictionary](/help/data-dictionary.html) and [map legend](/help/#legend) (for airport and navaid types). 
Effective 3 November 2021, the download files are stored on GitHub, in the repository [davidmegginson/ourairports-data](https://github.com/davidmegginson/ourairports-data). The old download links redirect to there. Cloning that repository is an alternative way to access the data. 
[airports.csv](https://davidmegginson.github.io/ourairports-data/airports.csv) (12,722,717 bytes, last modified Sep 13, 2026)
     Large file, containing information on all airports on this site. 
[airport-frequencies.csv](https://davidmegginson.github.io/ourairports-data/airport-frequencies.csv) (1,299,606 bytes, last modified Sep 13, 2026)
     Large file, listing communication frequencies for the airports in `airports.csv`. 
[airport-comments.csv](https://davidmegginson.github.io/ourairports-data/airport-comments.csv) (4,678,340 bytes, last modified Sep 13, 2026)
     Large file, listing member comments for the airports in `airports.csv`. 
[runways.csv](https://davidmegginson.github.io/ourairports-data/runways.csv) (3,964,126 bytes, last modified Sep 13, 2026)
     Large file, listing runways for the airports in `airports.csv`. 
[navaids.csv](https://davidmegginson.github.io/ourairports-data/navaids.csv) (1,524,946 bytes, last modified Sep 13, 2026)
    Large file, listing worldwide radio navigation aids.
[countries.csv](https://davidmegginson.github.io/ourairports-data/countries.csv) (24,583 bytes, last modified Sep 13, 2026)
     A list of the world's countries. You need this spreadsheet to interpret the country codes in the airports and navaids files. 
[regions.csv](https://davidmegginson.github.io/ourairports-data/regions.csv) (485,253 bytes, last modified Sep 13, 2026)
     A list of all countries' top-level administrative subdivisions (provinces, governorates, states, etc.). You need this spreadsheet to interpret the region codes in the airport file. 
## Workarounds for Microsoft Excel
The CSV files above use the Unicode [UTF-8](http://en.wikipedia.org/wiki/UTF-8) character encoding to represent a wide range of non-English characters, such as Hellenic, Cyrillic, Han Chinese, and Arabic scripts, as well as accented Latin characters.
Unfortunately, [Microsoft Excel](http://en.wikipedia.org/wiki/Microsoft_Excel) does not detect the character encoding of CSV files, and does not allow you to specify the encoding when you open them, always assuming a proprietary Microsoft character encoding. As a result, if you simply open the CSV files in Excel, any non-English characters will be scrambled.
There are two workarounds available:
  1. Create a new, blank spreadsheet first, then use Excel's text import tool to load the CSV file into the blank spreadsheet.
  2. Rename the CSV file's extension to ".txt" before opening it with Excel.


In both cases, Excel will give you an opportunity to specify the field separator (",") and the character encoding ("UTF-8"), and then accented and other non-English characters should appear without problem.
These workarounds are not necessary for [OpenOffice Calc](http://en.wikipedia.org/wiki/OpenOffice.org_Calc), which always prompts for the character encoding when opening a CSV file (just choose "UTF-8").
