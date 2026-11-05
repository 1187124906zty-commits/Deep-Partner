const r=`<?xml version="1.0" encoding="utf-8"?>\r
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" demote-non-dropping-particle="sort-only">\r
  <info>\r
    <title>Cite Them Right 12th edition (author-date/Harvard)</title>\r
    <id>http://www.zotero.org/styles/harvard-cite-them-right</id>\r
    <link href="http://www.zotero.org/styles/harvard-cite-them-right" rel="self"/>\r
    <link href="http://www.zotero.org/styles/harvard-cite-them-right-11th-edition" rel="template"/>\r
    <link href="http://www.citethemrightonline.com/" rel="documentation"/>\r
    <author>\r
      <name>Patrick O'Brien</name>\r
    </author>\r
    <category citation-format="author-date"/>\r
    <category field="generic-base"/>\r
    <summary>Harvard according to Cite Them Right, 11th edition.</summary>\r
    <updated>2026-02-12T10:08:06+00:00</updated>\r
    <rights license="http://creativecommons.org/licenses/by-sa/3.0/">This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 License</rights>\r
  </info>\r
  <locale xml:lang="en-GB">\r
    <terms>\r
      <term name="editor" form="short">\r
        <single>ed.</single>\r
        <multiple>eds</multiple>\r
      </term>\r
      <term name="editortranslator" form="verb">edited and translated by</term>\r
      <term name="edition" form="short">edn.</term>\r
    </terms>\r
  </locale>\r
  <macro name="editor">\r
    <choose>\r
      <if type="chapter paper-conference" match="any">\r
        <group delimiter=" ">\r
          <text term="in"/>\r
          <names variable="container-author" delimiter=", " suffix=", ">\r
            <name and="text" initialize-with=". "/>\r
          </names>\r
          <choose>\r
            <if variable="container-author" match="none">\r
              <names variable="editor translator" delimiter=", ">\r
                <name and="text" initialize-with="."/>\r
                <label form="short" prefix=" (" suffix=")"/>\r
              </names>\r
            </if>\r
          </choose>\r
        </group>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="secondary-contributors">\r
    <choose>\r
      <if type="chapter paper-conference" match="none">\r
        <names variable="editor translator" delimiter=". ">\r
          <label form="verb" text-case="capitalize-first" suffix=" "/>\r
          <name and="text" initialize-with="."/>\r
        </names>\r
      </if>\r
      <else-if variable="container-author" match="any">\r
        <names variable="editor translator" delimiter=". ">\r
          <label form="verb" text-case="capitalize-first" suffix=" "/>\r
          <name and="text" initialize-with=". " delimiter=", "/>\r
        </names>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <macro name="author">\r
    <names variable="author">\r
      <name and="text" delimiter-precedes-last="never" initialize-with="." name-as-sort-order="all"/>\r
      <label form="short" prefix=" (" suffix=")"/>\r
      <et-al font-style="italic"/>\r
      <substitute>\r
        <names variable="editor"/>\r
        <names variable="translator"/>\r
        <choose>\r
          <if type="article-newspaper article-magazine article-journal" match="any">\r
            <text variable="container-title" text-case="title" font-style="italic"/>\r
          </if>\r
          <else>\r
            <text macro="title"/>\r
          </else>\r
        </choose>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <macro name="author-short">\r
    <names variable="author">\r
      <name form="short" and="text" delimiter=", " delimiter-precedes-last="never" initialize-with=". "/>\r
      <et-al font-style="italic"/>\r
      <substitute>\r
        <names variable="editor"/>\r
        <names variable="translator"/>\r
        <choose>\r
          <if type="article-newspaper article-magazine article-journal" match="any">\r
            <text variable="container-title" text-case="title" font-style="italic"/>\r
          </if>\r
          <else>\r
            <text macro="title"/>\r
          </else>\r
        </choose>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <macro name="access">\r
    <choose>\r
      <if variable="DOI">\r
        <group delimiter=": ">\r
          <text term="available at" text-case="capitalize-first"/>\r
          <text variable="DOI" prefix="https://doi.org/"/>\r
        </group>\r
      </if>\r
      <else-if variable="URL">\r
        <text term="available at" suffix=": " text-case="capitalize-first"/>\r
        <text variable="URL"/>\r
        <group prefix=" (" delimiter=": " suffix=")">\r
          <text term="accessed" text-case="capitalize-first"/>\r
          <date form="text" variable="accessed">\r
            <date-part name="day"/>\r
            <date-part name="month"/>\r
            <date-part name="year"/>\r
          </date>\r
        </group>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <macro name="number-volumes">\r
    <choose>\r
      <if variable="volume" match="none">\r
        <group delimiter=" " prefix="(" suffix=")">\r
          <text variable="number-of-volumes"/>\r
          <label variable="volume" form="short" strip-periods="true"/>\r
        </group>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="title">\r
    <choose>\r
      <if type="bill book legal_case legislation motion_picture report song thesis webpage graphic" match="any">\r
        <group delimiter=". ">\r
          <group delimiter=" ">\r
            <group delimiter=" ">\r
              <text variable="title" font-style="italic"/>\r
              <text variable="medium" prefix="[" suffix="]"/>\r
            </group>\r
            <text macro="number-volumes"/>\r
          </group>\r
          <text macro="edition"/>\r
        </group>\r
      </if>\r
      <else>\r
        <text variable="title" form="long" quotes="true"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="publisher">\r
    <choose>\r
      <if type="thesis">\r
        <group delimiter=". ">\r
          <text variable="genre"/>\r
          <text variable="publisher"/>\r
        </group>\r
      </if>\r
      <else-if type="report">\r
        <group delimiter=". ">\r
          <group delimiter=" ">\r
            <text variable="genre"/>\r
            <text variable="number"/>\r
          </group>\r
          <group delimiter=": ">\r
            <text variable="publisher-place"/>\r
            <text variable="publisher"/>\r
          </group>\r
        </group>\r
      </else-if>\r
      <else-if type="article-journal article-newspaper article-magazine" match="none">\r
        <group delimiter=" ">\r
          <group delimiter=", ">\r
            <choose>\r
              <if type="speech" variable="event" match="any">\r
                <text variable="event" font-style="italic"/>\r
              </if>\r
            </choose>\r
            <group delimiter=": ">\r
              <text variable="publisher-place"/>\r
              <text variable="publisher"/>\r
            </group>\r
          </group>\r
          <group prefix="(" suffix=")" delimiter=", ">\r
            <text variable="collection-title"/>\r
            <text variable="collection-number"/>\r
          </group>\r
        </group>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <macro name="year-date">\r
    <choose>\r
      <if variable="issued">\r
        <date variable="issued">\r
          <date-part name="year"/>\r
        </date>\r
        <text variable="year-suffix"/>\r
      </if>\r
      <else>\r
        <text term="no date"/>\r
        <text variable="year-suffix" prefix=" "/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="locator">\r
    <choose>\r
      <if type="article-journal">\r
        <text variable="volume"/>\r
        <text variable="issue" prefix="(" suffix=")"/>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="published-date">\r
    <choose>\r
      <if type="article-newspaper article-magazine post-weblog speech" match="any">\r
        <date variable="issued">\r
          <date-part name="day" suffix=" "/>\r
          <date-part name="month" form="long"/>\r
        </date>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="pages">\r
    <choose>\r
      <if type="chapter paper-conference article-journal article article-magazine article-newspaper book review review-book report" match="any">\r
        <group delimiter=" ">\r
          <label variable="page" form="short"/>\r
          <text variable="page"/>\r
        </group>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="container-title">\r
    <choose>\r
      <if variable="container-title">\r
        <group delimiter=". ">\r
          <group delimiter=" ">\r
            <text variable="container-title" font-style="italic"/>\r
            <choose>\r
              <if type="article article-journal" match="any">\r
                <choose>\r
                  <if match="none" variable="page volume">\r
                    <text value="Preprint" prefix="[" suffix="]"/>\r
                  </if>\r
                </choose>\r
              </if>\r
            </choose>\r
          </group>\r
          <text macro="edition"/>\r
        </group>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="edition">\r
    <choose>\r
      <if is-numeric="edition">\r
        <group delimiter=" ">\r
          <number variable="edition" form="ordinal"/>\r
          <text term="edition" form="short" strip-periods="true"/>\r
        </group>\r
      </if>\r
      <else>\r
        <text variable="edition"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <citation et-al-min="4" et-al-use-first="1" disambiguate-add-year-suffix="true" disambiguate-add-names="true" disambiguate-add-givenname="true" collapse="year">\r
    <sort>\r
      <key macro="year-date"/>\r
    </sort>\r
    <layout prefix="(" suffix=")" delimiter="; ">\r
      <group delimiter=", ">\r
        <group delimiter=", ">\r
          <text macro="author-short"/>\r
          <text macro="year-date"/>\r
        </group>\r
        <group>\r
          <label variable="locator" form="short" suffix=" "/>\r
          <text variable="locator"/>\r
        </group>\r
      </group>\r
    </layout>\r
  </citation>\r
  <bibliography and="text" et-al-min="4" et-al-use-first="1">\r
    <sort>\r
      <key macro="author"/>\r
      <key macro="year-date"/>\r
      <key variable="title"/>\r
    </sort>\r
    <layout suffix=".">\r
      <group delimiter=". ">\r
        <group delimiter=" ">\r
          <text macro="author"/>\r
          <text macro="year-date" prefix="(" suffix=")"/>\r
          <group delimiter=", ">\r
            <text macro="title"/>\r
            <group delimiter=" ">\r
              <text macro="editor"/>\r
              <text macro="container-title"/>\r
            </group>\r
          </group>\r
        </group>\r
        <text macro="secondary-contributors"/>\r
        <text macro="publisher"/>\r
      </group>\r
      <group delimiter=", " prefix=", ">\r
        <text macro="locator"/>\r
        <text macro="published-date"/>\r
        <text macro="pages"/>\r
      </group>\r
      <text macro="access" prefix=". "/>\r
    </layout>\r
  </bibliography>\r
</style>\r
`;export{r as default};
