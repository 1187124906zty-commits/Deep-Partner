const e=`<?xml version="1.0" encoding="utf-8"?>\r
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" demote-non-dropping-particle="sort-only" default-locale="en-GB">\r
  <info>\r
    <title>Nature</title>\r
    <id>http://www.zotero.org/styles/nature</id>\r
    <link href="http://www.zotero.org/styles/nature" rel="self"/>\r
    <link href="https://www.nature.com/nature/for-authors/formatting-guide" rel="documentation"/>\r
    <author>\r
      <name>Michael Berkowitz</name>\r
      <email>mberkowi@gmu.edu</email>\r
    </author>\r
    <contributor>\r
      <name>Patrick O'Brien</name>\r
      <email>citationstyler@gmail.com</email>\r
    </contributor>\r
    <category citation-format="numeric"/>\r
    <category field="science"/>\r
    <category field="generic-base"/>\r
    <issn>0028-0836</issn>\r
    <eissn>1476-4687</eissn>\r
    <updated>2025-09-10T18:26:21+00:00</updated>\r
    <rights license="http://creativecommons.org/licenses/by-sa/3.0/">This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 License</rights>\r
  </info>\r
  <macro name="title">\r
    <choose>\r
      <if type="bill book graphic legal_case legislation motion_picture report song" match="any">\r
        <text variable="title" font-style="italic" text-case="title"/>\r
      </if>\r
      <else>\r
        <text variable="title"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="author">\r
    <names variable="author">\r
      <name sort-separator=", " delimiter=", " and="symbol" initialize-with=". " delimiter-precedes-last="never" name-as-sort-order="all"/>\r
      <label form="short" prefix=", "/>\r
      <et-al font-style="italic"/>\r
    </names>\r
  </macro>\r
  <macro name="access">\r
    <choose>\r
      <if variable="volume" type="article dataset software" match="any"/>\r
      <else-if variable="DOI">\r
        <text variable="DOI" prefix="doi:"/>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <macro name="access-data">\r
    <choose>\r
      <if type="dataset software" match="any">\r
        <text variable="DOI" prefix="https://doi.org/"/>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="issuance">\r
    <choose>\r
      <if type="bill book graphic legal_case legislation motion_picture song thesis chapter paper-conference" match="any">\r
        <group delimiter="; " suffix=".">\r
          <group delimiter=", " prefix="(" suffix=")">\r
            <text variable="publisher" form="long"/>\r
            <text variable="publisher-place"/>\r
            <date variable="issued">\r
              <date-part name="year"/>\r
            </date>\r
          </group>\r
        </group>\r
      </if>\r
      <else-if type="article">\r
        <group delimiter=" ">\r
          <choose>\r
            <if variable="genre" match="any">\r
              <text variable="genre" text-case="capitalize-first"/>\r
            </if>\r
            <else>\r
              <text term="preprint" text-case="capitalize-first"/>\r
            </else>\r
          </choose>\r
          <text term="at"/>\r
          <choose>\r
            <if variable="DOI" match="any">\r
              <text variable="DOI" prefix="https://doi.org/"/>\r
            </if>\r
            <else>\r
              <text variable="URL"/>\r
            </else>\r
          </choose>\r
          <date date-parts="year" form="text" variable="issued" prefix="(" suffix=")"/>\r
        </group>\r
      </else-if>\r
      <else-if type="dataset software" match="any">\r
        <group delimiter=" ">\r
          <text variable="publisher"/>\r
          <text macro="access-data"/>\r
          <date date-parts="year" form="text" variable="issued" prefix="(" suffix=")"/>\r
        </group>\r
      </else-if>\r
      <else-if type="report webpage post post-weblog" match="any">\r
        <group delimiter=" ">\r
          <text variable="URL"/>\r
          <date date-parts="year" form="text" variable="issued" prefix="(" suffix=")"/>\r
        </group>\r
      </else-if>\r
      <else-if type="article-journal" match="any">\r
        <group delimiter=" ">\r
          <choose>\r
            <if match="none" variable="volume page">\r
              <choose>\r
                <if match="any" variable="DOI">\r
                  <text variable="DOI" prefix="https://doi.org/"/>\r
                </if>\r
                <else>\r
                  <text variable="URL"/>\r
                </else>\r
              </choose>\r
            </if>\r
          </choose>\r
          <date date-parts="year" form="text" variable="issued" prefix="(" suffix=")"/>\r
        </group>\r
      </else-if>\r
      <else>\r
        <date variable="issued" prefix="(" suffix=")">\r
          <date-part name="year"/>\r
        </date>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="container-title">\r
    <choose>\r
      <if type="article-journal">\r
        <text variable="container-title" font-style="italic" form="short"/>\r
      </if>\r
      <else>\r
        <text variable="container-title" font-style="italic"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="editor">\r
    <choose>\r
      <if type="chapter paper-conference" match="any">\r
        <names variable="editor" prefix="(" suffix=")">\r
          <label form="short" suffix=" "/>\r
          <name and="symbol" delimiter-precedes-last="never" initialize-with=". " name-as-sort-order="all"/>\r
        </names>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="volume">\r
    <choose>\r
      <if type="article-journal" match="any">\r
        <text variable="volume" font-weight="bold" suffix=","/>\r
      </if>\r
      <else>\r
        <group delimiter=" ">\r
          <label variable="volume" form="short"/>\r
          <text variable="volume"/>\r
        </group>\r
      </else>\r
    </choose>\r
  </macro>\r
  <citation collapse="citation-number">\r
    <sort>\r
      <key variable="citation-number"/>\r
    </sort>\r
    <layout vertical-align="sup" delimiter=",">\r
      <text variable="citation-number"/>\r
    </layout>\r
  </citation>\r
  <bibliography et-al-min="6" et-al-use-first="1" second-field-align="flush" entry-spacing="0" line-spacing="2">\r
    <layout suffix=".">\r
      <text variable="citation-number" suffix="."/>\r
      <group delimiter=" ">\r
        <text macro="author" suffix="."/>\r
        <text macro="title" suffix="."/>\r
        <choose>\r
          <if type="chapter paper-conference" match="any">\r
            <text term="in"/>\r
          </if>\r
        </choose>\r
        <text macro="container-title"/>\r
        <text macro="editor"/>\r
        <text macro="volume"/>\r
        <text variable="page"/>\r
        <text macro="issuance"/>\r
        <text macro="access"/>\r
      </group>\r
    </layout>\r
  </bibliography>\r
</style>\r
`;export{e as default};
