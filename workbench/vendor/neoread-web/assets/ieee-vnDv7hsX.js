const r=`<?xml version="1.0" encoding="utf-8"?>\r
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" demote-non-dropping-particle="sort-only">\r
  <info>\r
    <title>IEEE Reference Guide version 11.29.2023</title>\r
    <title-short>Institute of Electrical and Electronics Engineers</title-short>\r
    <id>http://www.zotero.org/styles/ieee</id>\r
    <link href="http://www.zotero.org/styles/ieee" rel="self"/>\r
    <link href="https://journals.ieeeauthorcenter.ieee.org/your-role-in-article-production/ieee-editorial-style-manual/" rel="documentation"/>\r
    <author>\r
      <name>Michael Berkowitz</name>\r
      <email>mberkowi@gmu.edu</email>\r
    </author>\r
    <contributor>\r
      <name>Julian Onions</name>\r
      <email>julian.onions@gmail.com</email>\r
    </contributor>\r
    <contributor>\r
      <name>Rintze Zelle</name>\r
      <uri>http://twitter.com/rintzezelle</uri>\r
    </contributor>\r
    <contributor>\r
      <name>Stephen Frank</name>\r
      <uri>http://www.zotero.org/sfrank</uri>\r
    </contributor>\r
    <contributor>\r
      <name>Sebastian Karcher</name>\r
    </contributor>\r
    <contributor>\r
      <name>Giuseppe Silano</name>\r
      <email>g.silano89@gmail.com</email>\r
      <uri>http://giuseppesilano.net</uri>\r
    </contributor>\r
    <contributor>\r
      <name>Patrick O'Brien</name>\r
    </contributor>\r
    <contributor>\r
      <name>Brenton M. Wiernik</name>\r
    </contributor>\r
    <contributor>\r
      <name>Oliver Couch</name>\r
      <email>oliver.couch@gmail.com</email>\r
    </contributor>\r
    <contributor>\r
      <name>Andrew Dunning</name>\r
      <uri>https://orcid.org/0000-0003-0464-5036</uri>\r
    </contributor>\r
    <category citation-format="numeric"/>\r
    <category field="engineering"/>\r
    <category field="generic-base"/>\r
    <summary>IEEE style as per the 2023 guidelines.</summary>\r
    <updated>2024-03-27T11:41:27+00:00</updated>\r
    <rights license="http://creativecommons.org/licenses/by-sa/3.0/">This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 License</rights>\r
  </info>\r
  <locale xml:lang="en">\r
    <date form="text">\r
      <date-part name="month" form="short" suffix=" "/>\r
      <date-part name="day" form="numeric-leading-zeros" suffix=", "/>\r
      <date-part name="year"/>\r
    </date>\r
    <terms>\r
      <term name="chapter" form="short">ch.</term>\r
      <term name="chapter-number" form="short">ch.</term>\r
      <term name="presented at">presented at the</term>\r
      <term name="available at">available</term>\r
      <!-- always use three-letter abbreviations for months -->\r
      <term name="month-06" form="short">Jun.</term>\r
      <term name="month-07" form="short">Jul.</term>\r
      <term name="month-09" form="short">Sep.</term>\r
    </terms>\r
  </locale>\r
  <!-- Macros -->\r
  <macro name="status">\r
    <choose>\r
      <if variable="page issue volume" match="none">\r
        <text variable="status" text-case="capitalize-first" suffix="" font-weight="bold"/>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="edition">\r
    <choose>\r
      <if type="bill book chapter graphic legal_case legislation motion_picture paper-conference report song" match="any">\r
        <choose>\r
          <if is-numeric="edition">\r
            <group delimiter=" ">\r
              <number variable="edition" form="ordinal"/>\r
              <text term="edition" form="short"/>\r
            </group>\r
          </if>\r
          <else>\r
            <text variable="edition" text-case="capitalize-first" suffix="."/>\r
          </else>\r
        </choose>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="issued">\r
    <choose>\r
      <if type="article-journal report" match="any">\r
        <date variable="issued">\r
          <date-part name="month" form="short" suffix=" "/>\r
          <date-part name="year" form="long"/>\r
        </date>\r
      </if>\r
      <else-if type="bill book chapter graphic legal_case legislation song thesis" match="any">\r
        <date variable="issued">\r
          <date-part name="year" form="long"/>\r
        </date>\r
      </else-if>\r
      <else-if type="paper-conference" match="any">\r
        <date variable="issued">\r
          <date-part name="month" form="short"/>\r
          <date-part name="year" prefix=" "/>\r
        </date>\r
      </else-if>\r
      <else-if type="motion_picture" match="any">\r
        <date variable="issued" form="text" prefix="(" suffix=")"/>\r
      </else-if>\r
      <else>\r
        <date variable="issued" form="text"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="author">\r
    <names variable="author">\r
      <name and="text" et-al-min="7" et-al-use-first="1" initialize-with=". "/>\r
      <label form="short" prefix=", " text-case="capitalize-first"/>\r
      <et-al font-style="italic"/>\r
      <substitute>\r
        <names variable="editor"/>\r
        <names variable="translator"/>\r
        <text macro="director"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <macro name="editor">\r
    <names variable="editor">\r
      <name initialize-with=". " delimiter=", " and="text"/>\r
      <label form="short" prefix=", " text-case="capitalize-first"/>\r
    </names>\r
  </macro>\r
  <macro name="director">\r
    <names variable="director">\r
      <name and="text" et-al-min="7" et-al-use-first="1" initialize-with=". "/>\r
      <et-al font-style="italic"/>\r
    </names>\r
  </macro>\r
  <macro name="locators">\r
    <group delimiter=", ">\r
      <text macro="edition"/>\r
      <group delimiter=" ">\r
        <text term="volume" form="short"/>\r
        <number variable="volume" form="numeric"/>\r
      </group>\r
      <group delimiter=" ">\r
        <number variable="number-of-volumes" form="numeric"/>\r
        <text term="volume" form="short" plural="true"/>\r
      </group>\r
      <group delimiter=" ">\r
        <text term="issue" form="short"/>\r
        <number variable="issue" form="numeric"/>\r
      </group>\r
    </group>\r
  </macro>\r
  <macro name="title">\r
    <choose>\r
      <if type="bill book graphic legal_case legislation motion_picture song standard software" match="any">\r
        <text variable="title" font-style="italic"/>\r
      </if>\r
      <else>\r
        <text variable="title" quotes="true"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="publisher">\r
    <choose>\r
      <if type="bill book chapter graphic legal_case legislation motion_picture paper-conference song" match="any">\r
        <group delimiter=": ">\r
          <text variable="publisher-place"/>\r
          <text variable="publisher"/>\r
        </group>\r
      </if>\r
      <else>\r
        <group delimiter=", ">\r
          <text variable="publisher"/>\r
          <text variable="publisher-place"/>\r
        </group>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="event">\r
    <choose>\r
      <!-- Published Conference Paper -->\r
      <if type="paper-conference speech" match="any">\r
        <choose>\r
          <if variable="container-title" match="any">\r
            <group delimiter=" ">\r
              <text term="in"/>\r
              <text variable="container-title" font-style="italic"/>\r
            </group>\r
          </if>\r
          <!-- Unpublished Conference Paper -->\r
          <else>\r
            <group delimiter=" ">\r
              <text term="presented at"/>\r
              <text variable="event"/>\r
            </group>\r
          </else>\r
        </choose>\r
      </if>\r
    </choose>\r
  </macro>\r
  <macro name="access">\r
    <choose>\r
      <if type="webpage post post-weblog" match="any">\r
        <!-- https://url.com/ (accessed Mon. DD, YYYY). -->\r
        <choose>\r
          <if variable="URL">\r
            <group delimiter=". " prefix=" ">\r
              <group delimiter=": ">\r
                <text term="accessed" text-case="capitalize-first"/>\r
                <date variable="accessed" form="text"/>\r
              </group>\r
              <text term="online" prefix="[" suffix="]" text-case="capitalize-first"/>\r
              <group delimiter=": ">\r
                <text term="available at" text-case="capitalize-first"/>\r
                <text variable="URL"/>\r
              </group>\r
            </group>\r
          </if>\r
        </choose>\r
      </if>\r
      <else-if match="any" variable="DOI">\r
        <!-- doi: 10.1000/xyz123. -->\r
        <text variable="DOI" prefix=" doi: " suffix="."/>\r
      </else-if>\r
      <else-if variable="URL">\r
        <!-- Accessed: Mon. DD, YYYY. [Medium]. Available: https://URL.com/ -->\r
        <group delimiter=". " prefix=" " suffix=". ">\r
          <!-- Accessed: Mon. DD, YYYY. -->\r
          <group delimiter=": ">\r
            <text term="accessed" text-case="capitalize-first"/>\r
            <date variable="accessed" form="text"/>\r
          </group>\r
          <!-- [Online Video]. -->\r
          <group prefix="[" suffix="]" delimiter=" ">\r
            <choose>\r
              <if variable="medium" match="any">\r
                <text variable="medium" text-case="capitalize-first"/>\r
              </if>\r
              <else>\r
                <text term="online" text-case="capitalize-first"/>\r
                <choose>\r
                  <if type="motion_picture">\r
                    <text term="video" text-case="capitalize-first"/>\r
                  </if>\r
                </choose>\r
              </else>\r
            </choose>\r
          </group>\r
        </group>\r
        <!-- Available: https://URL.com/ -->\r
        <group delimiter=": " prefix=" ">\r
          <text term="available at" text-case="capitalize-first"/>\r
          <text variable="URL"/>\r
        </group>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <macro name="page">\r
    <choose>\r
      <if type="article-journal" variable="number" match="all">\r
        <group delimiter=" ">\r
          <text value="Art."/>\r
          <text term="issue" form="short"/>\r
          <text variable="number"/>\r
        </group>\r
      </if>\r
      <else>\r
        <group delimiter=" ">\r
          <label variable="page" form="short"/>\r
          <text variable="page"/>\r
        </group>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="citation-locator">\r
    <group delimiter=" ">\r
      <choose>\r
        <if locator="page">\r
          <label variable="locator" form="short"/>\r
        </if>\r
        <else>\r
          <label variable="locator" form="short" text-case="capitalize-first"/>\r
        </else>\r
      </choose>\r
      <text variable="locator"/>\r
    </group>\r
  </macro>\r
  <macro name="geographic-location">\r
    <group delimiter=", " suffix=".">\r
      <choose>\r
        <if variable="publisher-place">\r
          <text variable="publisher-place" text-case="title"/>\r
        </if>\r
        <else-if variable="event-place">\r
          <text variable="event-place" text-case="title"/>\r
        </else-if>\r
      </choose>\r
    </group>\r
  </macro>\r
  <!-- Series -->\r
  <macro name="collection">\r
    <choose>\r
      <if variable="collection-title" match="any">\r
        <text term="in" suffix=" "/>\r
        <group delimiter=", " suffix=". ">\r
          <text variable="collection-title"/>\r
          <text variable="collection-number" prefix="no. "/>\r
          <text variable="volume" prefix="vol. "/>\r
        </group>\r
      </if>\r
    </choose>\r
  </macro>\r
  <!-- Citation -->\r
  <citation>\r
    <sort>\r
      <key variable="citation-number"/>\r
    </sort>\r
    <layout delimiter=", ">\r
      <group prefix="[" suffix="]" delimiter=", ">\r
        <text variable="citation-number"/>\r
        <text macro="citation-locator"/>\r
      </group>\r
    </layout>\r
  </citation>\r
  <!-- Bibliography -->\r
  <bibliography entry-spacing="0" second-field-align="flush">\r
    <layout>\r
      <!-- Citation Number -->\r
      <text variable="citation-number" prefix="[" suffix="]"/>\r
      <!-- Author(s) -->\r
      <text macro="author" suffix=", "/>\r
      <!-- Rest of Citation -->\r
      <choose>\r
        <!-- Specific Formats -->\r
        <if type="article-journal">\r
          <group delimiter=", ">\r
            <text macro="title"/>\r
            <text variable="container-title" font-style="italic" form="short"/>\r
            <text macro="locators"/>\r
            <text macro="page"/>\r
            <text macro="issued"/>\r
            <text macro="status"/>\r
          </group>\r
          <choose>\r
            <if variable="URL DOI" match="none">\r
              <text value="."/>\r
            </if>\r
            <else>\r
              <text value=","/>\r
            </else>\r
          </choose>\r
          <text macro="access"/>\r
        </if>\r
        <else-if type="paper-conference speech" match="any">\r
          <group delimiter=", " suffix=", ">\r
            <text macro="title"/>\r
            <text macro="event"/>\r
            <text macro="editor"/>\r
          </group>\r
          <text macro="collection"/>\r
          <group delimiter=", " suffix=".">\r
            <text macro="publisher"/>\r
            <text macro="issued"/>\r
            <text macro="page"/>\r
            <text macro="status"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="chapter">\r
          <group delimiter=", " suffix=".">\r
            <text macro="title"/>\r
            <group delimiter=" ">\r
              <text term="in" suffix=" "/>\r
              <text variable="container-title" font-style="italic"/>\r
            </group>\r
            <text macro="locators"/>\r
            <text macro="editor"/>\r
            <text macro="collection"/>\r
            <text macro="publisher"/>\r
            <text macro="issued"/>\r
            <group delimiter=" ">\r
              <label variable="chapter-number" form="short"/>\r
              <text variable="chapter-number"/>\r
            </group>\r
            <text macro="page"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="report">\r
          <group delimiter=", " suffix=".">\r
            <text macro="title"/>\r
            <text macro="publisher"/>\r
            <group delimiter=" ">\r
              <text variable="genre"/>\r
              <text variable="number"/>\r
            </group>\r
            <text macro="issued"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="thesis">\r
          <group delimiter=", " suffix=".">\r
            <text macro="title"/>\r
            <text variable="genre"/>\r
            <text macro="publisher"/>\r
            <text macro="issued"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="software">\r
          <group delimiter=". " suffix=".">\r
            <text macro="title"/>\r
            <text macro="issued" prefix="(" suffix=")"/>\r
            <text variable="genre"/>\r
            <text macro="publisher"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="article">\r
          <group delimiter=", " suffix=".">\r
            <text macro="title"/>\r
            <text macro="issued"/>\r
            <group delimiter=": ">\r
              <text macro="publisher" font-style="italic"/>\r
              <text variable="number"/>\r
            </group>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="webpage post-weblog post" match="any">\r
          <group delimiter=", " suffix=".">\r
            <text macro="title"/>\r
            <text variable="container-title"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="patent">\r
          <group delimiter=", ">\r
            <text macro="title"/>\r
            <text variable="number"/>\r
            <text macro="issued"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <!-- Online Video -->\r
        <else-if type="motion_picture">\r
          <text macro="geographic-location" suffix=". "/>\r
          <group delimiter=", " suffix=".">\r
            <text macro="title"/>\r
            <text macro="issued"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="standard">\r
          <group delimiter=", " suffix=".">\r
            <text macro="title"/>\r
            <group delimiter=" ">\r
              <text variable="genre"/>\r
              <text variable="number"/>\r
            </group>\r
            <text macro="geographic-location"/>\r
            <text macro="issued"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <!-- Generic/Fallback Formats -->\r
        <else-if type="bill book graphic legal_case legislation report song" match="any">\r
          <group delimiter=", " suffix=". ">\r
            <text macro="title"/>\r
            <text macro="locators"/>\r
          </group>\r
          <text macro="collection"/>\r
          <group delimiter=", " suffix=".">\r
            <text macro="publisher"/>\r
            <text macro="issued"/>\r
            <text macro="page"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else-if type="article-magazine article-newspaper broadcast interview manuscript map patent personal_communication song speech thesis webpage" match="any">\r
          <group delimiter=", " suffix=".">\r
            <text macro="title"/>\r
            <text variable="container-title" font-style="italic"/>\r
            <text macro="locators"/>\r
            <text macro="publisher"/>\r
            <text macro="page"/>\r
            <text macro="issued"/>\r
          </group>\r
          <text macro="access"/>\r
        </else-if>\r
        <else>\r
          <group delimiter=", " suffix=". ">\r
            <text macro="title"/>\r
            <text variable="container-title" font-style="italic"/>\r
            <text macro="locators"/>\r
          </group>\r
          <text macro="collection"/>\r
          <group delimiter=", " suffix=".">\r
            <text macro="publisher"/>\r
            <text macro="page"/>\r
            <text macro="issued"/>\r
          </group>\r
          <text macro="access"/>\r
        </else>\r
      </choose>\r
    </layout>\r
  </bibliography>\r
</style>\r
`;export{r as default};
